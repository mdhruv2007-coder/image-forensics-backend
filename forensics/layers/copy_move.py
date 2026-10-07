"""Copy-move forgery detection layer.

Detects regions that were duplicated *within the same image* by matching
local feature descriptors against each other, discarding trivial matches,
and clustering the surviving pairs by their displacement vector.

Pipeline:
    1. Detect keypoints + descriptors (SIFT by default).
    2. k-NN match the descriptor set against itself. Candidates that sit
       spatially close to the query keypoint (including the keypoint itself
       and same-location duplicates SIFT emits for multiple orientations)
       are dropped *before* the ratio test, so they cannot be mistaken for a
       match nor poison the ratio test as a "second-best" competitor.
    3. Apply Lowe's ratio test to keep only distinctive matches.
    4. Group pairs whose displacement vector (copy - original) agrees; a
       real copy-move usually has one consistent offset.
    5. Score from the number of clustered pairs and how tight the clusters
       are.

SIFT vs ORB trade-off
---------------------
SIFT is more robust to rotation/scale changes in the duplicated region but
is slower and produces float descriptors (L2 distance). ORB is a much
faster drop-in alternative with binary descriptors (Hamming distance) but
is less robust and finds fewer keypoints on smooth regions. To switch,
change the single ``FEATURE_BACKEND`` constant below; the detector and the
matcher norm are both selected from it. (ORB's descriptor distances are on
a different scale, so you will likely want to loosen ``RATIO_THRESHOLD``
to roughly 0.75-0.8 when using it.)

Limitation: clustering by displacement assumes (near-)pure translation.
Rotated or scaled pastes still yield matches, but they scatter across
several displacement vectors and may fall below ``MIN_CLUSTER_SIZE``.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from PIL import Image

from forensics.layers.base import make_skipped_result
from forensics.schemas import LayerResult

__all__ = ["CopyMoveLayer", "LAYER_NAME", "run"]

LAYER_NAME = "copy_move"

# --- Tunables ---------------------------------------------------------------

# One-line backend swap: "sift" (robust, slower) or "orb" (fast, weaker).
FEATURE_BACKEND = "sift"

MAX_ANALYSIS_DIM = 1600       # Downscale larger images for speed; coords are scaled back.
MIN_KEYPOINTS = 50            # Below this the image is too blank/featureless to judge.
KNN_K = 5                     # Neighbours fetched per keypoint before filtering.
RATIO_THRESHOLD = 0.6         # Lowe ratio test (best / second-best distance).
MIN_PAIR_DISTANCE_FRAC = 0.02  # Pairs closer than this fraction of the long side are trivial.
MIN_PAIR_DISTANCE_PX = 10.0   # ...and never closer than this many pixels.
MAX_PAIRS = 2000              # Cap on pairs clustered (keeps O(n^2) clustering bounded).
CLUSTER_TOLERANCE_PX = 8.0    # Max displacement-vector deviation within a cluster.
MIN_CLUSTER_SIZE = 4          # Minimum pairs for a cluster to count as evidence.
MIN_CLUSTER_EXTENT_PX = 20.0  # Cluster keypoints must span at least this much (analysis px).
SCORE_SATURATION = 12.0       # Pair count at which the count-score reaches ~63%.


def _create_detector() -> tuple[Any, int]:
    """Return ``(detector, matcher_norm)`` for the configured backend."""
    if FEATURE_BACKEND == "sift":
        return cv2.SIFT_create(), cv2.NORM_L2
    if FEATURE_BACKEND == "orb":
        return cv2.ORB_create(nfeatures=5000), cv2.NORM_HAMMING
    raise ValueError(f"Unknown FEATURE_BACKEND: {FEATURE_BACKEND!r}")


def _prepare_gray(image: Image.Image) -> tuple[np.ndarray, float]:
    """Convert to uint8 grayscale, downscaling if large. Returns (gray, scale)."""
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    height, width = gray.shape
    longest = max(height, width)
    if longest > MAX_ANALYSIS_DIM:
        scale = MAX_ANALYSIS_DIM / longest
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
        return gray, scale
    return gray, 1.0


def _failed_result(reason: str) -> LayerResult:
    return LayerResult(
        layer_name=LAYER_NAME,
        score=0.0,
        reliability="low",
        status="failed",
        detail={"reason": reason, "message": f"Layer '{LAYER_NAME}' failed: {reason}."},
        heatmap_png_b64=None,
    )


def _match_within_image(
    points: np.ndarray,
    descriptors: np.ndarray,
    norm: int,
    min_distance: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find non-trivial descriptor matches inside one image.

    Returns ``(src, dst, ratios)`` where ``src``/``dst`` are ``(N, 2)``
    float arrays oriented so that ``dst - src`` lies in a canonical
    half-plane (making a pair and its mirror identical), and ``ratios`` are
    the ratio-test values (lower is more distinctive).
    """
    matcher = cv2.BFMatcher(norm)
    knn = matcher.knnMatch(descriptors, descriptors, k=min(KNN_K, len(descriptors)))

    best_by_pair: dict[tuple[int, int], float] = {}
    for matches in knn:
        if not matches:
            continue
        query_idx = matches[0].queryIdx
        qpt = points[query_idx]
        # Drop self, same-location duplicates and immediate neighbours.
        candidates = [
            m
            for m in matches
            if float(np.hypot(*(points[m.trainIdx] - qpt))) >= min_distance
        ]
        if len(candidates) < 2:
            continue
        best, second = candidates[0], candidates[1]
        if second.distance <= 0.0:
            continue
        ratio = best.distance / second.distance
        if ratio >= RATIO_THRESHOLD:
            continue
        key = (min(query_idx, best.trainIdx), max(query_idx, best.trainIdx))
        if ratio < best_by_pair.get(key, float("inf")):
            best_by_pair[key] = ratio

    if not best_by_pair:
        empty = np.empty((0, 2), dtype=np.float64)
        return empty, empty, np.empty(0, dtype=np.float64)

    keys = list(best_by_pair)
    ratios = np.array([best_by_pair[k] for k in keys], dtype=np.float64)
    order = np.argsort(ratios)[:MAX_PAIRS]
    keys = [keys[i] for i in order]
    ratios = ratios[order]

    a = points[[k[0] for k in keys]].astype(np.float64)
    b = points[[k[1] for k in keys]].astype(np.float64)
    # Canonical orientation: displacement points right (or down if vertical).
    delta = b - a
    flip = (delta[:, 0] < 0) | ((delta[:, 0] == 0) & (delta[:, 1] < 0))
    src = np.where(flip[:, None], b, a)
    dst = np.where(flip[:, None], a, b)
    return src, dst, ratios


def _cluster_displacements(disp: np.ndarray) -> list[np.ndarray]:
    """Greedy mode-seeking clustering of displacement vectors.

    Repeatedly takes the displacement with the most neighbours within
    ``CLUSTER_TOLERANCE_PX``, refines around the centroid, and removes the
    members. Returns index arrays (into ``disp``) for clusters with at
    least ``MIN_CLUSTER_SIZE`` members.
    """
    remaining = np.arange(len(disp))
    clusters: list[np.ndarray] = []
    while len(remaining) >= MIN_CLUSTER_SIZE:
        d = disp[remaining]
        dist = np.linalg.norm(d[:, None, :] - d[None, :, :], axis=2)
        counts = (dist <= CLUSTER_TOLERANCE_PX).sum(axis=1)
        seed = int(counts.argmax())
        if counts[seed] < MIN_CLUSTER_SIZE:
            break
        seed_members = np.flatnonzero(dist[seed] <= CLUSTER_TOLERANCE_PX)
        centroid = d[seed_members].mean(axis=0)
        members = np.flatnonzero(np.linalg.norm(d - centroid, axis=1) <= CLUSTER_TOLERANCE_PX)
        if len(members) < MIN_CLUSTER_SIZE:
            remaining = np.delete(remaining, seed)  # guarantee progress
            continue
        clusters.append(remaining[members])
        remaining = np.delete(remaining, members)
    return clusters


def _bbox(points: np.ndarray, scale: float) -> dict[str, int]:
    """Bounding box of ``points`` mapped back to original-image pixels."""
    lo = np.floor(points.min(axis=0) / scale).astype(int)
    hi = np.ceil(points.max(axis=0) / scale).astype(int)
    return {"x1": int(lo[0]), "y1": int(lo[1]), "x2": int(hi[0]), "y2": int(hi[1])}


def _extent(points: np.ndarray) -> float:
    return float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))


def _score_and_reliability(
    cluster_sizes: list[int],
    cluster_spreads: list[float],
    keypoint_count: int,
) -> tuple[float, str]:
    """Combine pair count and displacement consistency into (score, reliability)."""
    total = sum(cluster_sizes)
    if total == 0:
        reliability = "medium" if keypoint_count >= 150 else "low"
        return 0.0, reliability

    count_score = 1.0 - math.exp(-total / SCORE_SATURATION)
    # Size-weighted mean deviation from each cluster's centroid, as a
    # fraction of the tolerance: 0 = perfectly consistent, 1 = at the edge.
    mean_spread = sum(s * n for s, n in zip(cluster_spreads, cluster_sizes)) / total
    consistency = max(0.0, 1.0 - mean_spread / CLUSTER_TOLERANCE_PX)
    score = min(1.0, max(0.0, count_score * (0.6 + 0.4 * consistency)))

    if total >= 10 and keypoint_count >= 300:
        reliability = "high"
    elif total >= MIN_CLUSTER_SIZE and keypoint_count >= 100:
        reliability = "medium"
    else:
        reliability = "low"
    return score, reliability


class CopyMoveLayer:
    """Copy-move detector satisfying the ``Layer`` protocol."""

    def run(self, image: Image.Image) -> LayerResult:
        """Analyze ``image`` for duplicated regions.

        Coordinates in ``detail`` are in the coordinate space of the
        ``image`` passed in (i.e. the normalized image), even if it was
        internally downscaled for speed.
        """
        try:
            detector, norm = _create_detector()
        except (cv2.error, AttributeError, ValueError) as exc:
            return make_skipped_result(LAYER_NAME, f"feature detector unavailable ({exc})")

        try:
            gray, scale = _prepare_gray(image)
            keypoints, descriptors = detector.detectAndCompute(gray, None)
        except cv2.error as exc:
            return _failed_result(f"keypoint detection error: {exc}")

        keypoint_count = 0 if descriptors is None else len(keypoints)
        if descriptors is None or keypoint_count < MIN_KEYPOINTS:
            return make_skipped_result(
                LAYER_NAME,
                f"too few keypoints ({keypoint_count} < {MIN_KEYPOINTS}) for meaningful analysis",
            )

        points = np.array([kp.pt for kp in keypoints], dtype=np.float64)
        min_distance = max(MIN_PAIR_DISTANCE_PX, MIN_PAIR_DISTANCE_FRAC * max(gray.shape))

        try:
            src, dst, ratios = _match_within_image(points, descriptors, norm, min_distance)
        except cv2.error as exc:
            return _failed_result(f"descriptor matching error: {exc}")

        raw_match_count = len(src)
        clusters: list[np.ndarray] = []
        if raw_match_count >= MIN_CLUSTER_SIZE:
            disp = dst - src
            for members in _cluster_displacements(disp):
                both = np.vstack([src[members], dst[members]])
                if _extent(both) >= MIN_CLUSTER_EXTENT_PX:
                    clusters.append(members)
            clusters.sort(key=len, reverse=True)

        matched_pairs: list[tuple[float, float, float, float, int]] = []
        match_regions: list[dict[str, int]] = []
        cluster_info: list[dict[str, Any]] = []
        sizes: list[int] = []
        spreads: list[float] = []

        for cid, members in enumerate(clusters):
            s, d = src[members], dst[members]
            disp = d - s
            centroid = disp.mean(axis=0)
            spread = float(np.linalg.norm(disp - centroid, axis=1).mean())
            sizes.append(len(members))
            spreads.append(spread)

            for (x1, y1), (x2, y2) in zip(s / scale, d / scale):
                matched_pairs.append(
                    (round(float(x1), 1), round(float(y1), 1),
                     round(float(x2), 1), round(float(y2), 1), cid)
                )
            match_regions.append(_bbox(s, scale))
            match_regions.append(_bbox(d, scale))
            cluster_info.append(
                {
                    "cluster_id": cid,
                    "pair_count": int(len(members)),
                    "displacement": [
                        round(float(centroid[0] / scale), 1),
                        round(float(centroid[1] / scale), 1),
                    ],
                    "mean_spread_px": round(spread / scale, 2),
                    "mean_ratio": round(float(ratios[members].mean()), 3),
                }
            )

        score, reliability = _score_and_reliability(sizes, spreads, keypoint_count)

        width, height = image.size
        return LayerResult(
            layer_name=LAYER_NAME,
            score=score,
            reliability=reliability,  # type: ignore[arg-type]
            status="ok",
            detail={
                # (x1, y1, x2, y2, cluster_id) per pair; feed to draw_match_lines().
                "matched_pairs": matched_pairs,
                "match_regions": match_regions,  # two boxes (source, copy) per cluster
                "match_count": len(clusters),    # number of duplicated-region candidates
                "clusters": cluster_info,
                "keypoint_count": keypoint_count,
                "raw_match_count": raw_match_count,
                "feature_backend": FEATURE_BACKEND,
                "analysis_scale": round(scale, 4),
                "image_size": {"width": width, "height": height},
            },
            heatmap_png_b64=None,
        )


def run(image: Image.Image) -> LayerResult:
    """Module-level convenience wrapper around :class:`CopyMoveLayer`."""
    return CopyMoveLayer().run(image)
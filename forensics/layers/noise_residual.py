"""Noise-residual inconsistency layer for image tamper detection.

Approach
--------
1. Convert the image to grayscale and denoise it with a 3x3 median filter.
2. Subtract the denoised image from the original; what remains is the
   *noise residual* (sensor noise, demosaicing/processing artifacts, plus
   some leaked edge content).
3. Mask out pixels that would contaminate a noise estimate: strong edges
   (their energy leaks into the residual) and clipped shadows/highlights.
4. Split the image into a grid of patches and estimate a robust noise
   sigma (MAD) per patch from the remaining pixels.
5. A single untouched photo should have broadly consistent noise across
   patches. A region spliced in from another source often does not. The
   suspicion score combines the overall spread of per-patch log-sigma and
   the fraction of patches that deviate strongly from the median.

Limitations (read before trusting the output)
---------------------------------------------
This technique is inherently noisier and lower-precision than ELA or
copy-move detection. Ordinary variation in lighting, exposure, ISO
gain, local contrast, depth-of-field blur, and JPEG recompression changes
the noise level across a perfectly real photo, so false positives are
common. For that reason this layer's reliability is deliberately
conservative: it is never reported as ``"high"`` and is capped at
``"medium"``, and it only reaches ``"medium"`` when there is enough clean
data and the score sits at a clear extreme. All thresholds below are
heuristic starting points and are not calibrated against a dataset.

Output notes
------------
The per-patch inconsistency heatmap is returned in
``LayerResult.heatmap_png_b64`` (the schema's dedicated field), not
inside ``detail``. Bounding boxes of outlier patches are provided in
``detail["outlier_regions"]`` in the *input image's* pixel coordinates.
"""

from __future__ import annotations

import base64
import io
from typing import Final

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy import ndimage

from forensics.layers.base import make_skipped_result
from forensics.schemas import LayerResult

__all__ = ["NoiseResidualLayer", "NOISE_RESIDUAL_LAYER", "LAYER_NAME"]

LAYER_NAME: Final[str] = "noise_residual"

# --- Tunable constants (heuristic, uncalibrated) ---------------------------
_MIN_IMAGE_SIDE: Final[int] = 96          # px; smaller images can't form a usable grid
_MEDIAN_SIZE: Final[int] = 3              # median filter window
_MIN_PATCH: Final[int] = 32               # px; smallest patch side
_TARGET_GRID: Final[int] = 10             # aim for roughly this many patches on the short side
_MAX_GRID: Final[int] = 24                # cap patches per side
_MIN_GRID: Final[int] = 3                 # need at least 3x3 patches
_EDGE_PERCENTILE: Final[float] = 90.0     # only the strongest edges are masked; per-patch MAD handles the rest
_EDGE_SMOOTH_SIGMA: Final[float] = 3.0    # Gaussian sigma before gradient (noise-independent edges)
_CLIP_LOW: Final[int] = 3                 # pixels <= this are treated as clipped
_CLIP_HIGH: Final[int] = 252              # pixels >= this are treated as clipped
_MIN_VALID_FRACTION: Final[float] = 0.25  # min usable pixel fraction within a patch
_MIN_VALID_PATCHES: Final[int] = 6        # below this, skip the layer
_SIGMA_FLOOR: Final[float] = 0.1          # intensity units (0-255); avoids log(0) on flat data
_OUTLIER_LOG_DEV: Final[float] = 0.5      # |ln(sigma/median)| > 0.5, i.e. ~1.65x off
_SPREAD_LO: Final[float] = 0.10           # std of ln(sigma) mapping to spread term 0
_SPREAD_HI: Final[float] = 0.40           # ... mapping to spread term 1
_OUTLIER_FRAC_LO: Final[float] = 0.02     # outlier fraction mapping to term 0
_OUTLIER_FRAC_HI: Final[float] = 0.10     # ... mapping to term 1
_ADEQUATE_PATCHES: Final[int] = 36        # patches needed before "medium" reliability
_ADEQUATE_VALID_FRAC: Final[float] = 0.5  # fraction of grid that must be usable
_CLEAR_HIGH_SCORE: Final[float] = 0.75    # "extremely clear" inconsistency
_CLEAR_LOW_SCORE: Final[float] = 0.25     # clearly consistent
_HEATMAP_MAX_SIDE: Final[int] = 512       # px; long side of the returned heatmap
_HEATMAP_DEV_FULL_SCALE: Final[float] = 0.8  # |ln dev| that maps to full red
_MAX_OUTLIER_REGIONS: Final[int] = 25

_FloatArray = NDArray[np.float64]


class NoiseResidualLayer:
    """Detects splicing via inconsistent local noise levels."""

    def run(self, image: Image.Image) -> LayerResult:
        """Analyze ``image`` and return the noise-residual layer result.

        Args:
            image: Any PIL image. It is converted to 8-bit grayscale
                internally; the original object is not modified.

        Returns:
            A ``LayerResult`` with ``status="ok"``, or a skipped result
            (via ``make_skipped_result``) when the image is corrupt,
            too small, or has too little clean area to estimate noise.
        """
        gray = _load_gray(image)
        if gray is None:
            return make_skipped_result(
                LAYER_NAME, "image could not be decoded or converted to grayscale"
            )

        height, width = gray.shape
        if min(height, width) < _MIN_IMAGE_SIDE:
            return make_skipped_result(
                LAYER_NAME,
                f"image too small ({width}x{height}); need at least "
                f"{_MIN_IMAGE_SIDE}px on each side",
            )

        rows, cols = _grid_shape(height, width)
        if rows < _MIN_GRID or cols < _MIN_GRID:
            return make_skipped_result(
                LAYER_NAME, "image too small to form a usable patch grid"
            )

        residual, valid = _residual_and_mask(gray)
        y_edges = _edges(height, rows)
        x_edges = _edges(width, cols)
        sigma = _patch_sigmas(residual, valid, y_edges, x_edges)

        usable = np.isfinite(sigma)
        n_valid = int(usable.sum())
        n_total = rows * cols
        if n_valid < _MIN_VALID_PATCHES:
            return make_skipped_result(
                LAYER_NAME,
                "too little low-texture, unclipped area to estimate noise reliably",
            )

        log_sigma = np.log(sigma[usable])
        median_ls = float(np.median(log_sigma))
        spread = float(np.std(log_sigma))
        deviation = np.full(sigma.shape, np.nan, dtype=np.float64)
        deviation[usable] = np.abs(log_sigma - median_ls)
        outlier = usable & (np.nan_to_num(deviation, nan=0.0) > _OUTLIER_LOG_DEV)
        outlier_fraction = float(outlier.sum() / n_valid)

        score = _score(spread, outlier_fraction)
        reliability = _reliability(score, n_valid, n_total)

        detail: dict[str, object] = {
            "image_size": {"width": width, "height": height},
            "patch_grid": {"rows": rows, "cols": cols},
            "total_patches": n_total,
            "valid_patches": n_valid,
            "median_noise_sigma": round(float(np.exp(median_ls)), 4),
            "log_sigma_std": round(spread, 4),
            "outlier_fraction": round(outlier_fraction, 4),
            "outlier_regions": _outlier_boxes(
                outlier, deviation, y_edges, x_edges
            ),
            "denoiser": f"median_{_MEDIAN_SIZE}x{_MEDIAN_SIZE}",
        }

        return LayerResult(
            layer_name=LAYER_NAME,
            score=score,
            reliability=reliability,
            status="ok",
            detail=detail,
            heatmap_png_b64=_render_heatmap(deviation, height, width),
        )


NOISE_RESIDUAL_LAYER: Final[NoiseResidualLayer] = NoiseResidualLayer()


# --- Helpers ----------------------------------------------------------------

def _load_gray(image: Image.Image) -> NDArray[np.float32] | None:
    """Return the image as a float32 grayscale array, or ``None`` on failure."""
    try:
        # convert() forces a full decode, so truncated/corrupt data raises here.
        # Pillow raises a wide variety of exception types for bad input.
        gray = image.convert("L")
        return np.asarray(gray, dtype=np.float32)
    except Exception:  # noqa: BLE001
        return None


def _grid_shape(height: int, width: int) -> tuple[int, int]:
    """Choose a (rows, cols) patch grid with roughly square patches."""
    patch = max(_MIN_PATCH, min(height, width) // _TARGET_GRID)
    rows = min(_MAX_GRID, height // patch)
    cols = min(_MAX_GRID, width // patch)
    return rows, cols


def _edges(length: int, parts: int) -> NDArray[np.int64]:
    """Integer cell boundaries that tile ``length`` pixels exactly."""
    return np.linspace(0, length, parts + 1).round().astype(np.int64)


def _residual_and_mask(
    gray: NDArray[np.float32],
) -> tuple[NDArray[np.float32], NDArray[np.bool_]]:
    """Compute the noise residual and the mask of pixels fit for noise estimation."""
    denoised = ndimage.median_filter(gray, size=_MEDIAN_SIZE, mode="reflect")
    residual = gray - denoised

    # Edges are measured on a strongly smoothed copy so the gradient reflects
    # scene structure, not noise. Otherwise noisier regions would be masked
    # out more often, biasing exactly the statistic we want to compare.
    smooth = ndimage.gaussian_filter(gray, sigma=_EDGE_SMOOTH_SIGMA, mode="reflect")
    gx = ndimage.sobel(smooth, axis=1, mode="reflect")
    gy = ndimage.sobel(smooth, axis=0, mode="reflect")
    magnitude = np.hypot(gx, gy)
    edge_threshold = np.percentile(magnitude, _EDGE_PERCENTILE)

    not_edge = magnitude <= edge_threshold
    not_clipped = (gray > _CLIP_LOW) & (gray < _CLIP_HIGH)
    return residual, not_edge & not_clipped


def _patch_sigmas(
    residual: NDArray[np.float32],
    valid: NDArray[np.bool_],
    y_edges: NDArray[np.int64],
    x_edges: NDArray[np.int64],
) -> _FloatArray:
    """Robust (MAD-based) noise sigma per patch; NaN where data is insufficient."""
    rows, cols = len(y_edges) - 1, len(x_edges) - 1
    sigma = np.full((rows, cols), np.nan, dtype=np.float64)
    for i in range(rows):
        for j in range(cols):
            ys, ye = y_edges[i], y_edges[i + 1]
            xs, xe = x_edges[j], x_edges[j + 1]
            mask = valid[ys:ye, xs:xe]
            if mask.sum() < _MIN_VALID_FRACTION * mask.size:
                continue
            values = residual[ys:ye, xs:xe][mask].astype(np.float64)
            center = np.median(values)
            mad = 1.4826 * np.median(np.abs(values - center))
            sigma[i, j] = max(float(mad), _SIGMA_FLOOR)
    return sigma


def _ramp(value: float, low: float, high: float) -> float:
    """Linearly map ``value`` from [low, high] to [0, 1], clamped."""
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def _score(spread: float, outlier_fraction: float) -> float:
    """Combine global spread and outlier prevalence into a 0-1 suspicion score."""
    spread_term = _ramp(spread, _SPREAD_LO, _SPREAD_HI)
    outlier_term = _ramp(outlier_fraction, _OUTLIER_FRAC_LO, _OUTLIER_FRAC_HI)
    return float(np.clip(0.5 * spread_term + 0.5 * outlier_term, 0.0, 1.0))


def _reliability(score: float, n_valid: int, n_total: int) -> str:
    """Conservative reliability: never ``"high"``; ``"medium"`` only when warranted.

    Medium requires enough clean patches AND a score at a clear extreme
    (very consistent or very inconsistent). Ambiguous mid-range scores are
    exactly where lighting/exposure variation causes false positives, so
    they stay ``"low"``.
    """
    adequate = (
        n_valid >= _ADEQUATE_PATCHES
        and n_valid / n_total >= _ADEQUATE_VALID_FRAC
    )
    clear = score >= _CLEAR_HIGH_SCORE or score <= _CLEAR_LOW_SCORE
    return "medium" if adequate and clear else "low"


def _outlier_boxes(
    outlier: NDArray[np.bool_],
    deviation: _FloatArray,
    y_edges: NDArray[np.int64],
    x_edges: NDArray[np.int64],
) -> list[dict[str, int | float]]:
    """Bounding boxes (input-image pixels) of the most deviant outlier patches."""
    cells = [(int(i), int(j)) for i, j in zip(*np.nonzero(outlier))]
    cells.sort(key=lambda c: float(deviation[c]), reverse=True)
    boxes: list[dict[str, int | float]] = []
    for i, j in cells[:_MAX_OUTLIER_REGIONS]:
        boxes.append(
            {
                "x1": int(x_edges[j]),
                "y1": int(y_edges[i]),
                "x2": int(x_edges[j + 1]),
                "y2": int(y_edges[i + 1]),
                "log_deviation": round(float(deviation[i, j]), 4),
            }
        )
    return boxes


def _render_heatmap(deviation: _FloatArray, height: int, width: int) -> str:
    """Render per-patch noise deviation as a base64 PNG (blue=consistent, red=odd).

    Patches without enough clean data are drawn mid-gray. The output keeps the
    input image's aspect ratio, with its long side capped at ``_HEATMAP_MAX_SIDE``.
    """
    t = np.clip(np.nan_to_num(deviation, nan=0.0) / _HEATMAP_DEV_FULL_SCALE, 0.0, 1.0)
    stops = np.array(
        [[40.0, 70.0, 170.0], [245.0, 215.0, 60.0], [215.0, 30.0, 30.0]]
    )
    t2 = t * 2.0
    lo = np.clip(np.floor(t2), 0, 1).astype(np.int64)
    frac = (t2 - lo)[..., None]
    rgb = stops[lo] * (1.0 - frac) + stops[lo + 1] * frac
    rgb[~np.isfinite(deviation)] = (128.0, 128.0, 128.0)

    grid_img = Image.fromarray(rgb.round().astype(np.uint8), mode="RGB")
    scale = min(1.0, _HEATMAP_MAX_SIDE / max(height, width))
    out_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    heatmap = grid_img.resize(out_size, resample=Image.Resampling.NEAREST)

    buffer = io.BytesIO()
    heatmap.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
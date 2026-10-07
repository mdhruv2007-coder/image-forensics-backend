"""Visualization helper for copy-move detection results."""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np
from PIL import Image

__all__ = ["draw_match_lines"]

# Bright, mutually distinct colors in BGR order (OpenCV convention).
_PALETTE_BGR: tuple[tuple[int, int, int], ...] = (
    (0, 255, 0),      # green
    (0, 0, 255),      # red
    (255, 255, 0),    # cyan
    (0, 255, 255),    # yellow
    (255, 0, 255),    # magenta
    (0, 165, 255),    # orange
    (255, 128, 0),    # azure
    (128, 0, 255),    # pink
)


def draw_match_lines(image: Image.Image, matched_pairs: list[tuple]) -> bytes:
    """Draw lines between duplicated-region keypoint pairs and return PNG bytes.

    Args:
        image: The (normalized) image the pairs' coordinates refer to.
        matched_pairs: Pairs from ``LayerResult.detail["matched_pairs"]``,
            each ``(x1, y1, x2, y2, cluster_id)``. ``cluster_id`` may be
            omitted (4-tuples are drawn as cluster 0). Lists work as well
            as tuples, so JSON round-tripped data is accepted. Each cluster
            gets its own color.

    Returns:
        PNG-encoded image bytes, ready for base64 encoding.

    Raises:
        ValueError: If a pair is malformed or PNG encoding fails.
    """
    canvas = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    canvas = np.ascontiguousarray(canvas)

    long_side = max(canvas.shape[:2])
    thickness = max(1, round(long_side / 600))
    radius = max(2, round(long_side / 250))

    for pair in matched_pairs:
        values: Sequence[float] = pair
        if len(values) == 4:
            x1, y1, x2, y2 = values
            cluster_id = 0
        elif len(values) == 5:
            x1, y1, x2, y2, cluster_id = values
        else:
            raise ValueError(f"Expected (x1, y1, x2, y2[, cluster_id]), got {pair!r}")

        color = _PALETTE_BGR[int(cluster_id) % len(_PALETTE_BGR)]
        p1 = (int(round(x1)), int(round(y1)))
        p2 = (int(round(x2)), int(round(y2)))
        cv2.line(canvas, p1, p2, color, thickness, cv2.LINE_AA)
        cv2.circle(canvas, p1, radius, color, thickness, cv2.LINE_AA)
        cv2.circle(canvas, p2, radius, color, thickness, cv2.LINE_AA)

    ok, encoded = cv2.imencode(".png", canvas)
    if not ok:
        raise ValueError("Failed to encode match-line visualization as PNG")
    return encoded.tobytes()
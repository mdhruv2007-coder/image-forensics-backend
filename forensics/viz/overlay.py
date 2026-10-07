"""
forensics/viz/overlay.py

Colorizes a per-pixel / per-region tamper-suspicion map into a standalone
heatmap PNG, returned as a base64 string.

This module deliberately does NOT blend the heatmap onto the original image
and has no opacity parameter. Blending is done client-side with CSS so that
dragging an opacity slider never triggers a network request. The function is
pure and stateless: same input array, same output string.

Colormap choice: ``COLORMAP_TURBO``. It runs dark blue -> cyan -> green ->
yellow -> orange -> red, which reads naturally as "cool = fine, hot =
suspicious" for non-technical viewers, and unlike ``COLORMAP_JET`` it is
perceptually smoother (no misleading bright bands in the middle of the range).
Requires OpenCV >= 4.1.0.
"""

from __future__ import annotations

import base64

import cv2
import numpy as np

__all__ = ["make_heatmap_png"]

_COLORMAP: int = cv2.COLORMAP_TURBO


def make_heatmap_png(suspicion_map: np.ndarray) -> str:
    """Convert a 2D suspicion map (values 0-1) into a base64-encoded PNG heatmap.

    Args:
        suspicion_map: 2D array of shape ``(H, W)`` with values in ``[0, 1]``,
            where 0 is "no suspicion" and 1 is "highest suspicion". Values
            outside that range are clipped; NaN is treated as 0 and +/-inf as
            1 / 0 respectively. Any real numeric dtype is accepted.

    Returns:
        The PNG image as a base64-encoded ASCII string (no ``data:`` prefix),
        ready to place in a JSON field and used by the frontend as
        ``<img src="data:image/png;base64,...">``. The output has the same
        height and width as the input array.

    Raises:
        ValueError: If the input is not a non-empty 2D array, or PNG
            encoding fails.
    """
    arr = np.asarray(suspicion_map)
    if arr.ndim != 2:
        raise ValueError(
            f"suspicion_map must be 2D (H, W); got array with shape {arr.shape}"
        )
    if arr.size == 0:
        raise ValueError("suspicion_map must not be empty")
    if not np.issubdtype(arr.dtype, np.number) and arr.dtype != np.bool_:
        raise ValueError(f"suspicion_map must be numeric; got dtype {arr.dtype}")

    # Sanitize: NaN -> 0 (no suspicion), +inf -> 1, -inf -> 0, then clip to [0, 1].
    values = np.nan_to_num(
        arr.astype(np.float32), nan=0.0, posinf=1.0, neginf=0.0
    )
    values = np.clip(values, 0.0, 1.0)

    gray_u8: np.ndarray = np.rint(values * 255.0).astype(np.uint8)
    colored_bgr: np.ndarray = cv2.applyColorMap(gray_u8, _COLORMAP)

    # cv2.imencode expects BGR input, which is exactly what applyColorMap returns.
    ok, encoded = cv2.imencode(".png", colored_bgr)
    if not ok:
        raise ValueError("Failed to encode heatmap as PNG")

    return base64.b64encode(encoded.tobytes()).decode("ascii")
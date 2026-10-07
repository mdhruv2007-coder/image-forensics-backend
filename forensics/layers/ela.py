"""
forensics/layers/ela.py

Error Level Analysis (ELA) detection layer.

How ELA works
-------------
JPEG is lossy: every time a region is saved, its 8x8 DCT blocks are
quantized, and after a few save cycles the region settles into a state
where re-compressing it changes it very little. If we re-save an image at
a known quality and subtract the result from the original, regions that
have already been through similar compression show *low* error, while
regions that were pasted in, retouched, or generated separately (and so
have a different compression history) tend to show *higher* error than
their surroundings. A few sharply higher-error regions against an
otherwise consistent background is the classic ELA signature of local
editing.

What ELA cannot tell you
------------------------
* **Non-JPEG input (PNG, BMP, lossless WebP, TIFF...) is a known
  limitation.** ELA's signal comes entirely from JPEG quantization
  history. A lossless file has no such history (or it was discarded when
  the file was converted), so every pixel is "new" to the JPEG encoder and
  the error map mostly reflects image content (edges, texture, noise)
  rather than editing. We still run the technique on such inputs, but the
  layer reports ``reliability="low"``, damps the score, and records the
  situation in ``detail`` so downstream fusion weights it accordingly.
* Uniformly high error usually means a low-quality or heavily
  re-compressed source, not tampering. The score therefore rewards
  *localized outliers*, not overall error magnitude.
* ELA is a heuristic. It can be fooled by re-saving the whole image after
  editing, and high-contrast edges produce legitimate error spikes.

ASSUMPTIONS ABOUT forensics/layers/base.py (the uploaded file was empty)
------------------------------------------------------------------------
* ``Layer`` is a structural protocol with a ``run(image) -> LayerResult``
  method (a ``name`` attribute is provided here for convenience).
* ``base.py`` may expose a helper for skipped results. This module looks
  for ``skipped_result(layer_name, reason)`` and falls back to building the
  ``LayerResult`` directly if it is absent. Adjust ``_skipped`` if your
  helper has a different name or signature.
"""

from __future__ import annotations

import base64
import io
from typing import Any

import numpy as np
from scipy import ndimage
from PIL import Image, ImageChops, UnidentifiedImageError

from forensics.schemas import LayerResult

try:  # Helper name/signature is assumed; see module docstring.
    from forensics.layers.base import skipped_result as _base_skipped_result
except ImportError:  # pragma: no cover - depends on base.py contents
    _base_skipped_result = None

__all__ = ["ELALayer"]

LAYER_NAME = "ela"
RESAVE_QUALITY = 90
BLOCK_SIZE = 16
MIN_DIMENSION = BLOCK_SIZE  # smaller than one block: nothing to compare
MIN_BLOCKS_FOR_RELIABILITY = 16
OUTLIER_SIGMAS = 4.0
NON_JPEG_SCORE_DAMPING = 0.5
MIN_MEANINGFUL_BLOCK_ERROR = 2.0  # below this (0-255 scale) error is noise
_EPS = 1e-6
TEXTURE_OFFSET = 8.0   # keeps flat blocks from dominating the ratio
TEXTURE_SCALE = 10.0   # brings normalised error back to a comparable numeric range


def _skipped(reason: str) -> LayerResult:
    """Return a clean 'skipped' LayerResult."""
    if _base_skipped_result is not None:
        return _base_skipped_result(LAYER_NAME, reason)
    return LayerResult(
        layer_name=LAYER_NAME,
        score=0.0,
        reliability="low",
        status="skipped",
        detail={"reason": reason},
        heatmap_png_b64=None,
    )


def _png_b64(array_u8: np.ndarray) -> str:
    """Encode a 2-D uint8 array as a base64 grayscale PNG string."""
    buf = io.BytesIO()
    Image.fromarray(array_u8, mode="L").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _to_rgb(image: Image.Image) -> Image.Image:
    """Convert to RGB, flattening any transparency onto white."""
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _block_means(error: np.ndarray) -> np.ndarray:
    """Mean error per BLOCK_SIZE x BLOCK_SIZE block (edges are cropped)."""
    h, w = error.shape
    bh, bw = h // BLOCK_SIZE, w // BLOCK_SIZE
    cropped = error[: bh * BLOCK_SIZE, : bw * BLOCK_SIZE]
    return cropped.reshape(bh, BLOCK_SIZE, bw, BLOCK_SIZE).mean(axis=(1, 3))


def _score_blocks(blocks: np.ndarray) -> tuple[float, dict[str, float]]:
    """Score how much the error is dominated by a few outlier regions.

    Combines (a) contrast between the high-error tail and the median with
    (b) a locality weight that rewards a small outlier fraction and
    penalizes uniformly elevated error, then (c) suppresses the result when
    absolute error is too small to matter.
    """
    flat = blocks.ravel()
    median = float(np.median(flat))
    p99 = float(np.percentile(flat, 99))
    mad = float(np.median(np.abs(flat - median)))
    robust_sigma = max(1.4826 * mad, 0.25)

    outlier_fraction = float(np.mean(flat > median + OUTLIER_SIGMAS * robust_sigma))

    contrast = max(0.0, (p99 - median) / (p99 + median + _EPS))
    rise = min(1.0, outlier_fraction / 0.005)
    fall = 1.0 if outlier_fraction <= 0.10 else max(0.0, (0.40 - outlier_fraction) / 0.30)
    locality = rise * fall
    magnitude = min(1.0, p99 / MIN_MEANINGFUL_BLOCK_ERROR)

    score = float(np.clip(contrast * locality * magnitude, 0.0, 1.0))
    stats = {
        "median_block_error": round(median, 4),
        "p99_block_error": round(p99, 4),
        "outlier_block_fraction": round(outlier_fraction, 5),
        "contrast": round(contrast, 4),
        "locality_weight": round(locality, 4),
    }
    return score, stats


class ELALayer:
    """Error Level Analysis layer implementing ``run(image) -> LayerResult``."""

    name: str = LAYER_NAME

    def __init__(self, quality: int = RESAVE_QUALITY) -> None:
        self.quality = quality

    def run(self, image: Image.Image) -> LayerResult:
        """Run ELA on ``image`` and return a LayerResult.

        The original file format is read from ``image.format``. If the
        pipeline has already converted/copied the image, ``format`` is
        ``None`` and the input is treated as non-JPEG (reliability "low").
        """
        original_format = image.format  # None if image was copied/converted
        try:
            rgb = _to_rgb(image)
            width, height = rgb.size
            if width < MIN_DIMENSION or height < MIN_DIMENSION:
                return _skipped("image_too_small_for_ela")

            buf = io.BytesIO()
            rgb.save(buf, format="JPEG", quality=self.quality)
            buf.seek(0)
            with Image.open(buf) as resaved_img:
                resaved = resaved_img.convert("RGB")
                diff = ImageChops.difference(rgb, resaved)

            # Per-pixel error: worst channel difference, 0-255.
            error = np.asarray(diff, dtype=np.float32).max(axis=2)
        except (OSError, ValueError, UnidentifiedImageError, MemoryError) as exc:
            return _skipped(f"image_not_processable: {type(exc).__name__}")

        blocks = _block_means(error)
        # Error is naturally high on edges/text and low on flat areas. Judge each
        # block's error relative to its own texture so ordinary detail is not
        # mistaken for editing.
        gray = np.asarray(rgb.convert("L"), dtype=np.float32)
        texture = _block_means(np.hypot(ndimage.sobel(gray, axis=0), ndimage.sobel(gray, axis=1)))
        blocks = blocks / (texture + TEXTURE_OFFSET) * TEXTURE_SCALE
        raw_score, stats = _score_blocks(blocks)

        is_jpeg = original_format == "JPEG"
        score = raw_score if is_jpeg else raw_score * NON_JPEG_SCORE_DAMPING
        reliability = "medium" if is_jpeg else "low"
        if blocks.size < MIN_BLOCKS_FOR_RELIABILITY:
            reliability = "low"

        # Amplified map for visibility: stretch so the 99.9th percentile
        # maps to 255, preserving relative differences across the image.
        scale_ref = max(float(np.percentile(error, 99.9)), 1.0)
        amplified = np.clip(error * (255.0 / scale_ref), 0, 255).astype(np.uint8)

        detail: dict[str, Any] = {
            "resave_quality": self.quality,
            "original_format": original_format,
            "source_is_jpeg": is_jpeg,
            "block_size": BLOCK_SIZE,
            "texture_normalised": True,
            "raw_score_before_damping": round(raw_score, 4),
            "amplification_reference": round(scale_ref, 3),
            "error_map_png_b64": _png_b64(amplified),
            "error_map_size": {"width": width, "height": height},
            **stats,
        }
        if not is_jpeg:
            detail["note"] = (
                "Input was not a JPEG (format=%r), so it was re-encoded as JPEG "
                "for analysis. ELA relies on prior JPEG compression history, so "
                "this result is much weaker than for a JPEG source; the score "
                "was damped and should be weighted accordingly." % (original_format,)
            )

        return LayerResult(
            layer_name=LAYER_NAME,
            score=float(np.clip(score, 0.0, 1.0)),
            reliability=reliability,
            status="ok",
            detail=detail,
            heatmap_png_b64=None,
        )

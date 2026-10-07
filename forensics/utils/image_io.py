"""forensics/utils/image_io.py

Load, validate and normalize uploaded image bytes for the analysis pipeline.

Normalization means: EXIF orientation applied, RGB mode, and (only for very
large images) downscaled to ``MAX_LONG_EDGE``. Images at or below that size
are left at native resolution, because resampling destroys the JPEG
quantization history that ELA depends on.

IMPORTANT: the returned image keeps the *original* container format in
``image.format`` (e.g. "JPEG", "PNG"). ``ELALayer`` reads that attribute to
decide whether the source was a JPEG, and Pillow normally drops it whenever
an image is converted or copied.
"""

from __future__ import annotations

import io
from typing import Final

from PIL import Image, ImageOps

__all__ = ["load_and_normalize"]

MAX_FILE_BYTES: Final[int] = 50 * 1024 * 1024  # 50 MB upload cap
MAX_PIXELS: Final[int] = 100_000_000  # 100 MP; rejected before decoding
MAX_LONG_EDGE: Final[int] = 4096  # larger images are downscaled to this
MIN_DIMENSION: Final[int] = 8


def load_and_normalize(image_bytes: bytes) -> Image.Image:
    """Decode, validate and normalize raw image bytes.

    Args:
        image_bytes: The raw bytes of an uploaded image file.

    Returns:
        An RGB ``PIL.Image.Image`` with EXIF orientation applied, at most
        ``MAX_LONG_EDGE`` pixels on its long edge, and with ``format`` set
        to the original file format.

    Raises:
        ValueError: If the bytes are empty, too large, not a decodable
            image, or exceed the pixel limit.
    """
    if not image_bytes:
        raise ValueError("Empty upload.")
    if len(image_bytes) > MAX_FILE_BYTES:
        raise ValueError(
            f"File too large ({len(image_bytes)} bytes; limit {MAX_FILE_BYTES})."
        )

    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            original_format = opened.format
            width, height = opened.size  # header only; nothing decoded yet

            if width * height > MAX_PIXELS:
                raise ValueError(
                    f"Image too large ({width}x{height}; limit {MAX_PIXELS} pixels)."
                )
            if min(width, height) < MIN_DIMENSION:
                raise ValueError(f"Image too small ({width}x{height}).")

            opened.load()
            image = ImageOps.exif_transpose(opened)
            image = _to_rgb(image)
    except ValueError:
        raise
    except (OSError, Image.DecompressionBombError) as exc:
        # UnidentifiedImageError is an OSError subclass.
        raise ValueError(f"Could not decode image: {exc}") from exc

    if max(image.size) > MAX_LONG_EDGE:
        image.thumbnail(
            (MAX_LONG_EDGE, MAX_LONG_EDGE),
            Image.Resampling.BILINEAR,
            reducing_gap=2.0,
        )

    # convert()/exif_transpose()/thumbnail() produce images with format=None.
    image.format = original_format
    return image


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
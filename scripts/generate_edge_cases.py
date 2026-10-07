"""scripts/generate_edge_cases.py

Generate edge-case images for stress-testing the forensics pipeline.

Source images are read from ``--source-dir`` (default ``data/source``). If that
folder has no images, a few synthetic "camera-like" JPEG photos are created
there first, so the script works with zero setup. Drop real photos into the
folder later and rerun to get more realistic variants.

Variants written to ``--output-dir`` (default ``data/edge_cases``), one set per
source image, with the source's filename stem appended:

    edge_case_png_from_jpeg_<stem>.png
    edge_case_whatsapp_compressed_<stem>.jpg
    edge_case_screenshot_<stem>.png
    edge_case_oversized_<stem>.jpg   (first source only; it is slow to make)

Usage:
    python scripts/generate_edge_cases.py
    python scripts/generate_edge_cases.py --source-dir my_photos --max-sources 2
"""

from __future__ import annotations

import argparse
import io
import logging
from pathlib import Path
from typing import Final

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger("generate_edge_cases")

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR: Final[Path] = REPO_ROOT / "data" / "source"
DEFAULT_OUTPUT_DIR: Final[Path] = REPO_ROOT / "data" / "edge_cases"

IMAGE_SUFFIXES: Final[frozenset[str]] = frozenset({".jpg", ".jpeg", ".png"})

# WhatsApp downsizes to roughly this long edge and re-encodes aggressively.
WHATSAPP_MAX_EDGE: Final[int] = 1600
WHATSAPP_QUALITY_PASSES: Final[tuple[int, ...]] = (70, 55, 45, 38, 35)

# Pillow's decompression-bomb *error* triggers at ~178 MP; stay well under it.
DEFAULT_OVERSIZED_LONG_EDGE: Final[int] = 8_000


# --------------------------------------------------------------------------
# Source loading / synthesis
# --------------------------------------------------------------------------
def find_source_images(source_dir: Path) -> list[Path]:
    """Return image files in ``source_dir``, sorted by name."""
    if not source_dir.is_dir():
        return []
    return sorted(
        p for p in source_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES
    )


def synthesize_photo(seed: int, size: tuple[int, int] = (1600, 1200)) -> Image.Image:
    """Create a photo-like RGB image: smooth scene plus sensor-style noise.

    This is NOT a real photograph, but it has the properties the pipeline
    cares about for these tests: continuous tones, soft edges, and
    per-pixel noise.

    Args:
        seed: RNG seed so output is reproducible.
        size: ``(width, height)`` of the image.

    Returns:
        An RGB ``PIL.Image``.
    """
    rng = np.random.default_rng(seed)
    width, height = size

    # Vertical gradient "sky to ground" with a random palette.
    top = rng.integers(90, 220, size=3).astype(np.float32)
    bottom = rng.integers(20, 160, size=3).astype(np.float32)
    ramp = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
    canvas = top * (1.0 - ramp) + bottom * ramp
    canvas = np.broadcast_to(canvas, (height, width, 3)).copy()

    base = Image.fromarray(canvas.clip(0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(base)
    for _ in range(14):
        x0 = int(rng.integers(0, width - 100))
        y0 = int(rng.integers(0, height - 100))
        x1 = x0 + int(rng.integers(80, width // 3))
        y1 = y0 + int(rng.integers(80, height // 3))
        color = tuple(int(c) for c in rng.integers(20, 235, size=3))
        draw.ellipse((x0, y0, x1, y1), fill=color)

    soft = base.filter(ImageFilter.GaussianBlur(radius=6))
    arr = np.asarray(soft, dtype=np.float32)
    arr += rng.normal(0.0, 4.0, size=arr.shape).astype(np.float32)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")


def ensure_sources(source_dir: Path, synthetic_count: int) -> list[Path]:
    """Return source images, synthesizing JPEG photos if the folder is empty."""
    sources = find_source_images(source_dir)
    if sources:
        return sources

    logger.warning(
        "No source images in %s - generating %d synthetic photo(s).",
        source_dir,
        synthetic_count,
    )
    source_dir.mkdir(parents=True, exist_ok=True)
    for index in range(synthetic_count):
        path = source_dir / f"synthetic_photo_{index + 1}.jpg"
        synthesize_photo(seed=index + 1).save(path, format="JPEG", quality=92)
    return find_source_images(source_dir)


def load_rgb(path: Path) -> Image.Image:
    """Load an image as RGB with pixel data fully read into memory."""
    with Image.open(path) as img:
        return img.convert("RGB")


# --------------------------------------------------------------------------
# Variant builders
# --------------------------------------------------------------------------
def make_png_from_jpeg(image: Image.Image, out_path: Path) -> None:
    """Save a lossless PNG whose pixels already carry JPEG artifacts.

    The image is round-tripped through JPEG first so it behaves like a real
    "photo saved/exported as PNG" file, which is what ELA should flag as
    low-reliability.
    """
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    with Image.open(buffer) as degraded:
        degraded.convert("RGB").save(out_path, format="PNG")


def make_whatsapp_compressed(image: Image.Image, out_path: Path) -> None:
    """Mimic messaging-app degradation: downscale, then re-encode repeatedly.

    No EXIF is written, matching what WhatsApp does to uploaded photos.
    """
    current = image.copy()
    current.thumbnail((WHATSAPP_MAX_EDGE, WHATSAPP_MAX_EDGE), Image.Resampling.LANCZOS)

    for quality in WHATSAPP_QUALITY_PASSES:
        buffer = io.BytesIO()
        current.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        with Image.open(buffer) as reloaded:
            current = reloaded.convert("RGB")

    current.save(out_path, format="JPEG", quality=WHATSAPP_QUALITY_PASSES[-1])


def make_screenshot(out_path: Path, size: tuple[int, int] = (1280, 720)) -> None:
    """Draw a flat-color, UI-style image with no noise and no EXIF."""
    width, height = size
    img = Image.new("RGB", size, (245, 246, 248))
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, 48), fill=(32, 36, 44))  # title bar
    draw.text((16, 16), "Settings - Account", fill=(255, 255, 255))
    draw.rectangle((0, 48, 220, height), fill=(232, 235, 240))  # sidebar
    for i, label in enumerate(("Profile", "Security", "Billing", "Help")):
        top = 72 + i * 44
        fill = (66, 133, 244) if i == 0 else (255, 255, 255)
        draw.rounded_rectangle((16, top, 204, top + 32), radius=6, fill=fill)
        draw.text((28, top + 10), label, fill=(20, 20, 20))

    draw.rounded_rectangle((260, 90, 1220, 220), radius=10, fill=(255, 255, 255))
    draw.text((284, 110), "Email address", fill=(60, 60, 60))
    draw.rectangle((284, 140, 760, 176), outline=(190, 190, 190), fill=(250, 250, 250))
    draw.rounded_rectangle((284, 250, 420, 290), radius=8, fill=(52, 168, 83))
    draw.text((322, 264), "Save", fill=(255, 255, 255))
    draw.rounded_rectangle((440, 250, 576, 290), radius=8, fill=(219, 68, 55))
    draw.text((476, 264), "Cancel", fill=(255, 255, 255))

    img.save(out_path, format="PNG")


def make_oversized(image: Image.Image, out_path: Path, long_edge: int) -> None:
    """Upscale ``image`` so its long edge is ``long_edge`` pixels."""
    width, height = image.size
    scale = long_edge / max(width, height)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    big = image.resize(new_size, Image.Resampling.BILINEAR)
    big.save(out_path, format="JPEG", quality=85)
    logger.info("Oversized image: %dx%d (%.1f MP)", *new_size, new_size[0] * new_size[1] / 1e6)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--max-sources", type=int, default=2, help="Use at most this many source images."
    )
    parser.add_argument(
        "--synthetic-count",
        type=int,
        default=2,
        help="How many synthetic photos to create if the source folder is empty.",
    )
    parser.add_argument(
        "--oversized-long-edge",
        type=int,
        default=DEFAULT_OVERSIZED_LONG_EDGE,
        help="Long edge in pixels for the oversized variant.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Generate all edge-case variants. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    sources = ensure_sources(args.source_dir, args.synthetic_count)[: args.max_sources]
    if not sources:
        logger.error("No usable source images found or created.")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for index, source in enumerate(sources):
        stem = source.stem
        logger.info("Processing source: %s", source.name)
        image = load_rgb(source)

        make_png_from_jpeg(image, args.output_dir / f"edge_case_png_from_jpeg_{stem}.png")
        make_whatsapp_compressed(
            image, args.output_dir / f"edge_case_whatsapp_compressed_{stem}.jpg"
        )
        make_screenshot(args.output_dir / f"edge_case_screenshot_{stem}.png")
        if index == 0:  # one oversized file is enough and is slow to make
            logger.info("Building oversized image (this can take a minute)...")
            make_oversized(
                image,
                args.output_dir / f"edge_case_oversized_{stem}.jpg",
                args.oversized_long_edge,
            )

    logger.info("Wrote edge cases to %s", args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

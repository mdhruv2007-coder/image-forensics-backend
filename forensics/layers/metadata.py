"""EXIF / metadata inspection layer for the image-tampering detection pipeline.

This layer looks at the metadata embedded in an image rather than its pixels.
It reads EXIF with Pillow (``Image.getexif()``) to decide whether metadata is
present at all, and uses ``exifread`` to extract the full set of tags that
are reported back to the UI as "what we found".

Suspicion heuristic
-------------------
The score starts at a low baseline (0.10) and is adjusted by independent
signals:

* **EXIF missing (+0.35)** -- the format normally carries EXIF (JPEG, TIFF,
  WebP) but no EXIF block is present. This suggests the file was re-saved or
  stripped. It is weak evidence on its own because messaging apps, social
  networks and screenshot tools strip EXIF legitimately, so it is reported
  with ``reliability="low"`` when it is the only signal.
* **Known editor in Software tag (+0.60)** -- the ``Software`` tag names a
  common image editor (see ``KNOWN_EDITOR_KEYWORDS``). Editing software is a
  strong signal that the pixels were touched after capture, so this is
  reported with ``reliability="high"``.
* **Original timestamp missing (+0.20)** -- camera identity (Make/Model) is
  present but ``DateTimeOriginal`` is absent, a pattern consistent with
  metadata stripping or selective rewriting.
* **Timestamp order inconsistent (+0.30)** -- ``DateTime`` (last modified)
  is earlier than ``DateTimeOriginal`` (capture), which is physically
  impossible for an untouched file.
* **Unparseable timestamp (+0.15)** -- a timestamp tag is present but does
  not match the EXIF ``YYYY:MM:DD HH:MM:SS`` format.
* **Consistent camera original (-0.05)** -- Make, Model and a parseable
  ``DateTimeOriginal`` are present, no editor is named and no timestamp flag
  fired. This lowers the score slightly.

The final score is clamped to [0, 1]. Metadata is trivially forgeable, so
the "consistent camera original" signal never drives the score far below
baseline and is reported with ``reliability="medium"``.

Skipped vs. suspicious
----------------------
A missing EXIF block is only treated as suspicious for formats that normally
carry EXIF (JPEG, TIFF, WebP). For other formats, such as PNG, where EXIF is
optional and commonly absent, or formats with no EXIF support at all, the
layer returns ``make_skipped_result`` so that "not applicable" is never
reported as "suspicious".
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any

import exifread
from PIL import Image

from forensics.layers.base import make_skipped_result
from forensics.schemas import LayerResult

__all__ = ["MetadataLayer", "LAYER_NAME"]

logger = logging.getLogger(__name__)

LAYER_NAME: str = "metadata"

# Formats that normally carry an EXIF block. A missing block here is suspicious.
EXIF_EXPECTED_FORMATS: frozenset[str] = frozenset({"JPEG", "TIFF", "WEBP"})

# Common image editors matched case-insensitively against the Software tag.
KNOWN_EDITOR_KEYWORDS: tuple[str, ...] = (
    "photoshop",
    "gimp",
    "lightroom",
    "paint.net",
    "affinity",
    "pixelmator",
    "snapseed",
    "photoscape",
    "corel",
    "canva",
)

EXIF_TIMESTAMP_FORMAT: str = "%Y:%m:%d %H:%M:%S"
EXIF_APP1_PREFIX: bytes = b"Exif\x00\x00"

# Pillow tag IDs (IFD0 unless noted).
_PIL_MAKE = 0x010F
_PIL_MODEL = 0x0110
_PIL_SOFTWARE = 0x0131
_PIL_DATETIME = 0x0132
_PIL_EXIF_IFD_POINTER = 0x8769  # sub-IFD holding capture-time tags
_PIL_DATETIME_ORIGINAL = 0x9003
_PIL_DATETIME_DIGITIZED = 0x9004

# exifread tag names mapped onto the normalized field names used below.
_EXIFREAD_NAME_MAP: dict[str, str] = {
    "Image Make": "Make",
    "Image Model": "Model",
    "Image Software": "Software",
    "Image DateTime": "DateTime",
    "EXIF DateTimeOriginal": "DateTimeOriginal",
    "EXIF DateTimeDigitized": "DateTimeDigitized",
}

_MAX_VALUE_LEN: int = 120


class MetadataLayer:
    """EXIF/metadata layer satisfying the ``Layer`` protocol from ``base.py``."""

    def run(self, image: Image.Image) -> LayerResult:
        """Inspect the image's EXIF metadata and return a ``LayerResult``.

        Args:
            image: The Pillow image to inspect. Its ``format`` attribute and
                ``info["exif"]`` raw bytes are used when available.

        Returns:
            A ``LayerResult`` with ``status="ok"`` when the metadata was
            analyzed, ``status="skipped"`` when the format carries no EXIF
            that could be judged, or ``status="failed"`` if parsing raised an
            unexpected error.
        """
        try:
            return self._run(image)
        except Exception as exc:  # noqa: BLE001 - layer must never crash the pipeline
            logger.exception("Metadata layer failed")
            return LayerResult(
                layer_name=LAYER_NAME,
                score=0.0,
                reliability="low",
                status="failed",
                detail={
                    "error": type(exc).__name__,
                    "message": f"Metadata layer failed: {exc}",
                },
                heatmap_png_b64=None,
            )

    def _run(self, image: Image.Image) -> LayerResult:
        fmt: str | None = image.format
        raw_exif: bytes | None = image.info.get("exif")
        pillow_exif = image.getexif()
        exif_present = bool(raw_exif) or bool(pillow_exif)

        if not exif_present and fmt not in EXIF_EXPECTED_FORMATS:
            return make_skipped_result(
                LAYER_NAME,
                f"format {fmt or 'unknown'} has no EXIF block and does not "
                "normally carry one",
            )

        fields, parser = self._extract_fields(raw_exif, image)
        flags, score, reliability = self._score(fields, exif_present, fmt)

        editor_match = self._match_editor(fields.get("Software"))
        detail: dict[str, Any] = {
            "format": fmt,
            "exif_present": exif_present,
            "parser": parser,
            "fields": fields,
            "flags": flags,
            "editor_match": editor_match,
            "message": self._summarize(flags, exif_present, fmt),
        }

        return LayerResult(
            layer_name=LAYER_NAME,
            score=score,
            reliability=reliability,
            status="ok",
            detail=detail,
            heatmap_png_b64=None,
        )

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_fields(
        self, raw_exif: bytes | None, image: Image.Image
    ) -> tuple[dict[str, Any], str]:
        """Return normalized EXIF fields and the name of the parser that produced them.

        ``exifread`` is preferred because it exposes the full tag set. Pillow
        is used when the raw block is unavailable or ``exifread`` fails.
        """
        if raw_exif:
            try:
                fields = self._fields_from_exifread(raw_exif)
                if fields:
                    return fields, "exifread"
            except Exception:  # noqa: BLE001 - fall back to Pillow below
                logger.warning("exifread failed; falling back to Pillow", exc_info=True)

        fields = self._fields_from_pillow(image)
        return fields, "pillow" if fields else "none"

    @staticmethod
    def _fields_from_exifread(raw: bytes) -> dict[str, Any]:
        """Parse a raw EXIF block with exifread and return all readable tags."""
        payload = raw[len(EXIF_APP1_PREFIX):] if raw.startswith(EXIF_APP1_PREFIX) else raw
        tags = exifread.process_file(io.BytesIO(payload), details=False)

        fields: dict[str, Any] = {}
        for tag_name, tag_value in tags.items():
            if "Thumbnail" in tag_name or "MakerNote" in tag_name:
                continue
            text = str(tag_value).strip()[:_MAX_VALUE_LEN]
            fields[tag_name] = text

        # Re-key the handful of fields the heuristics depend on under short names.
        for source, target in _EXIFREAD_NAME_MAP.items():
            if source in tags:
                fields[target] = str(tags[source]).strip()
        return fields

    @staticmethod
    def _fields_from_pillow(image: Image.Image) -> dict[str, Any]:
        """Read the key EXIF fields directly through ``Image.getexif()``."""
        exif = image.getexif()
        if not exif:
            return {}

        capture_ifd = exif.get_ifd(_PIL_EXIF_IFD_POINTER)
        raw_values: dict[str, Any] = {
            "Make": exif.get(_PIL_MAKE),
            "Model": exif.get(_PIL_MODEL),
            "Software": exif.get(_PIL_SOFTWARE),
            "DateTime": exif.get(_PIL_DATETIME),
            "DateTimeOriginal": capture_ifd.get(_PIL_DATETIME_ORIGINAL),
            "DateTimeDigitized": capture_ifd.get(_PIL_DATETIME_DIGITIZED),
        }
        return {
            key: str(value).strip()[:_MAX_VALUE_LEN]
            for key, value in raw_values.items()
            if value not in (None, "")
        }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score(
        self, fields: dict[str, Any], exif_present: bool, fmt: str | None
    ) -> tuple[list[str], float, str]:
        """Apply the suspicion heuristic and return ``(flags, score, reliability)``."""
        flags: list[str] = []
        score = 0.10
        reliability = "medium"

        if not exif_present and fmt in EXIF_EXPECTED_FORMATS:
            flags.append("exif_missing")
            score += 0.35

        editor = self._match_editor(fields.get("Software"))
        if editor is not None:
            flags.append(f"editor_software:{editor}")
            score += 0.60
            reliability = "high"

        has_camera_identity = bool(fields.get("Make") or fields.get("Model"))
        original = self._parse_timestamp(fields.get("DateTimeOriginal"))
        modified = self._parse_timestamp(fields.get("DateTime"))

        if has_camera_identity and not fields.get("DateTimeOriginal"):
            flags.append("original_timestamp_missing")
            score += 0.20

        for name in ("DateTimeOriginal", "DateTime"):
            value = fields.get(name)
            if value and self._parse_timestamp(value) is None:
                flags.append(f"unparseable_timestamp:{name}")
                score += 0.15

        if original is not None and modified is not None and modified < original:
            flags.append("timestamp_order_inconsistent")
            score += 0.30
            reliability = "medium"

        camera_consistent = (
            has_camera_identity and original is not None and editor is None
        )
        if camera_consistent and not any(
            f.startswith(("original_timestamp", "timestamp_order", "unparseable"))
            for f in flags
        ):
            flags.append("camera_signature_consistent")
            score -= 0.05
            if reliability != "high":
                reliability = "medium"

        if flags == ["exif_missing"]:
            reliability = "low"

        score = min(max(score, 0.0), 1.0)
        return flags, round(score, 3), reliability

    @staticmethod
    def _match_editor(software: Any) -> str | None:
        """Return the matched editor keyword if the Software tag names a known editor."""
        if not software:
            return None
        lowered = str(software).lower()
        for keyword in KNOWN_EDITOR_KEYWORDS:
            if keyword in lowered:
                return keyword
        return None

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """Parse an EXIF timestamp string, returning ``None`` if absent or malformed."""
        if not value:
            return None
        try:
            return datetime.strptime(str(value), EXIF_TIMESTAMP_FORMAT)
        except ValueError:
            return None

    @staticmethod
    def _summarize(flags: list[str], exif_present: bool, fmt: str | None) -> str:
        """Build a short human-readable summary for the UI."""
        if not exif_present:
            return f"No EXIF metadata found in this {fmt or 'image'} file."
        if not flags or flags == ["camera_signature_consistent"]:
            return "EXIF metadata looks consistent with an unedited camera original."
        return "EXIF metadata shows signs of editing or stripping: " + ", ".join(flags) + "."

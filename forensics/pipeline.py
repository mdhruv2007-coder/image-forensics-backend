
"""forensics/pipeline.py

End-to-end analysis pipeline: raw image bytes in, ``AnalysisResult`` out.

Stages:
    1. Load, validate and normalize the image via ``image_io``.
    2. Run every detection layer. A layer that raises is converted into a
       ``failed`` LayerResult so one broken layer cannot take down the rest.
    3. Fuse the layer scores and classify the fused score into a verdict.
    4. Assemble the ``AnalysisResult`` returned by the API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Final

from PIL import Image

from forensics.fusion import fuse
from forensics.layers.ai_detector import AIDetectorLayer
from forensics.layers.base import Layer, make_skipped_result
from forensics.layers.copy_move import CopyMoveLayer
from forensics.layers.ela import ELALayer
from forensics.layers.noise_residual import NoiseResidualLayer
from forensics.schemas import AnalysisResult, CoordinateSpace, LayerResult
from forensics.utils.image_io import load_and_normalize
from forensics.verdicts import classify

__all__ = ["InvalidImageError", "analyze"]

logger = logging.getLogger(__name__)

# (expected layer_name, layer instance). The name must match the layer_name
# the layer writes into its LayerResult, and the key in fusion_weights.yaml.
_LAYERS: Final[tuple[tuple[str, Layer], ...]] = (
    ("ai_generated_classifier", AIDetectorLayer()),
    ("ela", ELALayer()),
    ("noise_residual", NoiseResidualLayer()),
    ("copy_move", CopyMoveLayer()),
)

_DISPLAY_NAMES: Final[dict[str, str]] = {
    "ai_generated_classifier": "AI-generated classifier",
    "ela": "Error level analysis",
    "noise_residual": "Noise residual analysis",
    "copy_move": "Copy-move detection",
}


class InvalidImageError(ValueError):
    """Raised when the uploaded bytes cannot be decoded as a usable image."""


def analyze(image_bytes: bytes) -> AnalysisResult:
    """Run the full forensic analysis on raw uploaded image bytes.

    Args:
        image_bytes: The raw bytes of the uploaded image file.

    Returns:
        A complete ``AnalysisResult``. ``coordinate_space`` reflects the
        normalized image dimensions, and ``offline_mode`` is True when any
        layer was skipped.

    Raises:
        InvalidImageError: If the bytes cannot be decoded as an image.
        ValueError: If no detection layer completed, so no score can be fused.
    """
    try:
        image = load_and_normalize(image_bytes)
    except (OSError, ValueError) as exc:
        raise InvalidImageError(str(exc)) from exc

    layer_results = [_run_layer(name, layer, image) for name, layer in _LAYERS]
    tamper_score = fuse(layer_results)
    verdict = classify(tamper_score)
    width, height = image.size

    return AnalysisResult(
        verdict=verdict,
        tamper_score=tamper_score,
        per_layer=layer_results,
        explanation=_build_explanation(layer_results),
        metadata={},
        coordinate_space=CoordinateSpace(width=width, height=height),
        offline_mode=any(result.status == "skipped" for result in layer_results),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _run_layer(name: str, layer: Layer, image: Image.Image) -> LayerResult:
    """Run one detection layer, converting any exception into a failed result.

    Args:
        name: The expected layer name, used if the layer fails.
        layer: The detection layer to run.
        image: The normalized image to analyze.

    Returns:
        The layer's own ``LayerResult``, or a ``failed`` result if it raised.
    """
    try:
        return layer.run(image)
    except Exception:  # noqa: BLE001 - faults are isolated per layer by design
        logger.exception("Detection layer '%s' raised an exception", name)
        return _failed_result(name)


def _failed_result(layer_name: str) -> LayerResult:
    """Build a ``failed`` LayerResult for a layer that raised an exception.

    The exception text is logged server-side and deliberately kept out of
    the result, so internal details are not exposed to API clients.

    Args:
        layer_name: Identifier of the layer that failed.

    Returns:
        A ``LayerResult`` with ``status="failed"`` and zero score.
    """
    failed = make_skipped_result(layer_name, reason="internal error")
    return failed.model_copy(
        update={
            "status": "failed",
            "detail": {
                "reason": "internal_error",
                "message": f"Layer '{layer_name}' failed during analysis.",
            },
        }
    )


def _build_explanation(layer_results: list[LayerResult]) -> list[str]:
    """Produce plain-English lines describing each layer's outcome.

    This is a minimal stand-in for the explainability module.

    Args:
        layer_results: Results from every detection layer.

    Returns:
        One explanation line per layer.
    """
    lines: list[str] = []
    for result in layer_results:
        label = _DISPLAY_NAMES.get(result.layer_name, result.layer_name)
        if result.status == "ok":
            lines.append(
                f"{label} scored {result.score:.2f} with {result.reliability} reliability."
            )
        else:
            lines.append(str(result.detail.get("message", f"{label} did not complete.")))
    return lines
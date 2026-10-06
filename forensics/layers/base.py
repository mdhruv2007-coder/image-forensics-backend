"""Protocol and shared helpers for all forensics detection layers.

Every layer module (ELA, noise residual, copy-move, AI-classifier) exposes
an object satisfying the ``Layer`` protocol. Layers that cannot run should
return ``make_skipped_result(...)`` rather than inventing their own shape.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PIL import Image

from forensics.schemas import LayerResult

__all__ = ["Layer", "make_skipped_result"]


@runtime_checkable
class Layer(Protocol):
    """Interface implemented by every detection layer."""

    def run(self, image: Image.Image) -> LayerResult:
        """Analyze ``image`` and return this layer's result."""
        ...


def make_skipped_result(layer_name: str, reason: str) -> LayerResult:
    """Build a consistent ``LayerResult`` for a layer that did not run.

    Args:
        layer_name: Identifier of the layer, e.g. ``"ai_generated_classifier"``.
        reason: Human-readable explanation, e.g. ``"no internet connection"``.

    Returns:
        A ``LayerResult`` with ``status="skipped"``, zero score, low
        reliability, and a ``detail`` dict containing both the raw reason
        and a readable message for the UI.
    """
    return LayerResult(
        layer_name=layer_name,
        score=0.0,
        reliability="low",
        status="skipped",
        detail={
            "reason": reason,
            "message": f"Layer '{layer_name}' was skipped: {reason}.",
        },
        heatmap_png_b64=None,
    )
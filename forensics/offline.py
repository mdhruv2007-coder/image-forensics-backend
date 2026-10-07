"""forensics/offline.py

Offline-mode helpers. The term "offline_mode" in this project means two
distinct things, and it is important not to conflate them:

(a) Python level (implemented here): ``settings.OFFLINE_MODE`` tells the
    code to skip any detection layer that needs a downloaded ML model at
    runtime. ``should_skip_layer`` answers that question for a given
    layer. Classical layers (ELA, noise residual, copy-move) always run,
    since they need no network or model download at any point.

(b) Operational (NOT implemented here): the whole backend and the separate
    frontend can be run with zero internet access by starting both services
    on localhost. This is a fallback for when the deployed Render/Vercel
    URLs are unreachable. It requires no special code. Running both
    services locally is sufficient, and this module does not handle it.

Integration note: ``pipeline.analyze`` does not yet call
``should_skip_layer``. Wiring it in (skipping a layer before ``_run_layer``
and recording it as ``skipped``) is a separate change to ``pipeline.py``.
"""

from __future__ import annotations

from typing import Final

from app.core.config import settings

__all__ = ["MODEL_BACKED_LAYERS", "CLASSICAL_LAYERS", "should_skip_layer"]

# Layer names must match the names used in forensics/pipeline.py and in
# fusion_weights.yaml.
MODEL_BACKED_LAYERS: Final[frozenset[str]] = frozenset({"ai_generated_classifier"})

CLASSICAL_LAYERS: Final[frozenset[str]] = frozenset(
    {"ela", "noise_residual", "copy_move"}
)


def should_skip_layer(layer_name: str) -> bool:
    """Return True if a layer should be skipped in the current mode.

    Only model-backed layers are skipped, and only when
    ``settings.OFFLINE_MODE`` is enabled. Classical layers always run.

    Args:
        layer_name: The layer identifier, as used in ``pipeline.py``.

    Returns:
        True if the layer should be skipped, False if it should run.

    Raises:
        ValueError: If ``layer_name`` is not a known layer. This surfaces
            typos instead of silently running or skipping a layer.
    """
    if layer_name in MODEL_BACKED_LAYERS:
        return bool(settings.OFFLINE_MODE)
    if layer_name in CLASSICAL_LAYERS:
        return False
    raise ValueError(f"Unknown detection layer: {layer_name!r}")
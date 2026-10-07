"""forensics/fusion.py

Combines per-layer suspicion scores into a single fused tamper score.

Weights are read from YAML on every call so they can be tuned without a
code change. Only layers with ``status == "ok"`` contribute. Their weights
are re-normalized among themselves, so a skipped or failed layer does not
silently pull the score toward zero.

This module is pure apart from reading the weights file.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from forensics.schemas import LayerResult

__all__ = ["DEFAULT_WEIGHTS_PATH", "fuse"]

DEFAULT_WEIGHTS_PATH: str = "config/fusion_weights.yaml"

_SUM_TOLERANCE: float = 1e-6


def fuse(
    layer_results: list[LayerResult],
    weights_path: str = DEFAULT_WEIGHTS_PATH,
) -> float:
    """Compute the weighted average suspicion score across completed layers.

    Args:
        layer_results: Results from every detection layer for one image.
        weights_path: Path to a YAML mapping of layer name to weight.

    Returns:
        The fused tamper score in the range 0-1.

    Raises:
        ValueError: If no layer completed with ``status == "ok"``, if a
            completed layer has no configured weight, or if the configured
            weights for completed layers total zero.
        OSError: If the weights file cannot be read.
    """
    weights = _load_weights(weights_path)

    completed = [result for result in layer_results if result.status == "ok"]
    if not completed:
        raise ValueError("Cannot fuse scores: no detection layer completed successfully.")

    unknown = sorted({result.layer_name for result in completed} - set(weights))
    if unknown:
        raise ValueError(
            f"No fusion weight configured for layer(s): {', '.join(unknown)}."
        )

    total_weight = sum(weights[result.layer_name] for result in completed)
    if total_weight <= 0.0:
        raise ValueError("Completed layers have zero total fusion weight.")

    weighted_sum = sum(weights[result.layer_name] * result.score for result in completed)
    return weighted_sum / total_weight


def _load_weights(weights_path: str) -> dict[str, float]:
    """Load and validate the layer weight mapping from a YAML file.

    Args:
        weights_path: Path to the YAML weights file.

    Returns:
        A dict mapping layer name to a non-negative float weight.

    Raises:
        ValueError: If the file is not a non-empty mapping, contains a
            negative weight, or the weights do not sum to 1.0.
    """
    with Path(weights_path).open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{weights_path} must contain a non-empty mapping of layer name to weight.")

    weights = {str(name): float(value) for name, value in raw.items()}

    if any(value < 0.0 for value in weights.values()):
        raise ValueError(f"{weights_path} contains a negative weight.")

    if abs(sum(weights.values()) - 1.0) > _SUM_TOLERANCE:
        raise ValueError(f"Fusion weights in {weights_path} must sum to 1.0.")

    return weights

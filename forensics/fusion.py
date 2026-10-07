"""Weighted fusion of per-layer tamper scores into one 0-1 score.

Weights are loaded from a YAML file on every call so they can be tuned
without code changes. Only layers with ``status == "ok"`` contribute;
skipped or failed layers are excluded and the remaining weights are
renormalized, so a missing layer does not drag the score toward zero.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

import yaml

from forensics.schemas import LayerResult

__all__ = ["fuse", "load_weights"]

_WEIGHT_SUM_TOLERANCE = 1e-6


def load_weights(weights_path: str) -> dict[str, float]:
    """Load and validate per-layer fusion weights from a YAML file.

    Args:
        weights_path: Path to a YAML mapping of layer name to weight.

    Returns:
        Mapping of layer name to non-negative float weight.

    Raises:
        ValueError: If the file is not a mapping, a weight is not a
            non-negative number, or the weights do not sum to 1.0.
        OSError: If the file cannot be read.
    """
    with Path(weights_path).open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"{weights_path}: expected a mapping of layer weights")

    weights: dict[str, float] = {}
    for name, value in raw.items():
        if not isinstance(name, str):
            raise ValueError(f"{weights_path}: layer name {name!r} is not a string")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{weights_path}: weight for {name!r} is not a number")
        weight = float(value)
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError(
                f"{weights_path}: weight for {name!r} must be finite and >= 0"
            )
        weights[name] = weight

    total = sum(weights.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"{weights_path}: weights must sum to 1.0, got {total:.6f}"
        )
    return weights


def fuse(
    layer_results: Sequence[LayerResult],
    weights_path: str = "config/fusion_weights.yaml",
) -> float:
    """Fuse per-layer scores into a single tamper score in [0, 1].

    Only results with ``status == "ok"`` are used. Their weights are
    renormalized to sum to 1 before averaging, so skipped or failed
    layers are excluded rather than counted as zero.

    Args:
        layer_results: Results from every layer that ran, including
            skipped and failed ones.
        weights_path: Path to the fusion weights YAML file.

    Returns:
        The weighted average of the ``ok`` layer scores, clamped to [0, 1].

    Raises:
        ValueError: If no ``ok`` results exist, an ``ok`` layer has no
            configured weight, a layer name appears more than once among
            the ``ok`` results, or the weights are invalid.
    """
    weights = load_weights(weights_path)

    usable: list[LayerResult] = [r for r in layer_results if r.status == "ok"]
    if not usable:
        raise ValueError("no layer results with status 'ok' to fuse")

    seen: set[str] = set()
    for result in usable:
        if result.layer_name not in weights:
            raise ValueError(
                f"layer {result.layer_name!r} has no weight in {weights_path}"
            )
        if result.layer_name in seen:
            raise ValueError(f"duplicate ok result for layer {result.layer_name!r}")
        seen.add(result.layer_name)

    total_weight = sum(weights[r.layer_name] for r in usable)
    if total_weight <= 0.0:
        raise ValueError("configured weights of the ok layers sum to zero")

    fused = sum(weights[r.layer_name] * r.score for r in usable) / total_weight
    return min(max(fused, 0.0), 1.0)

"""Map a fused tamper score to a verdict label using configured thresholds.

Thresholds are loaded from YAML on every call so they can be tuned
without code changes. Boundaries are lower-inclusive: a score exactly
equal to a bound falls into the higher-suspicion class.
"""

from __future__ import annotations

from pathlib import Path

import yaml

__all__ = ["classify", "load_thresholds"]

_AUTHENTIC_KEY = "authentic_upper_bound"
_TAMPERED_KEY = "likely_tampered_lower_bound"


def load_thresholds(thresholds_path: str) -> tuple[float, float]:
    """Load and validate the verdict thresholds from a YAML file.

    Args:
        thresholds_path: Path to a YAML mapping containing
            ``authentic_upper_bound`` and ``likely_tampered_lower_bound``.

    Returns:
        A tuple ``(authentic_upper_bound, likely_tampered_lower_bound)``.

    Raises:
        ValueError: If a key is missing, a value is not a number, or the
            values are not ordered as 0 <= authentic <= tampered <= 1.
        OSError: If the file cannot be read.
    """
    with Path(thresholds_path).open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"{thresholds_path}: expected a mapping of thresholds")

    values: list[float] = []
    for key in (_AUTHENTIC_KEY, _TAMPERED_KEY):
        if key not in raw:
            raise ValueError(f"{thresholds_path}: missing key {key!r}")
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{thresholds_path}: {key!r} is not a number")
        values.append(float(value))

    authentic, tampered = values
    if not 0.0 <= authentic <= tampered <= 1.0:
        raise ValueError(
            f"{thresholds_path}: require 0 <= {_AUTHENTIC_KEY} <= "
            f"{_TAMPERED_KEY} <= 1, got {authentic} and {tampered}"
        )
    return authentic, tampered


def classify(
    tamper_score: float,
    thresholds_path: str = "config/thresholds.yaml",
) -> str:
    """Return the verdict label for a fused tamper score.

    Args:
        tamper_score: Fused score in [0, 1].
        thresholds_path: Path to the thresholds YAML file.

    Returns:
        ``"authentic"``, ``"suspicious"``, or ``"likely_tampered"``.

    Raises:
        ValueError: If ``tamper_score`` is not a number in [0, 1] (NaN
            is rejected), or the thresholds file is invalid.
    """
    if not 0.0 <= tamper_score <= 1.0:
        raise ValueError(f"tamper_score must be in [0, 1], got {tamper_score!r}")

    authentic_upper, tampered_lower = load_thresholds(thresholds_path)

    if tamper_score < authentic_upper:
        return "authentic"
    if tamper_score < tampered_lower:
        return "suspicious"
    return "likely_tampered"

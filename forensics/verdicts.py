"""forensics/verdicts.py

Maps a fused tamper score onto a human-readable verdict label.

Thresholds are read from YAML on every call so they can be tuned without a
code change. This module is pure apart from reading the thresholds file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

__all__ = ["DEFAULT_THRESHOLDS_PATH", "Verdict", "classify"]

Verdict = Literal["authentic", "suspicious", "likely_tampered"]

DEFAULT_THRESHOLDS_PATH: str = "config/thresholds.yaml"

_AUTHENTIC_KEY: str = "authentic_suspicious"
_TAMPERED_KEY: str = "suspicious_likely_tampered"


def classify(
    tamper_score: float,
    thresholds_path: str = DEFAULT_THRESHOLDS_PATH,
) -> Verdict:
    """Return the verdict label for a fused tamper score.

    Args:
        tamper_score: Fused suspicion score in the range 0-1.
        thresholds_path: Path to the YAML file holding the two thresholds.

    Returns:
        ``"authentic"`` if the score is below the first threshold,
        ``"suspicious"`` if it is at or above the first threshold but below
        the second, and ``"likely_tampered"`` if it is at or above the second.

    Raises:
        ValueError: If ``tamper_score`` is outside 0-1, or the thresholds
            file is malformed.
        OSError: If the thresholds file cannot be read.
    """
    if not 0.0 <= tamper_score <= 1.0:
        raise ValueError(f"tamper_score must be in [0, 1], got {tamper_score!r}.")

    authentic_upper, tampered_lower = _load_thresholds(thresholds_path)

    if tamper_score < authentic_upper:
        return "authentic"
    if tamper_score < tampered_lower:
        return "suspicious"
    return "likely_tampered"


def _load_thresholds(thresholds_path: str) -> tuple[float, float]:
    """Load and validate the two verdict thresholds from a YAML file.

    Args:
        thresholds_path: Path to the YAML thresholds file.

    Returns:
        A ``(authentic_suspicious, suspicious_likely_tampered)`` tuple.

    Raises:
        ValueError: If a key is missing, a value is not a number, or the
            values do not satisfy ``0 <= low < high <= 1``.
    """
    with Path(thresholds_path).open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise ValueError(f"{thresholds_path} must contain a mapping of thresholds.")

    try:
        low = float(raw[_AUTHENTIC_KEY])
        high = float(raw[_TAMPERED_KEY])
    except KeyError as exc:
        raise ValueError(f"{thresholds_path} is missing required key {exc.args[0]!r}.") from exc

    if not 0.0 <= low < high <= 1.0:
        raise ValueError(
            f"Thresholds must satisfy 0 <= {_AUTHENTIC_KEY} < {_TAMPERED_KEY} <= 1, "
            f"got {low} and {high}."
        )

    return low, high

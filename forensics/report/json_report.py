"""
forensics/report/json_report.py

Wraps an AnalysisResult in a human-readable report dict. The result is
nested under the "result" key, and a disclaimer and a UTC timestamp are
added alongside it. This module does no I/O and has no side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from forensics.schemas import AnalysisResult

__all__ = ["DISCLAIMER", "format_report"]

DISCLAIMER: str = (
    "Automated forensic analysis, not a legal determination. "
    "Results should be reviewed by a qualified examiner before use."
)


def format_report(result: AnalysisResult) -> dict[str, Any]:
    """Return a report dict containing the analysis result and metadata.

    The input is assumed to be a validated AnalysisResult, so no further
    validation happens here. Serialization errors are not caught and
    propagate to the caller.
    """
    return {
        "disclaimer": DISCLAIMER,
        "report_generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "result": result.model_dump(mode="json"),
    }
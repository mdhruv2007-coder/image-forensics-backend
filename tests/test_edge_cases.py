"""tests/test_edge_cases.py

Run ``forensics.pipeline.analyze`` against every file in ``data/edge_cases/``.

Generate the inputs first:
    python scripts/generate_edge_cases.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from forensics.pipeline import InvalidImageError, analyze
from forensics.schemas import AnalysisResult, LayerResult

EDGE_CASE_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "data" / "edge_cases"
VALID_STATUSES: Final[frozenset[str]] = frozenset({"ok", "skipped", "failed"})


def _edge_case_files() -> list[Path]:
    """All generated edge-case files, sorted for stable test IDs."""
    if not EDGE_CASE_DIR.is_dir():
        return []
    return sorted(p for p in EDGE_CASE_DIR.iterdir() if p.is_file())


def _png_from_jpeg_files() -> list[Path]:
    return [p for p in _edge_case_files() if p.name.startswith("edge_case_png_from_jpeg")]


def _ela_result(result: AnalysisResult) -> LayerResult:
    return next(r for r in result.per_layer if r.layer_name == "ela")


@pytest.fixture(scope="module", autouse=True)
def _require_edge_cases() -> None:
    if not _edge_case_files():
        pytest.skip(
            "No files in data/edge_cases/ - run scripts/generate_edge_cases.py first."
        )


@pytest.mark.parametrize("path", _edge_case_files(), ids=lambda p: p.name)
def test_analyze_does_not_crash(path: Path) -> None:
    """analyze() returns a result (or a clean InvalidImageError), never crashes."""
    try:
        result = analyze(path.read_bytes())
    except InvalidImageError:
        # A deliberate, documented rejection (e.g. size limits) is not a crash.
        pytest.xfail(f"{path.name} was rejected with InvalidImageError")
    assert isinstance(result, AnalysisResult)


@pytest.mark.parametrize("path", _edge_case_files(), ids=lambda p: p.name)
def test_every_layer_reports_a_known_status(path: Path) -> None:
    """Each layer result carries a recognised status value."""
    try:
        result = analyze(path.read_bytes())
    except InvalidImageError:
        pytest.skip(f"{path.name} rejected before layers ran")
    statuses = {r.status for r in result.per_layer}
    assert statuses <= VALID_STATUSES


@pytest.mark.parametrize("path", _png_from_jpeg_files(), ids=lambda p: p.name)
def test_png_from_jpeg_ela_is_low_reliability(path: Path) -> None:
    """A PNG that began life as a JPEG must get low-reliability ELA."""
    result = analyze(path.read_bytes())
    assert _ela_result(result).reliability == "low"


@pytest.mark.parametrize("path", _png_from_jpeg_files(), ids=lambda p: p.name)
def test_png_from_jpeg_ela_layer_did_not_fail(path: Path) -> None:
    """The ELA layer should complete (ok) rather than fail on PNG input."""
    result = analyze(path.read_bytes())
    assert _ela_result(result).status != "failed"

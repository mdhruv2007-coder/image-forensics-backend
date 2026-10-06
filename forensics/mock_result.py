"""Mock ``AnalysisResult`` payloads for frontend development.
 
Run as a script to dump every scenario as one JSON object:
 
    python -m forensics.mock_result > mock_data.json
"""
 
from __future__ import annotations
 
import json
from typing import Any, Callable
 
from forensics.schemas import AnalysisResult, CoordinateSpace, LayerResult
 
__all__ = ["SCENARIOS", "get_mock_result"]
 
# 1x1 transparent PNG, valid but placeholder-sized.
PLACEHOLDER_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
GENERATED_AT = "2026-10-02T17:45:12Z"
COORDS = CoordinateSpace(width=1024, height=768)
 
 
def _verdict_for(score: float) -> str:
    """Map a fused tamper score to a verdict label."""
    if score >= 0.7:
        return "likely_tampered"
    if score >= 0.4:
        return "suspicious"
    return "authentic"
 
 
def _tampered() -> AnalysisResult:
    """Strong evidence across several layers, including a copy-move match."""
    per_layer = [
        LayerResult(
            layer_name="ela",
            score=0.74,
            reliability="medium",
            status="ok",
            detail={"jpeg_quality_estimate": 85, "hotspot_count": 3},
            heatmap_png_b64=PLACEHOLDER_PNG_B64,
        ),
        LayerResult(
            layer_name="noise_residual",
            score=0.65,
            reliability="medium",
            status="ok",
            detail={"residual_variance": 0.0021},
            heatmap_png_b64=PLACEHOLDER_PNG_B64,
        ),
        LayerResult(
            layer_name="copy_move",
            score=0.91,
            reliability="high",
            status="ok",
            detail={
                "match_regions": [
                    {"x1": 120, "y1": 340, "x2": 410, "y2": 560},
                    {"x1": 900, "y1": 340, "x2": 1190, "y2": 560},
                ],
                "match_count": 1,
            },
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="ai_generated_classifier",
            score=0.58,
            reliability="low",
            status="ok",
            detail={"model": "local-v1", "top_label": "possibly_synthetic"},
            heatmap_png_b64=None,
        ),
    ]
    score = 0.87
    return AnalysisResult(
        verdict=_verdict_for(score),
        tamper_score=score,
        per_layer=per_layer,
        explanation=[
            "A duplicated region was detected in the upper-right quadrant of the image.",
            "Error level analysis shows inconsistent compression artifacts around the duplicated region.",
            "Noise residual variance differs between the two halves of the image.",
        ],
        metadata={
            "exif_present": True,
            "software_tag": "Adobe Photoshop 25.0",
            "original_datetime": "2024-03-11T14:22:03",
            "gps_present": False,
        },
        coordinate_space=COORDS,
        offline_mode=True,
        generated_at=GENERATED_AT,
    )
 
 
def _authentic() -> AnalysisResult:
    """Clean signals across all layers; low-scoring but not all high-reliability."""
    per_layer = [
        LayerResult(
            layer_name="ela",
            score=0.08,
            reliability="high",
            status="ok",
            detail={"jpeg_quality_estimate": 92, "hotspot_count": 0},
            heatmap_png_b64=PLACEHOLDER_PNG_B64,
        ),
        LayerResult(
            layer_name="noise_residual",
            score=0.11,
            reliability="medium",
            status="ok",
            detail={"residual_variance": 0.0009},
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="copy_move",
            score=0.03,
            reliability="high",
            status="ok",
            detail={"match_regions": [], "match_count": 0},
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="ai_generated_classifier",
            score=0.22,
            reliability="low",
            status="ok",
            detail={"model": "local-v1", "top_label": "likely_camera"},
            heatmap_png_b64=None,
        ),
    ]
    score = 0.12
    return AnalysisResult(
        verdict=_verdict_for(score),
        tamper_score=score,
        per_layer=per_layer,
        explanation=[
            "No duplicated regions were found.",
            "Compression artifacts are uniform across the image.",
        ],
        metadata={
            "exif_present": True,
            "camera_make": "Apple",
            "camera_model": "iPhone 15",
            "original_datetime": "2025-07-19T09:05:44",
            "gps_present": False,
        },
        coordinate_space=COORDS,
        offline_mode=False,
        generated_at=GENERATED_AT,
    )
 
 
def _degraded() -> AnalysisResult:
    """One layer skipped due to no internet; verdict still computed from the rest."""
    per_layer = [
        LayerResult(
            layer_name="ela",
            score=0.61,
            reliability="medium",
            status="ok",
            detail={"jpeg_quality_estimate": 78, "hotspot_count": 1},
            heatmap_png_b64=PLACEHOLDER_PNG_B64,
        ),
        LayerResult(
            layer_name="noise_residual",
            score=0.55,
            reliability="medium",
            status="ok",
            detail={"residual_variance": 0.0015},
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="copy_move",
            score=0.44,
            reliability="medium",
            status="ok",
            detail={"match_regions": [], "match_count": 0},
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="ai_generated_classifier",
            score=0.0,
            reliability="low",
            status="skipped",
            detail={
                "reason": "no_internet_fallback_model_unavailable",
                "message": "Layer 'ai_generated_classifier' was skipped: no internet connection.",
            },
            heatmap_png_b64=None,
        ),
    ]
    score = 0.58
    return AnalysisResult(
        verdict=_verdict_for(score),
        tamper_score=score,
        per_layer=per_layer,
        explanation=[
            "Error level analysis shows mild inconsistencies in the lower-left region.",
            "The AI-generated-image classifier was skipped because no internet connection was available.",
            "The verdict is based on the remaining three layers and may be less certain.",
        ],
        metadata={
            "exif_present": False,
            "gps_present": False,
        },
        coordinate_space=COORDS,
        offline_mode=True,
        generated_at=GENERATED_AT,
    )
 
 
def _partial_failure() -> AnalysisResult:
    """One layer errored out; UI must handle status='failed' distinctly from skipped."""
    per_layer = [
        LayerResult(
            layer_name="ela",
            score=0.19,
            reliability="medium",
            status="ok",
            detail={"jpeg_quality_estimate": 90, "hotspot_count": 0},
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="noise_residual",
            score=0.27,
            reliability="medium",
            status="ok",
            detail={"residual_variance": 0.0012},
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="copy_move",
            score=0.0,
            reliability="low",
            status="failed",
            detail={"error": "pipeline_failure", "message": "Feature matching ran out of memory."},
            heatmap_png_b64=None,
        ),
        LayerResult(
            layer_name="ai_generated_classifier",
            score=0.31,
            reliability="low",
            status="ok",
            detail={"model": "local-v1", "top_label": "likely_camera"},
            heatmap_png_b64=None,
        ),
    ]
    score = 0.24
    return AnalysisResult(
        verdict=_verdict_for(score),
        tamper_score=score,
        per_layer=per_layer,
        explanation=[
            "No strong tampering signals were found in the layers that completed.",
            "The copy-move layer failed, so duplicated regions could not be ruled out.",
        ],
        metadata={"exif_present": True, "camera_make": "Canon", "gps_present": True},
        coordinate_space=COORDS,
        offline_mode=False,
        generated_at=GENERATED_AT,
    )
 
 
SCENARIOS: dict[str, Callable[[], AnalysisResult]] = {
    "tampered": _tampered,
    "authentic": _authentic,
    "degraded": _degraded,
    "partial_failure": _partial_failure,
}
 
 
def get_mock_result(scenario: str = "tampered") -> AnalysisResult:
    """Return a mock ``AnalysisResult`` for the named scenario.
 
    Args:
        scenario: One of ``"tampered"``, ``"authentic"``, ``"degraded"``,
            or ``"partial_failure"``.
 
    Raises:
        ValueError: If ``scenario`` is not a known scenario name.
    """
    try:
        builder = SCENARIOS[scenario]
    except KeyError as exc:
        valid = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"Unknown scenario {scenario!r}; expected one of: {valid}") from exc
    return builder()
 
 
def _dump_all() -> dict[str, Any]:
    """Serialize every scenario to a JSON-compatible dict."""
    return {name: get_mock_result(name).model_dump(mode="json") for name in SCENARIOS}
 
 
if __name__ == "__main__":
    print(json.dumps(_dump_all(), indent=2))
 
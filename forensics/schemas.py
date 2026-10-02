"""
forensics/schemas.py
 
Single source of truth for the API data contracts used by the
image-tampering-detection backend. This module is pure Python with no
FastAPI (or any other project) imports, so it can be imported by any
detection layer, the fusion function, or external tooling without
pulling in the web framework.
 
Pydantic v2 syntax is used throughout (ConfigDict / Field, no v1-style
``class Config``).
 
Note on requests: there is no ``AnalyzeRequest`` model in this file.
The analyze endpoint accepts ``multipart/form-data`` with a single
file field named ``"image"`` — not a JSON body — so there is no
request schema to define beyond this comment. FastAPI's ``UploadFile``
parameter type covers that directly at the route level.
"""
 
from __future__ import annotations
 
from typing import Any, Literal
 
from pydantic import BaseModel, ConfigDict, Field
 
__all__ = [
    "LayerResult",
    "AnalysisResult",
    "CoordinateSpace",
    "ErrorResponse",
]
 
 
class LayerResult(BaseModel):
    """Output of a single detection layer (ELA, noise residual, copy-move, or AI-classifier)."""
 
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "layer_name": "copy_move",
                "score": 0.82,
                "reliability": "high",
                "status": "ok",
                "detail": {
                    "match_regions": [
                        {"x1": 120, "y1": 340, "x2": 410, "y2": 560},
                        {"x1": 900, "y1": 340, "x2": 1190, "y2": 560},
                    ],
                    "match_count": 1,
                },
                "heatmap_png_b64": None,
            }
        }
    )
 
    layer_name: str = Field(
        ...,
        description="Identifier of the detection layer that produced this result, e.g. 'ela', 'noise_residual', 'copy_move', or 'ai_generated_classifier'.",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Suspicion score from this layer in the range 0-1, where higher means more likely tampered.",
    )
    reliability: Literal["low", "medium", "high"] = Field(
        ...,
        description="This layer's confidence in its own score, independent of the score's magnitude.",
    )
    status: Literal["ok", "skipped", "failed"] = Field(
        ...,
        description="Execution status of the layer: completed normally, intentionally skipped, or failed with an error.",
    )
    detail: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form, layer-specific extra data, e.g. copy-move match-line coordinates or ELA quality settings.",
    )
    heatmap_png_b64: str | None = Field(
        default=None,
        description="Base64-encoded PNG heatmap visualizing this layer's findings, if the layer produces one.",
    )
 
 
class CoordinateSpace(BaseModel):
    """The normalized image dimensions that overlay/heatmap coordinates are expressed relative to."""
 
    width: int = Field(
        ...,
        gt=0,
        description="Width in pixels of the normalized coordinate space used for overlays and heatmaps.",
    )
    height: int = Field(
        ...,
        gt=0,
        description="Height in pixels of the normalized coordinate space used for overlays and heatmaps.",
    )
 
 
class AnalysisResult(BaseModel):
    """Full response returned by the analyze endpoint for one image analysis."""
 
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "verdict": "likely_tampered",
                "tamper_score": 0.87,
                "per_layer": [
                    {
                        "layer_name": "ela",
                        "score": 0.74,
                        "reliability": "medium",
                        "status": "ok",
                        "detail": {"jpeg_quality_estimate": 85},
                        "heatmap_png_b64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB...",
                    },
                    {
                        "layer_name": "noise_residual",
                        "score": 0.65,
                        "reliability": "medium",
                        "status": "ok",
                        "detail": {"residual_variance": 0.0021},
                        "heatmap_png_b64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB...",
                    },
                    {
                        "layer_name": "copy_move",
                        "score": 0.91,
                        "reliability": "high",
                        "status": "ok",
                        "detail": {
                            "match_regions": [
                                {"x1": 120, "y1": 340, "x2": 410, "y2": 560},
                                {"x1": 900, "y1": 340, "x2": 1190, "y2": 560},
                            ],
                            "match_count": 1,
                        },
                        "heatmap_png_b64": None,
                    },
                    {
                        "layer_name": "ai_generated_classifier",
                        "score": 0.12,
                        "reliability": "low",
                        "status": "skipped",
                        "detail": {"reason": "no_internet_fallback_model_unavailable"},
                        "heatmap_png_b64": None,
                    },
                ],
                "explanation": [
                    "A duplicated region was detected in the upper-right quadrant of the image.",
                    "Error level analysis shows inconsistent compression artifacts around the duplicated region.",
                    "The AI-generated-image classifier was skipped because no internet connection was available.",
                ],
                "metadata": {
                    "exif_present": True,
                    "software_tag": "Adobe Photoshop 25.0",
                    "original_datetime": "2024-03-11T14:22:03",
                    "gps_present": False,
                },
                "coordinate_space": {"width": 1024, "height": 768},
                "offline_mode": True,
                "generated_at": "2026-10-02T17:45:12Z",
            }
        }
    )
 
    verdict: Literal["authentic", "suspicious", "likely_tampered"] = Field(
        ...,
        description="Overall human-readable verdict derived from the fused tamper score.",
    )
    tamper_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Final fused suspicion score across all detection layers, in the range 0-1.",
    )
    per_layer: list[LayerResult] = Field(
        ...,
        description="Individual results from each detection layer that contributed to the fused score.",
    )
    explanation: list[str] = Field(
        default_factory=list,
        description="Plain-English reasons for the verdict, produced by the explainability module.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="EXIF and other file-metadata findings extracted from the uploaded image.",
    )
    coordinate_space: CoordinateSpace = Field(
        ...,
        description="Normalized image dimensions that all overlay and heatmap coordinates are relative to.",
    )
    offline_mode: bool = Field(
        ...,
        description="Whether this analysis ran with one or more layers skipped due to no-internet fallback.",
    )
    generated_at: str = Field(
        ...,
        description="UTC ISO-8601 timestamp string indicating when this result was generated.",
    )
 
 
class ErrorResponse(BaseModel):
    """Clean error shape returned for failed requests."""
 
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "no_image_provided",
                "message": "No image file was found in the request.",
                "detail": "Expected a multipart/form-data field named 'image'.",
            }
        }
    )
 
    error: str = Field(
        ...,
        description="Short machine-readable error code, e.g. 'no_image_provided' or 'pipeline_failure'.",
    )
    message: str = Field(
        ...,
        description="Human-readable description of what went wrong.",
    )
    detail: str | None = Field(
        default=None,
        description="Optional additional detail, such as a lower-level error message or traceback summary.",
    )
 
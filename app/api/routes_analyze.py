"""app/api/routes_analyze.py

FastAPI router exposing the image-forensics analysis endpoint.
"""

from __future__ import annotations

import logging
from typing import Final

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from forensics import pipeline
from forensics.schemas import AnalysisResult, ErrorResponse

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])

_ALLOWED_CONTENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "image/gif",
    }
)

_ERROR_RESPONSES: Final[dict[int | str, dict[str, object]]] = {
    422: {
        "model": ErrorResponse,
        "description": "The request did not contain a usable image.",
    },
    500: {
        "model": ErrorResponse,
        "description": "The analysis pipeline failed unexpectedly.",
    },
}


@router.post(
    "/api/analyze",
    response_model=AnalysisResult,
    responses=_ERROR_RESPONSES,
    summary="Analyze an uploaded image for signs of tampering",
)
async def analyze_image(
    image: UploadFile | None = File(
        default=None,
        description="The image file to analyze, sent as multipart/form-data.",
    ),
) -> AnalysisResult | JSONResponse:
    """Analyze an uploaded image for tampering and AI generation.

    Accepts a ``multipart/form-data`` request with a single file field named
    ``image``. On success, returns an ``AnalysisResult`` containing the
    overall ``verdict`` (``authentic``, ``suspicious``, or
    ``likely_tampered``), the fused ``tamper_score`` from 0 to 1, a
    ``per_layer`` list of individual ``LayerResult`` entries, plain-English
    ``explanation`` lines, file ``metadata``, the ``coordinate_space`` that
    overlay and heatmap coordinates are relative to, an ``offline_mode``
    flag, and a UTC ``generated_at`` timestamp.

    On failure, returns an ``ErrorResponse`` with status 422 when the
    upload is missing, is not an image, is empty, or cannot be decoded,
    and with status 500 when the pipeline fails internally.

    Args:
        image: The uploaded image file, or ``None`` if the field is absent.

    Returns:
        An ``AnalysisResult`` on success, or a ``JSONResponse`` carrying an
        ``ErrorResponse`` body on failure.
    """
    if image is None:
        return _error(
            422,
            "no_image_provided",
            "No image file was found in the request.",
            "Expected a multipart/form-data field named 'image'.",
        )

    if image.content_type not in _ALLOWED_CONTENT_TYPES:
        return _error(
            422,
            "unsupported_media_type",
            "The uploaded file is not a supported image type.",
            f"Received content type '{image.content_type}'.",
        )

    data = await image.read()
    if not data:
        return _error(422, "empty_image", "The uploaded image is empty.", None)

    try:
        return await run_in_threadpool(pipeline.analyze, data)
    except pipeline.InvalidImageError as exc:
        return _error(
            422,
            "invalid_image",
            "The uploaded file could not be decoded as an image.",
            str(exc),
        )
    except Exception:
        logger.exception("Image analysis pipeline failed")
        return _error(
            500,
            "pipeline_failure",
            "Image analysis failed due to an internal error.",
            None,
        )


def _error(
    status_code: int,
    code: str,
    message: str,
    detail: str | None,
) -> JSONResponse:
    """Build a JSON error response with the ``ErrorResponse`` shape.

    Args:
        status_code: HTTP status code to return.
        code: Short machine-readable error code.
        message: Human-readable description of the failure.
        detail: Optional additional detail, or ``None``.

    Returns:
        A ``JSONResponse`` whose body matches ``ErrorResponse``.
    """
    body = ErrorResponse(error=code, message=message, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump())

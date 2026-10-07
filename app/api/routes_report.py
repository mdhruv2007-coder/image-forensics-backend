"""
app/api/routes_report.py

FastAPI router exposing POST /api/report/pdf. The client re-sends the
AnalysisResult it already received from /api/analyze as a JSON body.
The PDF bytes are returned as application/pdf with a Content-Disposition
header suggesting forensics-report.pdf. FastAPI returns 422 for malformed
bodies before this handler runs. Errors raised during PDF generation are
not caught here and surface as 500 responses.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from forensics.report.pdf_report import generate_pdf
from forensics.schemas import AnalysisResult

__all__ = ["router"]

router = APIRouter(prefix="/api/report", tags=["report"])


@router.post("/pdf", response_class=Response)
def report_pdf(result: AnalysisResult) -> Response:
    """Generate a PDF report from an AnalysisResult and return it."""
    pdf_bytes = generate_pdf(result)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="forensics-report.pdf"'},
    )
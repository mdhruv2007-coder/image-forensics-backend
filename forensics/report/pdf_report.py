"""
forensics/report/pdf_report.py

Builds a one-to-two-page PDF summary of an AnalysisResult with reportlab.
The layout uses reportlab's built-in styles only, with no custom fonts or
image assets. The disclaimer is imported from json_report so both
outputs stay in sync. reportlab exceptions are not caught here and
propagate to the caller.
"""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from forensics.report.json_report import DISCLAIMER
from forensics.schemas import AnalysisResult

__all__ = ["generate_pdf"]


def generate_pdf(result: AnalysisResult) -> bytes:
    """Render an AnalysisResult to PDF and return the document bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(8.5 * inch, 11 * inch),
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Image Forensics Report",
    )
    styles = getSampleStyleSheet()
    story: list = []

    story.append(Paragraph("Image Forensics Report", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(
        Paragraph(
            f"<b>Verdict:</b> {result.verdict.replace('_', ' ').title()}",
            styles["Heading2"],
        )
    )
    story.append(
        Paragraph(
            f"<b>Tamper score:</b> {result.tamper_score:.2f} (0 to 1 scale)",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Per-layer results", styles["Heading3"]))
    table_data = [["Layer", "Score", "Reliability", "Status"]]
    for layer in result.per_layer:
        table_data.append(
            [
                layer.layer_name,
                f"{layer.score:.2f}",
                layer.reliability,
                layer.status,
            ]
        )
    table = Table(table_data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Explanation", styles["Heading3"]))
    if result.explanation:
        items = [
            ListItem(Paragraph(text, styles["Normal"]))
            for text in result.explanation
        ]
        story.append(ListFlowable(items, bulletType="bullet", start="•"))
    else:
        story.append(Paragraph("No explanation was provided.", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("<i>" + DISCLAIMER + "</i>", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
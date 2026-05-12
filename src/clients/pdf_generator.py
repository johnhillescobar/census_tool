import pandas as pd
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    Flowable,
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
)
from typing import List
from datetime import datetime
from pathlib import Path
from io import BytesIO
import logging

from src.domain.census_tool_contract import (
    StrictCensusApiResponse,
)
from src.domain.rendered_output_contract import RenderedArtifact, FootnoteItem
from src.services.census_render_adapter import response_to_tabular_payload
from src.state.types import FinalResponseState, WorkflowArtifactsState


logger = logging.getLogger(__name__)


class PdfSessionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str | None = None


class PdfConversationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final: FinalResponseState | None = None
    artifacts: WorkflowArtifactsState | None = None
    logs: list[str] = Field(default_factory=list)
    error: str | None = None


class PdfConversationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = "No question available"
    timestamp: datetime | None = None
    result: PdfConversationResult | None = None


def _coerce_rendered_artifacts(value: Any) -> list[RenderedArtifact]:
    if not isinstance(value, list):
        return []

    artifacts: list[RenderedArtifact] = []

    for item in value:
        try:
            if isinstance(item, RenderedArtifact):
                artifacts.append(item)

            elif isinstance(item, dict):
                artifacts.append(RenderedArtifact.model_validate(item))

        except Exception as exc:
            logger.warning(
                "Skipping invalid rendered artifact in PDF generator: %s", exc
            )
            continue

    return artifacts


def _coerce_final_state(state: Any) -> FinalResponseState | None:
    try:
        if isinstance(state, FinalResponseState):
            return state

        elif isinstance(state, dict):
            return FinalResponseState.model_validate(state)

    except Exception as exc:
        logger.warning("Skipping invalid final status in PDF generator: %s", exc)
        return None


def _coerce_artifacts_state(value: Any) -> WorkflowArtifactsState | None:
    try:
        if isinstance(value, WorkflowArtifactsState):
            return value

        elif isinstance(value, dict):
            return WorkflowArtifactsState.model_validate(value)

    except Exception as exc:
        logger.warning("Skipping invalid artifacts state in PDF generator: %s", exc)
        return None


def _coerce_footnotes(value: Any) -> list[FootnoteItem]:
    if not isinstance(value, list):
        return []

    items: list[FootnoteItem] = []
    for item in value:
        try:
            if isinstance(item, FootnoteItem):
                items.append(item)
            elif isinstance(item, str):
                items.append(FootnoteItem(text=item))
            elif isinstance(item, dict):
                items.append(FootnoteItem.model_validate(item))
        except Exception as exc:
            logger.warning("Skipping invalid footnote in PDF generator: %s", exc)

    return items


def generate_session_pdf(
    conversation_history: list[PdfConversationEntry],
    user_id: str,
    session_metadata: PdfSessionMetadata,
) -> bytes:
    """
    Generate PDF from Streamlit session data

    Args:
        conversation_history: List of PdfConversationEntry objects
        user_id: User identifier
        session_metadata: PdfSessionMetadata object

    Returns:
        PDF bytes for download
    """
    entries = [
        item
        if isinstance(item, PdfConversationEntry)
        else PdfConversationEntry.model_validate(item)
        for item in conversation_history
    ]
    metadata = (
        session_metadata
        if isinstance(session_metadata, PdfSessionMetadata)
        else PdfSessionMetadata.model_validate(session_metadata)
    )

    # Import pandas for table data processing
    import pandas as pd

    # Create BytesIO buffer for PDF
    buffer = BytesIO()

    # Custom page template for headers/footers
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            start_page = getattr(self, "_startPage")
            start_page()

        def save(self):
            page_count = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_number(page_count)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def draw_page_number(self, page_count):
            self.setFont("Helvetica", 9)
            self.setFillColor(colors.grey)
            # Footer with page numbers and timestamp
            page_number = getattr(self, "_pageNumber")
            footer_text = f"Page {page_number} of {page_count} | Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            self.drawRightString(7.5 * inch, 0.75 * inch, footer_text)

            # Header line
            self.setStrokeColor(colors.HexColor("#E6E6E6"))
            self.setLineWidth(0.5)
            self.line(0.75 * inch, 10.3 * inch, 7.5 * inch, 10.3 * inch)

    # Initialize PDF document with custom canvas
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=100,  # Increased for header
        bottomMargin=72,  # Increased for footer
    )

    # Enhanced styles
    styles = getSampleStyleSheet()

    # Cover page title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        spaceAfter=40,
        alignment=1,  # Center
        textColor=colors.HexColor("#2E4057"),
        fontName="Helvetica-Bold",
    )

    # Question style
    question_style = ParagraphStyle(
        "QuestionStyle",
        parent=styles["Normal"],
        fontSize=12,
        spaceAfter=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#2E4057"),
    )

    # Answer style
    answer_style = ParagraphStyle(
        "AnswerStyle",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=15,
        leftIndent=20,
        fontName="Helvetica",
    )

    # Metadata style
    meta_style = ParagraphStyle(
        "MetaStyle",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=5,
        fontName="Helvetica-Oblique",
        textColor=colors.grey,
    )

    # Footnote style
    footnote_style = ParagraphStyle(
        "Footnote",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#666666"),
        leftIndent=12,
        spaceBefore=2,
        spaceAfter=2,
    )

    # Story list to hold all content
    story = []

    # Enhanced cover page
    story.append(Spacer(1, 60))
    story.append(Paragraph("🏛️ Census Data Session Report", title_style))
    story.append(Spacer(1, 40))

    # Session metadata with better styling
    session_info = f"""
    <b>User Session Details:</b><br/><br/>
    <b>User ID:</b> {user_id}<br/>
    <b>Thread ID:</b> {metadata.thread_id or "N/A"}<br/>
    <b>Report Generated:</b> {datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")}<br/>
    <b>Total Questions:</b> {len(entries)}<br/>
    <b>Session Duration:</b> {_calculate_session_duration(entries)}
    """
    story.append(Paragraph(session_info, styles["Normal"]))
    story.append(Spacer(1, 60))
    story.append(
        Paragraph(
            "<i>This report contains all questions, answers, charts, and data tables from your census data session.</i>",
            meta_style,
        )
    )

    # Page break
    story.append(Spacer(1, 300))

    # Process each conversation with enhanced formatting
    for i, entry in enumerate(entries, 1):
        # Question section with enhanced styling
        question = entry.question
        timestamp = entry.timestamp

        # Question header with timestamp
        if timestamp:
            try:
                if hasattr(timestamp, "strftime"):
                    time_str = timestamp.strftime("%I:%M %p")
                else:
                    time_str = str(timestamp)
                story.append(Paragraph(f"Question {i} • {time_str}", meta_style))
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to format timestamp for question {i}: {e}")
                story.append(Paragraph(f"Question {i}", meta_style))
        else:
            story.append(Paragraph(f"Question {i}", meta_style))

        story.append(Paragraph(f"<b>📋 {question}</b>", question_style))
        story.append(Spacer(1, 15))

        # Answer section
        result = entry.result
        final_state = result.final if result else None
        artifacts_state = result.artifacts if result else None
        answer_text = final_state.answer_text if final_state else "No answer available"

        story.append(Paragraph("<b>💡 Answer:</b>", styles["Normal"]))
        story.append(Paragraph(answer_text, answer_style))
        story.append(Spacer(1, 15))

        # Enhanced file processing with table embedding
        generated_files = _coerce_rendered_artifacts(
            final_state.generated_files if final_state else []
        )
        census_data = artifacts_state.census_data if artifacts_state else None

        # Process charts and tables
        charts_processed = 0
        tables_processed = 0

        for artifact in generated_files:
            artifact_path = Path(artifact.path)

            if artifact.kind == "chart":
                try:
                    story.append(Paragraph("<b>📊 Chart:</b>", styles["Normal"]))

                    if artifact_path.exists():
                        img = Image(
                            str(artifact_path), width=6 * inch, height=4.5 * inch
                        )
                        story.append(img)
                        story.append(Spacer(1, 10))
                        charts_processed += 1
                    else:
                        story.append(
                            Paragraph(
                                f"⚠️ Chart file not found: {artifact_path.name}",
                                meta_style,
                            )
                        )

                except Exception as exc:
                    logger.warning("Skipping invalid chart in PDF generator: %s", exc)

            elif artifact.kind == "table":
                story.append(Paragraph("<b>📋 Data Table:</b>", styles["Normal"]))
                table_embedded = False

                # Method 1: Embed directly from typed census data
                if (
                    census_data is not None
                    and census_data.success
                    and census_data.row_count > 0
                ):
                    try:
                        table_data = _create_pdf_table_from_census_data(census_data)
                        if table_data:
                            story.append(table_data)
                            table_embedded = True
                            tables_processed += 1

                    except Exception as exc:
                        logger.warning(
                            "Failed to embed table from census data: %s", exc
                        )

                # Method 2: Try to read the saved table file
                if not table_embedded:
                    try:
                        if artifact_path.exists():
                            suffix = artifact_path.suffix.lower()
                            if suffix == ".csv":
                                df = pd.read_csv(artifact_path)
                            elif suffix == ".parquet":
                                df = pd.read_parquet(artifact_path)
                            else:
                                df = None
                            if df is not None:
                                table_data = _create_pdf_table_from_dataframe(
                                    df,
                                    artifact.title
                                    or f"Table from {artifact_path.name}",
                                )
                                if table_data:
                                    story.append(table_data)
                                    table_embedded = True
                                    tables_processed += 1
                    except Exception:
                        pass  # Fall back to file reference

                # Method 3: Mention the file only
                if not table_embedded:
                    story.append(
                        Paragraph(
                            f"📁 Table saved to: {artifact_path.name}",
                            meta_style,
                        )
                    )

                # Add footnotes below table
                footnotes = _coerce_footnotes(
                    final_state.footnotes if final_state else []
                )
                if footnotes:
                    story.append(Spacer(1, 10))
                    for i, footnote in enumerate(footnotes, 1):
                        footnote_text = f"{i}. {footnote}"
                        story.append(Paragraph(footnote_text, footnote_style))
                    story.append(Spacer(1, 10))

        # Add summary for this conversation
        if charts_processed > 0 or tables_processed > 0:
            summary_parts = []
            if charts_processed > 0:
                summary_parts.append(
                    f"{charts_processed} chart{'s' if charts_processed > 1 else ''}"
                )
            if tables_processed > 0:
                summary_parts.append(
                    f"{tables_processed} table{'s' if tables_processed > 1 else ''}"
                )

            story.append(
                Paragraph(f"<i>Generated: {', '.join(summary_parts)}</i>", meta_style)
            )

        # Add spacing between conversations
        story.append(Spacer(1, 30))

    # Build PDF with custom canvas
    try:
        doc.build(
            story,
            onFirstPage=_add_header,
            onLaterPages=_add_header,
            canvasmaker=NumberedCanvas,
        )
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        # Return error as PDF content
        error_buffer = BytesIO()
        error_doc = SimpleDocTemplate(error_buffer, pagesize=letter)
        error_story: list[Flowable] = [
            Paragraph(f"PDF Generation Error: {str(e)}", styles["Normal"])
        ]
        error_doc.build(error_story)
        error_buffer.seek(0)
        return error_buffer.getvalue()


def _calculate_session_duration(
    conversation_history: list[PdfConversationEntry],
) -> str:
    """Calculate session duration from conversation timestamps"""
    if len(conversation_history) < 2:
        return "N/A"

    try:
        timestamps = []
        for entry in conversation_history:
            ts = entry.timestamp
            if ts:
                timestamps.append(ts)

        if len(timestamps) >= 2:
            duration = max(timestamps) - min(timestamps)
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)

            if hours > 0:
                return f"{int(hours)}h {int(minutes)}m"
            else:
                return f"{int(minutes)} minutes"
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to calculate session duration: {e}")
        return "N/A"

    return "N/A"


def _add_header(canvas, doc):
    """Add header to PDF pages"""
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(colors.HexColor("#2E4057"))
    canvas.drawString(72, letter[1] - 50, "Census Data Session Report")

    # Header line
    canvas.setStrokeColor(colors.HexColor("#048A81"))
    canvas.setLineWidth(2)
    canvas.line(72, letter[1] - 65, letter[0] - 72, letter[1] - 65)
    canvas.restoreState()


def _create_pdf_table_from_census_data(
    census_data: StrictCensusApiResponse,
) -> Table | None:
    """Create ReportLab Table from census_data structure"""
    try:
        raw_table = response_to_tabular_payload(census_data)
        table_data = [raw_table.headers, *raw_table.rows]
        return _create_pdf_table_from_data(table_data, "Census Data")

    except Exception:
        return None


def _create_pdf_table_from_dataframe(df: pd.DataFrame, title: str) -> Table | None:
    """Create ReportLab Table from pandas DataFrame"""
    try:
        # Limit rows for readability
        if len(df) > 20:
            df_display = df.head(20)
            note_added = True
        else:
            df_display = df
            note_added = False

        # Convert to list of lists
        table_data = [df_display.columns.tolist()] + df_display.values.tolist()

        if note_added:
            table_data.append(
                ["...", "Data truncated for PDF display"] + [""] * (len(df.columns) - 2)
            )

        return _create_pdf_table_from_data(table_data, title)
    except Exception:
        return None


def _create_pdf_table_from_data(table_data: List[List], title: str) -> Table | None:
    """Create styled ReportLab Table from data array"""
    try:
        if not table_data or len(table_data) < 2:
            return None

        # Create table
        table = Table(table_data)

        # Apply styling
        table.setStyle(
            TableStyle(
                [
                    # Header row
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#048A81")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    # Data rows
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8F9FA")],
                    ),
                    # Grid
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # Column width
                    (
                        "COLWIDTH",
                        (0, 0),
                        (0, -1),
                        1.5 * inch,
                    ),  # First column (location names) wider
                ]
            )
        )

        return table

    except Exception:
        return None

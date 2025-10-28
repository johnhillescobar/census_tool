import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
)
from typing import Dict, List
from datetime import datetime
from pathlib import Path
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def generate_session_pdf(
    conversation_history: List[Dict], user_id: str, session_metadata: Dict
) -> bytes:
    """
    Generate PDF from Streamlit session data

    Args:
        conversation_history: List of {question, answer, charts, tables, timestamp}
        user_id: User identifier
        session_metadata: {thread_id, start_time, etc.}

    Returns:
        PDF bytes for download
    """
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
            self._startPage()

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
            footer_text = f"Page {self._pageNumber} of {page_count} | Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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
    <b>Thread ID:</b> {session_metadata.get("thread_id", "N/A")}<br/>
    <b>Report Generated:</b> {datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")}<br/>
    <b>Total Questions:</b> {len(conversation_history)}<br/>
    <b>Session Duration:</b> {_calculate_session_duration(conversation_history)}
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
    for i, entry in enumerate(conversation_history, 1):
        # Question section with enhanced styling
        question = entry.get("question", "No question available")
        timestamp = entry.get("timestamp", "")

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
        result = entry.get("result", {})
        final = result.get("final", {})
        artifacts = result.get("artifacts", {})
        answer_text = final.get("answer_text", "No answer available")

        story.append(Paragraph("<b>💡 Answer:</b>", styles["Normal"]))
        story.append(Paragraph(answer_text, answer_style))
        story.append(Spacer(1, 15))

        # Enhanced file processing with table embedding
        generated_files = final.get("generated_files", [])
        census_data = artifacts.get("census_data", {})

        # Process charts and tables
        charts_processed = 0
        tables_processed = 0

        for file_info in generated_files:
            if isinstance(file_info, str):
                if "Chart created successfully:" in file_info:
                    # Extract and embed chart
                    filepath = file_info.split("Chart created successfully: ")[1]
                    try:
                        if Path(filepath).exists():
                            story.append(
                                Paragraph("<b>📊 Chart:</b>", styles["Normal"])
                            )
                            # Resize chart appropriately
                            img = Image(filepath, width=6 * inch, height=4.5 * inch)
                            story.append(img)
                            story.append(Spacer(1, 10))  # Reduced spacing

                            # Add footnotes below chart
                            footnotes = final.get("footnotes", [])
                            if footnotes:
                                for i, footnote in enumerate(footnotes, 1):
                                    footnote_text = f"{i}. {footnote}"
                                    story.append(
                                        Paragraph(footnote_text, footnote_style)
                                    )
                                story.append(Spacer(1, 10))

                            story.append(Spacer(1, 5))  # Remaining spacing
                            charts_processed += 1
                        else:
                            story.append(
                                Paragraph(
                                    f"⚠️ Chart file not found: {Path(filepath).name}",
                                    meta_style,
                                )
                            )
                    except Exception as e:
                        story.append(
                            Paragraph(f"❌ Error loading chart: {str(e)}", meta_style)
                        )

                elif "Table created successfully:" in file_info:
                    # Extract table path and embed data directly
                    table_path = file_info.split("Table created successfully: ")[1]
                    story.append(Paragraph("<b>📋 Data Table:</b>", styles["Normal"]))

                    # Try to embed table data directly from census_data
                    table_embedded = False

                    # Method 1: Extract from census_data artifacts
                    if census_data and "data" in census_data:
                        try:
                            table_data = _create_pdf_table_from_census_data(census_data)
                            if table_data:
                                story.append(table_data)
                                table_embedded = True
                                tables_processed += 1
                        except Exception:
                            pass  # Fall back to file reference

                    # Method 2: Try to read the saved table file
                    if not table_embedded:
                        try:
                            table_file_path = Path(table_path)
                            if table_file_path.exists():
                                if table_file_path.suffix == ".csv":
                                    df = pd.read_csv(table_file_path)
                                    table_data = _create_pdf_table_from_dataframe(
                                        df, f"Table from {table_file_path.name}"
                                    )
                                    story.append(table_data)
                                    table_embedded = True
                                    tables_processed += 1
                        except Exception:
                            pass  # Fall back to file reference

                    # Fallback: Just mention the file
                    if not table_embedded:
                        story.append(
                            Paragraph(
                                f"📁 Table saved to: {Path(table_path).name}",
                                meta_style,
                            )
                        )

                    # Add footnotes below table
                    footnotes = final.get("footnotes", [])
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
        doc.build(story, onFirstPage=_add_header, onLaterPages=_add_header)
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        # Return error as PDF content
        error_buffer = BytesIO()
        error_doc = SimpleDocTemplate(error_buffer, pagesize=letter)
        error_story = [Paragraph(f"PDF Generation Error: {str(e)}", styles["Normal"])]
        error_doc.build(error_story)
        error_buffer.seek(0)
        return error_buffer.getvalue()


def _calculate_session_duration(conversation_history: List[Dict]) -> str:
    """Calculate session duration from conversation timestamps"""
    if len(conversation_history) < 2:
        return "N/A"

    try:
        timestamps = []
        for entry in conversation_history:
            ts = entry.get("timestamp")
            if ts:
                if hasattr(ts, "to_pydatetime"):
                    timestamps.append(ts.to_pydatetime())
                elif hasattr(ts, "timestamp"):
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


def _create_pdf_table_from_census_data(census_data: Dict) -> Table:
    """Create ReportLab Table from census_data structure"""
    try:
        if not census_data or "data" not in census_data or not census_data["data"]:
            return None

        data_rows = census_data["data"]
        if len(data_rows) < 2:
            return None

        # First row is headers, rest are data
        headers = data_rows[0]
        table_data = [headers] + data_rows[1:]

        # Limit rows for PDF readability (max 20 rows + header)
        if len(table_data) > 21:
            table_data = table_data[:21]
            # Add note about truncation
            table_data[-1] = ["...", "Data truncated for PDF display"] + [""] * (
                len(headers) - 2
            )

        return _create_pdf_table_from_data(table_data, "Census Data")

    except Exception:
        return None


def _create_pdf_table_from_dataframe(df: pd.DataFrame, title: str) -> Table:
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


def _create_pdf_table_from_data(table_data: List[List], title: str) -> Table:
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

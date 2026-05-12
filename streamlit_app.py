"""
Streamlit Web Interface for Census Data Assistant

This provides a web-based interface alongside the existing CLI interface (main.py).
Both interfaces use the same underlying LangGraph workflow and processing logic.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import logging
from typing import Any
from datetime import datetime

from src.domain.benchmark_contract import BenchmarkClarificationRequired
from src.domain.temporal_contract import TemporalClarificationRequired
from src.state.types import (
    FinalResponseState,
    WorkflowArtifactsState,
    WorkflowPlanState,
)
from src.clients import SessionLogger
from src.domain.presentation_contract import PresentationKind
from src.clients.pdf_generator import PdfSessionMetadata, generate_session_pdf
from src.services.census_render_adapter import (
    response_to_dataframe,
    response_to_tabular_payload,
)
from src.services.conversation_history import (
    census_state_from_pdf_history_entry,
    history_entry_presentation_kind,
    infer_streamlit_line_xy,
    pdf_conversation_result_dict,
)
from src.services.presentation_routing import compute_presentation_routing
from app import create_census_graph
from src.state.types import CensusState
from langchain_core.runnables import RunnableConfig

project_root = Path(__file__).parent
streamlit_logs_dir = project_root / "logs" / "streamlit_logs"
streamlit_logs_dir.mkdir(parents=True, exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Census Data Assistant",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _first_table_download_info(
    final: FinalResponseState | None,
) -> tuple[str, str] | None:
    """Saved table path and MIME from rendered artifacts (`RenderedArtifact`)."""
    if final is None or not final.generated_files:
        return None
    for art in final.generated_files:
        if art.kind == "table" and art.path:
            mime = art.mime_type or "application/octet-stream"
            return art.path, mime
    for art in final.generated_files:
        if art.mime_type == "text/csv" and art.path:
            return art.path, art.mime_type
    return None


def _clarification_question_and_options(
    plan: WorkflowPlanState, final: FinalResponseState
) -> tuple[str, list[str]]:
    """Clarification UI text from plan (temporal/benchmark prompts), not FinalResponseState fields."""
    temporal = plan.temporal
    if isinstance(temporal, TemporalClarificationRequired):
        p = temporal.clarification_prompt
        lines = [f"{o.option_id}: {o.label}" for o in p.options]
        return (p.question_text, lines)
    benchmark = plan.benchmark
    if isinstance(benchmark, BenchmarkClarificationRequired):
        p = benchmark.clarification_prompt
        lines = [f"{o.option_id}: {o.label}" for o in p.options]
        return (p.question_text, lines)
    text = (final.answer_text or "").strip()
    return (text or "I need more information.", [])


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if "graph" not in st.session_state:
        st.session_state.graph = create_census_graph()

    if "user_id" not in st.session_state:
        st.session_state.user_id = "demo"

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = "main"

    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []

    if "current_result" not in st.session_state:
        st.session_state.current_result = None

    # Initialize session logger state
    if "session_logger" not in st.session_state:
        st.session_state.session_logger = None

    if "logged_user_id" not in st.session_state:
        st.session_state.logged_user_id = None

    if "log_file_path" not in st.session_state:
        st.session_state.log_file_path = None

    # Check if user_id changed - start new logger
    if st.session_state.logged_user_id != st.session_state.user_id:
        # Stop previous logger if it exists
        if st.session_state.session_logger:
            try:
                st.session_state.session_logger.stop()
            except Exception as e:
                logger.warning(f"Error stopping previous logger: {e}")

        # Start new logger for current user
        try:
            session_logger = SessionLogger(
                st.session_state.user_id,
                log_dir=streamlit_logs_dir,
                filename_prefix=f"streamlit_{st.session_state.user_id}",
            )
            log_file = session_logger.start()
            st.session_state.session_logger = session_logger
            st.session_state.logged_user_id = st.session_state.user_id
            st.session_state.log_file_path = log_file
            logger.info(f"Session logging started for user: {st.session_state.user_id}")
            logger.info(f"Log file: {log_file}")
        except Exception as e:
            logger.error(f"Error starting session logger: {e}")


def display_streamlit_results(payload: CensusState | dict[str, Any] | None) -> None:
    """Render workflow state from a ``CensusState`` or raw LangGraph invoke dict."""

    if payload is None:
        st.error("No results to display")
        return

    if isinstance(payload, dict) and payload.get("error"):
        st.error(str(payload["error"]))
        return

    try:
        state = (
            payload
            if isinstance(payload, CensusState)
            else CensusState.model_validate(payload)
        )
    except Exception as e:
        logger.warning("Invalid workflow state for display: %s", e)
        st.error("Could not read workflow results.")
        return

    routing = compute_presentation_routing(state)
    final = state.final
    st.caption(f"Presentation routing: {routing.kind.value} — {routing.reason}")

    if routing.kind == PresentationKind.CLARIFICATION:
        display_clarification_streamlit(state.plan, state.final)
        return

    if routing.kind == PresentationKind.NON_CENSUS_OR_EMPTY:
        display_not_census_streamlit(state.final)
        return

    if not final or not final.answer_text:
        st.warning("No answer available")
        return

    st.subheader("Answer")
    st.markdown(final.answer_text)

    footnotes = final.footnotes if final.footnotes else []
    if footnotes:
        st.subheader("Footnotes")
        for i, footnote in enumerate(footnotes):
            st.caption(f"{i + 1}. {footnote}")

    if routing.kind == PresentationKind.SINGLE_VALUE:
        display_single_value_streamlit(state.artifacts)
    elif routing.kind == PresentationKind.TIME_SERIES:
        display_series_streamlit(state.artifacts)
    elif routing.kind == PresentationKind.TABLE:
        display_table_streamlit(state.artifacts, final)
    elif routing.kind == PresentationKind.NARRATIVE_ONLY:
        pass
    else:
        st.warning("No presentation routing available")


def display_single_value_streamlit(artifacts: WorkflowArtifactsState) -> None:
    """Display a single value answer with Streamlit components"""

    cd = artifacts.census_data
    if not cd.success or cd.row_count < 1:
        st.warning("No census data to display as a single value.")
        return

    row = cd.records[0].values
    year = str(cd.request.year) if cd.request else "-"
    geo = row.get("NAME", "Unknown location") or row.get("name", "Unknown location")

    value = "N/A"
    label = "Value"

    if cd.request and cd.request.variables:
        for var in cd.request.variables:
            if var in row:
                value = row[var]
                label = artifacts.variable_labels.labels.get(var, var)
                break

    # Create metrics display
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📍 Location", geo)

    with col2:
        st.metric("📅 Year", year)

    with col3:
        st.metric("📊 Value", value)

    if label != "Value":
        st.info(f"🔢 Variable: {label}")


def display_series_streamlit(artifacts: WorkflowArtifactsState) -> None:
    """Display a time series answer with interactive chart"""

    cd = artifacts.census_data
    if not cd.success or cd.row_count < 1:
        st.warning("No census data to display as a time series.")
        return

    data = cd.records
    geo = data[0].values.get("NAME", "Unknown location") or data[0].values.get(
        "name", "Unknown location"
    )
    year = str(cd.request.year) if cd.request else "-"
    variable = (
        cd.request.variables[0]
        if cd.request and cd.request.variables
        else "Unknown variable"
    )

    if not data:
        st.warning("No data available")
        return

    df = response_to_dataframe(response_to_tabular_payload(cd))

    try:
        x_col, y_col = infer_streamlit_line_xy(df, cd)
        plot_df = df[[x_col, y_col]].copy()
    except ValueError:
        # Narrow projection when API rows use year/value keys but headers differ.
        plot_df = pd.DataFrame(
            [
                {
                    "Year": item.values.get("year", "Unknown"),
                    "Value": item.values.get("value", 0),
                    "Formatted Value": item.values.get(
                        "formatted_value",
                        str(item.values.get("value", 0)),
                    ),
                }
                for item in data
            ]
        )
        x_col, y_col = "Year", "Value"

    # Display summary
    st.info(f"📍 Location: {geo}")
    st.info(f"📅 Year: {year}")
    st.info(f"🔢 Variable: {variable}")

    fig = px.line(
        plot_df,
        x=x_col,
        y=y_col,
        title=f"{variable} Trends for {geo}",
        labels={y_col: y_col, x_col: x_col},
    )

    fig.update_layout(
        xaxis_title=x_col, yaxis_title=y_col, hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📈 Data Table")
    st.dataframe(df, use_container_width=True)


def display_table_streamlit(
    artifacts: WorkflowArtifactsState,
    final: FinalResponseState | None = None,
) -> None:
    """Display a table answer with interactive table"""

    cd = artifacts.census_data
    if not cd.success or cd.row_count < 1:
        st.warning("No census data to display as a table.")
        return

    data = cd.records
    total_rows = cd.row_count

    st.info(f"📊 Table Data ({total_rows} rows)")

    if not data:
        st.warning("No data available")
        return

    df = response_to_dataframe(response_to_tabular_payload(cd))
    st.dataframe(df, use_container_width=True)

    # Show export path when workflow wrote a table/CSV file
    download_info = _first_table_download_info(final)
    if download_info:
        file_path, download_mime = download_info
        st.success(f"💾 Full data saved to: {file_path}")

        # Add download button
        label = (
            "📥 Download CSV"
            if download_mime == "text/csv"
            else "📥 Download table export"
        )
        try:
            with open(file_path, "rb") as f:
                st.download_button(
                    label=label,
                    data=f.read(),
                    file_name=Path(file_path).name,
                    mime=download_mime,
                )
        except FileNotFoundError:
            st.warning("File not found for download")


def display_not_census_streamlit(final: FinalResponseState | None = None) -> None:
    """Display a non-Census response"""

    if final is None:
        st.warning("No non-Census response to display")
        return

    if not isinstance(final, FinalResponseState):
        st.warning("Invalid non-Census response type")
        return

    answer_text = final.answer_text if final.answer_text else "I can't help with that."

    st.info(f"ℹ️ {answer_text}")


def display_clarification_streamlit(
    plan: WorkflowPlanState | None = None,
    final: FinalResponseState | None = None,
) -> None:
    """Display clarification request"""
    if plan is None or final is None:
        st.warning("No clarification request to display")
        return

    if not isinstance(plan, WorkflowPlanState):
        st.warning("Invalid clarification plan type")
        return

    if not isinstance(final, FinalResponseState):
        st.warning("Invalid clarification final response type")
        return

    message, clarification_needed = _clarification_question_and_options(plan, final)

    st.warning(f"❓ {message}")

    if clarification_needed:
        st.write("Please provide:")
        for i, item in enumerate(clarification_needed, 1):
            st.write(f"{i}. {item}")


def process_question(user_input: str) -> CensusState | dict[str, Any]:
    """Process a user question through the LangGraph workflow"""

    try:
        logger.info(f"Processing question: {user_input}")
        # Ensure session state is initialized
        initialize_session_state()

        # Create initial state
        initial_state = CensusState(
            messages=[{"role": "user", "content": user_input}],
            original_query=user_input,
            intent=None,
            geo={},
            candidates={},
            plan=None,
            artifacts=WorkflowArtifactsState(),
            final=None,
            logs=[],
            error=None,
            summary=None,
            profile={},
            history=[],
            cache_index={},
        )

        # Create config
        config = RunnableConfig(
            configurable={
                "user_id": st.session_state.user_id,
                "thread_id": st.session_state.thread_id,
            }
        )

        # Process through graph
        result = st.session_state.graph.invoke(initial_state, config)
        census_state = CensusState.model_validate(result)

        # PdfConversationEntry shape only (session PDF + sidebar); no duplicate top-level keys.
        st.session_state.conversation_history.append(
            {
                "question": user_input,
                "timestamp": datetime.now(),
                "result": pdf_conversation_result_dict(census_state),
            }
        )

        return census_state

    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        return {"error": f"Error processing question: {str(e)}"}


def main():
    """Main Streamlit application"""

    # Initialize session state
    initialize_session_state()

    # Header
    st.title("🏛️ Census Data Assistant")
    st.markdown(
        "Ask questions about US Census data and get instant answers with visualizations!"
    )

    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")

        # User settings
        st.session_state.user_id = st.text_input(
            "User ID",
            value=st.session_state.user_id,
            help="Enter your user ID for personalized responses",
        )

        st.session_state.thread_id = st.text_input(
            "Thread ID",
            value=st.session_state.thread_id,
            help="Enter thread ID to continue conversations",
        )

        # Display log file location
        if st.session_state.log_file_path:
            st.info(f"📝 Session logging to:\n`{st.session_state.log_file_path}`")

        # Clear conversation button
        if st.button("🗑️ Clear Conversation"):
            st.session_state.conversation_history = []
            st.session_state.current_result = None
            st.rerun()

        # Add PDF export section
        st.sidebar.markdown("---")
        st.sidebar.subheader("📄 Session Export")

        if st.session_state.conversation_history:
            if st.sidebar.button("📥 Download Session as PDF", type="primary"):
                try:
                    pdf_bytes = generate_session_pdf(
                        conversation_history=st.session_state.conversation_history,
                        user_id=st.session_state.user_id or "demo",
                        session_metadata=PdfSessionMetadata(
                            thread_id=st.session_state.thread_id,
                        ),
                    )

                    st.sidebar.download_button(
                        label="📥 Download PDF",
                        data=pdf_bytes,
                        file_name=f"census_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                    )
                    st.sidebar.success("PDF ready for download!")

                except Exception as e:
                    st.sidebar.error(f"PDF generation failed: {e}")
        else:
            st.sidebar.info("No conversations to export yet")

        # Conversation history
        if st.session_state.conversation_history:
            st.header("📜 Conversation History")
            for i, entry in enumerate(st.session_state.conversation_history[-5:]):
                with st.expander(f"Q{i + 1}: {entry['question'][:50]}..."):
                    st.text(f"Question: {entry['question']}")
                    try:
                        kind = history_entry_presentation_kind(entry)
                        st.text(f"Presentation: {kind.value}")
                        hist_state = census_state_from_pdf_history_entry(entry)
                        if hist_state.final and hist_state.final.answer_text:
                            ans = hist_state.final.answer_text
                            st.text(f"Answer preview: {ans[:200]}{'…' if len(ans) > 200 else ''}")
                    except Exception as ex:
                        logger.warning("Sidebar history preview failed: %s", ex)
                        st.text("Presentation: (unavailable)")

    # Main interface
    st.header("💬 Ask a Question")

    # Example questions
    st.markdown("**Example questions:**")
    examples = [
        "What's the population of New York City?",
        "Show me median income trends from 2015 to 2020",
        "Compare population by county in California",
        "What's the median income in Los Angeles County?",
    ]

    # Create columns for example buttons
    cols = st.columns(2)
    for i, example in enumerate(examples):
        with cols[i % 2]:
            if st.button(f"📝 {example}", key=f"example_{i}"):
                st.session_state.example_question = example

    # Text input
    user_input = st.text_input(
        "Your question:",
        value=st.session_state.get("example_question", ""),
        placeholder="Ask me about Census data...",
        help="Type your question about Census data here",
    )

    # Debug info
    st.write(f"Debug: user_input = '{user_input}'")
    st.write(f"Debug: user_input.strip() = '{user_input.strip()}'")
    st.write(
        f"Debug: example_question in session_state = {'example_question' in st.session_state}"
    )

    # Process button
    if st.button("🔍 Ask Question", type="primary") and user_input.strip():
        st.write(f"Debug: Button clicked with input: '{user_input.strip()}'")
        with st.spinner("🔍 Processing your question..."):
            result = process_question(user_input.strip())
            st.session_state.current_result = result

        # Display results
        display_streamlit_results(result)

        # Clear example question after use
        if "example_question" in st.session_state:
            del st.session_state.example_question

    # Display current result if available
    elif st.session_state.current_result:
        display_streamlit_results(st.session_state.current_result)

    # Footer
    st.markdown("---")
    st.markdown(
        "💡 **Tip:** Use the CLI interface (`uv run python main.py`) for advanced features and scripting. "
        "This web interface provides the same functionality with visual enhancements."
    )


if __name__ == "__main__":
    main()

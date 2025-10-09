"""
Streamlit Web Interface for Census Data Assistant

This provides a web-based interface alongside the existing CLI interface (main.py).
Both interfaces use the same underlying LangGraph workflow and processing logic.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
import logging
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from app import create_census_graph
from src.state.types import CensusState
from langchain_core.runnables import RunnableConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Census Data Assistant",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


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


def display_streamlit_results(result: Dict[str, Any]):
    """Display results using Streamlit components"""

    if not result:
        st.error("No results to display")
        return

    # Check for errors
    if result.get("error"):
        st.error(f"❌ Error: {result['error']}")
        return

    # Display final answer
    final = result.get("final")
    if not final:
        st.warning("❌ No answer available")
        return

    # Display answer type
    answer_type = final.get("type", "Unknown")

    # Create columns for better layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 Census Data Results")

        if answer_type == "single":
            display_single_value_streamlit(final)
        elif answer_type == "series":
            display_series_streamlit(final)
        elif answer_type == "table":
            display_table_streamlit(final)
        elif answer_type == "not_census":
            display_not_census_streamlit(final)
        elif answer_type == "clarification":
            display_clarification_streamlit(final)
        else:
            st.info(f"Answer: {final}")

    with col2:
        # Display footnotes
        footnotes = final.get("footnotes", [])
        if footnotes:
            st.subheader("📝 Footnotes")
            for i, footnote in enumerate(footnotes):
                st.caption(f"{i + 1}. {footnote}")

        # Display system logs
        logs = result.get("logs", [])
        if logs:
            with st.expander("🔍 System Logs"):
                for log in logs[-5:]:  # Show last 5 logs
                    st.text(log)


def display_single_value_streamlit(final: Dict[str, Any]):
    """Display a single value answer with Streamlit components"""

    value = final.get("value", "N/A")
    geo = final.get("geo", "Unknown location")
    year = final.get("year", "Unknown year")
    variable = final.get("variable", "Unknown variable")

    # Create metrics display
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📍 Location", geo)

    with col2:
        st.metric("📅 Year", year)

    with col3:
        st.metric("📊 Value", value)

    if variable != "Unknown variable":
        st.info(f"🔢 Variable: {variable}")


def display_series_streamlit(final: Dict[str, Any]):
    """Display a time series answer with interactive chart"""

    data = final.get("data", [])
    geo = final.get("geo", "Unknown location")
    variable = final.get("variable", "Unknown variable")

    if not data:
        st.warning("No data available")
        return

    # Convert to DataFrame for easier handling
    df_data = []
    for item in data:
        df_data.append(
            {
                "Year": item.get("year", "Unknown"),
                "Value": item.get("value", 0),
                "Formatted Value": item.get(
                    "formatted_value", str(item.get("value", 0))
                ),
            }
        )

    df = pd.DataFrame(df_data)

    # Display summary
    st.info(f"📍 Location: {geo}")
    st.info(f"🔢 Variable: {variable}")

    # Create interactive line chart
    fig = px.line(
        df,
        x="Year",
        y="Value",
        title=f"{variable} Trends for {geo}",
        labels={"Value": "Value", "Year": "Year"},
    )

    fig.update_layout(xaxis_title="Year", yaxis_title="Value", hovermode="x unified")

    st.plotly_chart(fig, use_container_width=True)

    # Display data table
    st.subheader("📈 Data Table")
    st.dataframe(df, use_container_width=True)

    # Show file path if available
    file_path = final.get("file_path")
    if file_path:
        st.success(f"💾 Full data saved to: {file_path}")

        # Add download button
        try:
            with open(file_path, "rb") as f:
                st.download_button(
                    label="📥 Download CSV",
                    data=f.read(),
                    file_name=Path(file_path).name,
                    mime="text/csv",
                )
        except FileNotFoundError:
            st.warning("File not found for download")


def display_table_streamlit(final: Dict[str, Any]):
    """Display a table answer with interactive table"""

    data = final.get("data", [])
    total_rows = final.get("total_rows", 0)
    columns = final.get("columns", [])

    st.info(f"📊 Table Data ({total_rows} rows)")

    if not data:
        st.warning("No data available")
        return

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Display interactive table
    st.dataframe(df, use_container_width=True)

    # Show file path if available
    file_path = final.get("file_path")
    if file_path:
        st.success(f"💾 Full data saved to: {file_path}")

        # Add download button
        try:
            with open(file_path, "rb") as f:
                st.download_button(
                    label="📥 Download CSV",
                    data=f.read(),
                    file_name=Path(file_path).name,
                    mime="text/csv",
                )
        except FileNotFoundError:
            st.warning("File not found for download")


def display_not_census_streamlit(final: Dict[str, Any]):
    """Display a non-Census response"""

    message = final.get("message", "I can't help with that.")
    suggestion = final.get("suggestion", "")

    st.info(f"ℹ️ {message}")
    if suggestion:
        st.info(f"💡 {suggestion}")


def display_clarification_streamlit(final: Dict[str, Any]):
    """Display clarification request"""

    message = final.get("message", "I need more information.")
    clarification_needed = final.get("clarification_needed", [])

    st.warning(f"❓ {message}")

    if clarification_needed:
        st.write("Please provide:")
        for i, item in enumerate(clarification_needed, 1):
            st.write(f"{i}. {item}")


def process_question(user_input: str) -> Dict[str, Any]:
    """Process a user question through the LangGraph workflow"""

    try:
        # Create initial state
        initial_state = CensusState(
            messages=[{"role": "user", "content": user_input}],
            intent=None,
            geo={},
            candidates={},
            plan=None,
            artifacts={},
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

        # Add to conversation history
        st.session_state.conversation_history.append(
            {"question": user_input, "result": result, "timestamp": pd.Timestamp.now()}
        )

        return result

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

        # Clear conversation button
        if st.button("🗑️ Clear Conversation"):
            st.session_state.conversation_history = []
            st.session_state.current_result = None
            st.rerun()

        # Conversation history
        if st.session_state.conversation_history:
            st.header("📜 Conversation History")
            for i, entry in enumerate(st.session_state.conversation_history[-5:]):
                with st.expander(f"Q{i + 1}: {entry['question'][:50]}..."):
                    st.text(f"Question: {entry['question']}")
                    if entry["result"].get("final"):
                        st.text(
                            f"Answer: {entry['result']['final'].get('type', 'Unknown')}"
                        )

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

    # Clear example question after use
    if "example_question" in st.session_state:
        del st.session_state.example_question

    # Process button
    if st.button("🔍 Ask Question", type="primary") and user_input.strip():
        with st.spinner("🔍 Processing your question..."):
            result = process_question(user_input.strip())
            st.session_state.current_result = result

        # Display results
        display_streamlit_results(result)

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


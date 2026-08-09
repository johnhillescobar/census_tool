import logging
import os
import sqlite3

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

# Import state and routing
from src.state.types import CensusState

# Import all workflows
from src.workflows import (
    agent_planning_node,
    agent_reasoning_node,
    benchmark_node,
    comparison_metrics_node,
    comparison_node,
    geography_node,
    geography_resume_node,
    memory_load_node,
    memory_write_node,
    output_node,
    temporal_node,
)

logger = logging.getLogger(__name__)


def create_viz_graph(compiled_graph):
    # Keep graph visualization logic

    try:
        compiled_graph.get_graph(xray=True).draw_mermaid_png(output_file_path="graph.png")

        logger.info("Graph visualization saved to graph.png")

    except Exception as e:
        logger.warning(f"Could not generate graph visualization: {e}")

    return compiled_graph


def _route_after_geography(state: CensusState) -> str:
    if state.plan and (state.plan.requires_clarification or state.plan.workflow_cancelled):
        return "output"

    return "benchmark"


def _route_after_memory(state: CensusState) -> str:
    if state.plan and state.plan.pending_geography_clarification:
        return "geography_resume"
    return "temporal"


def _route_after_temporal(state: CensusState) -> str:
    if state.plan and state.plan.requires_clarification:
        return "output"

    return "agent_planning"


def _route_after_agent_planning(state: CensusState) -> str:
    if state.plan and state.plan.requires_clarification:
        return "output"

    return "geography"


def _route_after_benchmark(state: CensusState) -> str:
    if state.plan and state.plan.requires_clarification:
        return "output"

    if state.plan and state.plan.benchmark_is_not_applicable():
        return "agent"

    return "comparison"


def _route_after_comparison(state: CensusState) -> str:
    if state.plan and state.plan.requires_clarification:
        return "output"

    return "agent"


def _route_after_agent(state: CensusState) -> str:
    if state.plan and state.plan.requires_clarification:
        return "output"

    return "comparison_metrics"


def create_census_graph():
    # Reducers are defined on CensusState via Annotated types (see src/state/types.py).

    workflow = StateGraph(CensusState)

    # Workflow nodes

    workflow.add_node("memory_load", memory_load_node)

    workflow.add_node("geography", geography_node)
    workflow.add_node("geography_resume", geography_resume_node)

    workflow.add_node("temporal", temporal_node)

    workflow.add_node("agent_planning", agent_planning_node)

    workflow.add_node("benchmark", benchmark_node)

    workflow.add_node("comparison", comparison_node)

    workflow.add_node("agent", agent_reasoning_node)

    workflow.add_node("comparison_metrics", comparison_metrics_node)

    workflow.add_node("output", output_node)

    workflow.add_node("memory_write", memory_write_node)

    workflow.set_entry_point("memory_load")

    workflow.add_conditional_edges(
        "memory_load",
        _route_after_memory,
        {"temporal": "temporal", "geography_resume": "geography_resume"},
    )
    workflow.add_conditional_edges(
        "geography_resume",
        _route_after_geography,
        {"benchmark": "benchmark", "output": "output"},
    )

    workflow.add_conditional_edges(
        "geography",
        _route_after_geography,
        {"benchmark": "benchmark", "output": "output"},
    )

    workflow.add_conditional_edges(
        "temporal",
        _route_after_temporal,
        {"agent_planning": "agent_planning", "output": "output"},
    )

    workflow.add_conditional_edges(
        "agent_planning",
        _route_after_agent_planning,
        {"geography": "geography", "output": "output"},
    )

    workflow.add_conditional_edges(
        "benchmark",
        _route_after_benchmark,
        {"comparison": "comparison", "agent": "agent", "output": "output"},
    )

    workflow.add_conditional_edges(
        "comparison",
        _route_after_comparison,
        {"agent": "agent", "output": "output"},
    )

    workflow.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"comparison_metrics": "comparison_metrics", "output": "output"},
    )

    workflow.add_edge("comparison_metrics", "output")

    workflow.add_edge("output", "memory_write")

    workflow.add_edge("memory_write", "__end__")

    # Compile the graph first

    try:
        db_path = os.environ.get("CENSUS_CHECKPOINT_DB", "checkpoints.db")

        if os.environ.get("CENSUS_RESET_CHECKPOINTS") == "1" and os.path.exists(db_path):
            logger.info("Removing checkpoints because CENSUS_RESET_CHECKPOINTS=1")

            try:
                os.remove(db_path)

                logger.info(f"Removed {db_path}")

            except Exception as e:
                logger.warning(f"Could not remove old checkpoints: {e}")

        # Create fresh SQLite connection

        conn = sqlite3.connect(db_path, check_same_thread=False)

        checkpointer = SqliteSaver(conn)

        logger.info("SQLite checkpointer initialized for agent architecture")

        compiled_graph = workflow.compile(checkpointer=checkpointer)

        create_viz_graph(compiled_graph)

        return compiled_graph

    except Exception as e:
        logger.error(f"Failed to initialize SQLite checkpointer: {e}")

        logger.info("Falling back to memory checkpointer (no persistence)")

        try:
            checkpointer = MemorySaver()

            compiled_graph = workflow.compile(checkpointer=checkpointer)

            create_viz_graph(compiled_graph)

            return compiled_graph

        except Exception as e2:
            logger.error(f"Memory checkpointer also failed: {e2}")

            compiled_graph = workflow.compile()

            create_viz_graph(compiled_graph)

            return compiled_graph

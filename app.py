from typing import List, Dict, Any
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import os
from langgraph.checkpoint.memory import MemorySaver

# Import state and routing
from src.state.types import CensusState

# Import all nodes
from src.nodes.memory import memory_load_node, memory_write_node
from src.nodes.agent import agent_reasoning_node
from src.nodes.output import output_node

import logging

logger = logging.getLogger(__name__)


def create_viz_graph(compiled_graph):
    # Keep graph visualization logic
    try:
        compiled_graph.get_graph().draw_mermaid_png(output_file_path="graph.png")
        logger.info("Graph visualization saved to graph.png")
    except Exception as e:
        logger.warning(f"Could not generate graph visualization: {e}")

    return compiled_graph


def create_reducers():
    def append_reducer(existing: List[str], new: List[str]) -> List[str]:
        """Append new items to existing list"""
        if existing is None:
            return new
        return existing + new

    def overwrite_reducer(existing: Any, new: Any) -> Any:
        """Overwrite existing item with new value"""
        return new

    def merge_reducer(existing: Dict, new: Dict) -> Dict:
        """Merge new dictionary into existing one"""
        if existing is None:
            return new
        result = existing.copy()
        result.update(new)
        return result

    return {
        "messages": append_reducer,
        "intent": overwrite_reducer,
        "geo": overwrite_reducer,
        "candidates": overwrite_reducer,
        "plan": overwrite_reducer,
        "artifacts": merge_reducer,
        "final": overwrite_reducer,
        "logs": append_reducer,
        "error": overwrite_reducer,
        "summary": overwrite_reducer,
        "profile": merge_reducer,
        "history": append_reducer,
        "cache_index": merge_reducer,
    }


def create_census_graph():
    workflow = StateGraph(CensusState, reducers=create_reducers())

    # Only 4 nodes
    workflow.add_node("memory_load", memory_load_node)
    workflow.add_node("agent", agent_reasoning_node)
    workflow.add_node("output", output_node)
    workflow.add_node("memory_write", memory_write_node)

    # Linear flow - no conditional routing
    workflow.set_entry_point("memory_load")
    workflow.add_edge("memory_load", "agent")
    workflow.add_edge("agent", "output")
    workflow.add_edge("output", "memory_write")
    workflow.add_edge("memory_write", "__end__")

    # Compile the graph first
    try:
        db_path = "checkpoints.db"

        # Reset checkpoints for clean architecture change
        # Delete existing checkpoints to avoid node structure conflicts
        if os.path.exists(db_path):
            logger.info("Removing old checkpoints for agent architecture migration")
            try:
                os.remove(db_path)
                logger.info(
                    f"Removed {db_path} - starting fresh with agent architecture"
                )
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

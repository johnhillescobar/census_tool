from typing import List, Dict, Any
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

# Import state and routing
from src.state.types import CensusState
from src.state.routing import (
    should_summarize,
    route_from_intent,
    route_from_retrieve,
    route_from_plan,
    route_from_data,
    route_from_answer,
)

# Import all nodes
from src.nodes.memory import memory_load_node, memory_write_node
from src.nodes.intent import intent_node, router_from_intent_node, clarify_node
from src.nodes.geo import geo_node
from src.nodes.retrieve import retrieve_node, plan_node
from src.nodes.data import data_node
from src.nodes.answer import answer_node, not_census_node
from src.nodes.utils.summarizer import summarizer_node


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
    """Create the Census QA graph with complete control flow"""

    # Create state graph with reducers
    reducers = create_reducers()
    workflow = StateGraph(CensusState, reducers=reducers)

    # Add nodes (we'll implement these next)
    workflow.add_node("memory_load", memory_load_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("intent", intent_node)
    workflow.add_node("router", router_from_intent_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("geo", geo_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("data", data_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("memory_write", memory_write_node)
    workflow.add_node("not_census", not_census_node)

    # Set entry point
    workflow.set_entry_point("memory_load")

    # Add conditional edges
    workflow.add_conditional_edges(
        "memory_load",
        should_summarize,  # Function that returns next node
        {"summarizer": "summarizer", "intent": "intent"},
    )

    workflow.add_edge("summarizer", "intent")
    workflow.add_edge("intent", "router")

    workflow.add_conditional_edges(
        "router",
        route_from_intent,
        {"not_census": "not_census", "clarify": "clarify", "geo": "geo"},
    )

    workflow.add_edge("geo", "retrieve")

    workflow.add_conditional_edges(
        "retrieve",
        route_from_retrieve,
        {"clarify": "clarify", "plan": "plan"},
    )

    workflow.add_conditional_edges(
        "plan",
        route_from_plan,
        {"clarify": "clarify", "data": "data"},
    )

    workflow.add_conditional_edges(
        "data",
        route_from_data,
        {"clarify": "clarify", "answer": "answer"},
    )

    workflow.add_conditional_edges(
        "answer", route_from_answer, {"memory_write": "memory_write"}
    )

    workflow.add_edge("memory_write", "__end__")
    workflow.add_edge("not_census", "__end__")
    workflow.add_edge("clarify", "__end__")

    # Compile the graph
    workflow.get_graph().draw_mermaid_png(output_file_path="graph.png")
    return workflow.compile(checkpointer=SqliteSaver.from_conn_string("checkpoints.db"))

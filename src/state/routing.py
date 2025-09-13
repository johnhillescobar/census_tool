from src.state.types import CensusState
from config import MESSAGE_THRESHOLD


def should_summarize(state: CensusState) -> str:
    """Determine if summarization is needed"""
    messages = state.get("messages", [])
    if len(messages) > MESSAGE_THRESHOLD:
        return "summarizer"
    return "intent"


def route_from_intent(state: CensusState) -> str:
    """Route based on intent analysis"""
    intent = state.get("intent", {})

    if not intent.get("is_census", False):
        return "not_census"
    elif intent.get("needs_clarification", False):
        return "clarify"
    else:
        return "geo"


def route_from_retrieve(state: CensusState) -> str:
    """Route after retrieval based on confidence"""
    candidates = state.get("candidates", {})
    variables = candidates.get("variables", [])

    if not variables:
        return "clarify"  # No candidates found
    else:
        return "plan"


def route_from_plan(state: CensusState) -> str:
    """Route after planning"""
    plan = state.get("plan", {})
    queries = plan.get("queries", [])

    if not queries:
        return "clarify"  # No valid plan
    else:
        return "data"


def route_from_data(state: CensusState) -> str:
    """Route after data fetching"""
    artifacts = state.get("artifacts", {})
    datasets = artifacts.get("datasets", {})

    if not datasets:
        return "clarify"  # No data retrieved
    else:
        return "answer"


def route_from_answer(state: CensusState) -> str:
    """Route after answering"""
    return "memory_write"

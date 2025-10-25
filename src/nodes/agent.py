import os
import sys
import logging

from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import CensusState
from src.utils.agents.census_query_agent import CensusQueryAgent

logger = logging.getLogger(__name__)


def agent_reasoning_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    user_question = state.messages[-1]["content"]
    profile = state.profile

    # Agent expects intent dict - create basic one if not exists
    intent = state.intent or {"is_census": True, "topic": "general"}

    agent = CensusQueryAgent()
    result = agent.solve(user_query=user_question, intent=intent)

    return {
        "artifacts": {
            "census_data": result.get("census_data", {}),
            "data_summary": result.get("data_summary", ""),
            "reasoning_trace": result.get("reasoning_trace", ""),
        },
        "final": {
            "answer_text": result.get("answer_text"),
            "charts_needed": result.get("charts_needed", []),
            "tables_needed": result.get("tables_needed", []),
        },
        "logs": ["agent: completed reasoning with data"],
    }

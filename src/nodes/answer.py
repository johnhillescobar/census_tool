from typing import Dict, Any
from app import CensusState


def answer_node(state: CensusState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Answer the user's question"""

    # TODO: Implement answer node

    return {"logs": ["answer: placeholder"]}


def not_census_node(state: CensusState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a message indicating the question is not related to Census"""

    # TODO: Implement not_census node

    return {"logs": ["not_census: placeholder"]}

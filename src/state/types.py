from typing import TypedDict, List, Dict, Optional, Any


# Define the state schema
class CensusState(TypedDict):
    # Core conversation data
    messages: List[Dict[str, Any]]  # Chat turns; reducer: append.
    intent: Optional[Dict[str, Any]]  # Intent analysis; reducer; overwrite.
    geo: Dict[str, Any]  # Geo resolution; reducer; overwrite.
    candidates: Dict[str, Any]  # Candidate variables; reducer; overwrite.
    plan: Optional[Dict[str, Any]]  # Query plan; reducer; overwrite.
    artifacts: Dict[
        str, Any
    ]  # Dataset and preview handles; reducer; merge dictionaries.
    final: Optional[Dict[str, Any]]  # Final answer; reducer; overwrite.

    # System data
    logs: List[str]  # System logs; reducer: append.
    error: Optional[str]  # Error message; reducer; overwrite.
    summary: Optional[str]  # Message summary; reducer; overwrite.

    # Mmemory and persistence
    profile: Dict[str, Any]  # User profile; reducer; merge dictionaries.
    history: List[Dict[str, Any]]  # Conversation history; reducer; append.
    cache_index: Dict[str, Any]  # Cache index; reducer; merge dictionaries.


class QuerySpec(TypedDict):
    year: int
    dataset: str
    variables: List[str]
    geo: Dict[str, Any]
    save_as: str

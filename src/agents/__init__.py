from typing import Any

__all__ = ["CensusQueryAgent"]


def __getattr__(name: str) -> Any:
    if name == "CensusQueryAgent":
        from .census_query_agent import CensusQueryAgent

        return CensusQueryAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

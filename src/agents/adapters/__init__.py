"""Adapters bridging modern LangChain agents to legacy parser contracts."""

from src.agents.adapters.message_to_executor import message_trace_to_executor_result

__all__ = ["message_trace_to_executor_result"]

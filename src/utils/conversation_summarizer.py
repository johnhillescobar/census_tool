"""
Conversation summarization to prevent context length overflow.

Monitors token count in agent conversation history and summarizes
old tool outputs when approaching the model's context limit.
"""

import logging
import json
from typing import List, Dict, Any
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token for English text.
    This is conservative - actual tokenization may differ.
    """
    return len(text) // 4


def summarize_tool_output(tool_name: str, tool_input: str, observation: str) -> str:
    """
    Summarize a single tool call and its output.
    Keep essential information, discard verbose details.
    """
    # Parse tool input if it's JSON
    try:
        input_dict = json.loads(tool_input)
        input_summary = ", ".join(f"{k}={v}" for k, v in list(input_dict.items())[:3])
    except Exception as e:
        logger.warning(f"Error parsing tool input: {e}")
        input_summary = tool_input[:100]

    # Summarize observation
    obs_length = len(observation)
    if obs_length > 500:
        # For large outputs, just keep metadata
        if "success" in observation.lower():
            obs_summary = f"[Success response, {obs_length} chars]"
        elif "error" in observation.lower():
            obs_summary = f"[Error response: {observation[:200]}...]"
        else:
            obs_summary = f"[Large response, {obs_length} chars, first 100: {observation[:100]}...]"
    else:
        obs_summary = observation

    return f"Tool: {tool_name}({input_summary}) → {obs_summary}"


class ConversationSummarizer(BaseCallbackHandler):
    """
    Callback handler that monitors conversation token count and
    summarizes old messages when approaching context limit.
    """

    def __init__(self, token_threshold: int = 100000, keep_recent: int = 5):
        """
        Args:
            token_threshold: Trigger summarization when exceeding this many tokens
            keep_recent: Number of recent tool calls to keep in full detail
        """
        self.token_threshold = token_threshold
        self.keep_recent = keep_recent
        self.current_messages: List[str] = []
        self.summarized = False

    def on_agent_action(self, action, **kwargs) -> None:
        """Called when agent takes an action (tool call)"""
        # Track the action
        tool_name = action.tool
        tool_input = str(action.tool_input)
        self.current_messages.append(f"Action: {tool_name}({tool_input[:200]})")

    def on_tool_end(self, output: str, **kwargs) -> None:
        """Called when a tool finishes"""
        # Track the observation
        self.current_messages.append(f"Observation: {output[:500]}")

        # Check if we need to summarize
        total_text = "\n".join(self.current_messages)
        estimated_tokens = estimate_tokens(total_text)

        if estimated_tokens > self.token_threshold and not self.summarized:
            logger.warning(
                f"Conversation approaching token limit ({estimated_tokens} tokens). "
                "Summarization would be triggered in production."
            )
            # Note: Actual summarization would require modifying the agent's message list
            # which is not directly accessible from the callback.
            # This serves as a monitoring/logging mechanism.
            self.summarized = True


def summarize_intermediate_steps(
    intermediate_steps: List[tuple], keep_recent: int = 5
) -> List[tuple]:
    """
    Summarize old intermediate steps, keeping only recent ones in full detail.

    Args:
        intermediate_steps: List of (AgentAction, observation) tuples
        keep_recent: Number of recent steps to keep unchanged

    Returns:
        Summarized list of intermediate steps
    """
    if len(intermediate_steps) <= keep_recent:
        return intermediate_steps

    # Keep recent steps unchanged
    recent_steps = intermediate_steps[-keep_recent:]
    old_steps = intermediate_steps[:-keep_recent]

    # Summarize old steps
    summarized_old = []
    for action, observation in old_steps:
        tool_name = action.tool
        tool_input = str(action.tool_input)

        # Create a summarized observation
        summary = summarize_tool_output(tool_name, tool_input, str(observation))

        # Keep the action but replace observation with summary
        summarized_old.append((action, summary))

    logger.info(
        f"Summarized {len(old_steps)} old tool calls, "
        f"kept {len(recent_steps)} recent calls in full detail"
    )

    return summarized_old + recent_steps


def trim_messages_by_tokens(
    messages: List[Dict[str, Any]], max_tokens: int = 100000, keep_system: bool = True
) -> List[Dict[str, Any]]:
    """
    Trim message list to stay under token limit.

    Args:
        messages: List of message dictionaries
        max_tokens: Maximum total tokens to keep
        keep_system: Always keep the first system message

    Returns:
        Trimmed message list
    """
    if not messages:
        return messages

    # Calculate current token count
    total_text = "\n".join(str(msg.get("content", "")) for msg in messages)
    current_tokens = estimate_tokens(total_text)

    if current_tokens <= max_tokens:
        return messages

    logger.warning(
        f"Message list exceeds {max_tokens} tokens ({current_tokens} estimated). "
        "Trimming old messages."
    )

    # Keep system message and recent messages
    result = []
    if keep_system and messages[0].get("role") == "system":
        result.append(messages[0])
        remaining_messages = messages[1:]
    else:
        remaining_messages = messages

    # Add messages from the end until we hit the limit
    accumulated_tokens = (
        estimate_tokens(str(result[0].get("content", ""))) if result else 0
    )

    for msg in reversed(remaining_messages):
        msg_tokens = estimate_tokens(str(msg.get("content", "")))
        if accumulated_tokens + msg_tokens > max_tokens:
            break
        result.insert(1 if keep_system else 0, msg)
        accumulated_tokens += msg_tokens

    logger.info(
        f"Trimmed from {len(messages)} to {len(result)} messages "
        f"({current_tokens} → ~{accumulated_tokens} tokens)"
    )

    return result

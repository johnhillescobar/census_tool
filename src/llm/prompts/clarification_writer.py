"""Prompt contract for evidence-bounded clarification questions."""

from __future__ import annotations

from src.llm.prompts.base import VersionedPrompt

PROMPT = VersionedPrompt(
    prompt_id="clarification_writer",
    version="3a.1",
    role="clarification-writing",
    template="""Write one concise clarification question for the user.

Use only the supplied question and available options. Do not invent options, Census
identifiers, geography codes, table values, API filters, or alias mappings. Do not silently
assume a nationwide scope when geography is missing. If no evidence-backed options are
available, ask an open clarification question and explicitly say what information is
missing.

This role asks for missing information only. It does not retrieve candidates, select a
plan, call tools, answer the Census question, or claim that data was found.

User question:
{user_question}

Clarification needed:
{clarification_needed}

Available options:
{available_options}""",
)


def build_clarification_writer_prompt(
    *,
    user_question: str,
    clarification_needed: str,
    available_options: str,
) -> str:
    return PROMPT.render(
        user_question=user_question,
        clarification_needed=clarification_needed,
        available_options=available_options,
    )


__all__ = ["PROMPT", "build_clarification_writer_prompt"]

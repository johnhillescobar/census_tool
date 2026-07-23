"""Prompt contract for writing an answer from validated evidence."""

from __future__ import annotations

from src.llm.prompts.base import VersionedPrompt

PROMPT = VersionedPrompt(
    prompt_id="answer_writer",
    version="3a.1",
    role="answer-writing",
    template="""Write a concise, professional answer using only the supplied validated data.

Do not retrieve, select candidates, call tools, alter the plan, or infer missing Census
values. Do not invent Census identifiers, geography codes, table values, API filters,
citations, or alias mappings. Do not silently assume a nationwide scope. If the supplied
data is missing, unsuccessful, or insufficient to answer the question, state that failure
explicitly and make no unsupported factual claim.

Include useful year and geography context only when present in the evidence. Mention
limitations supported by the evidence. Keep the answer under 250 words.

User question:
{user_question}

Answer type:
{answer_type}

Validated data summary:
{data_summary}

Validated geographic context:
{geo_context}""",
)


def build_answer_writer_prompt(
    *,
    user_question: str,
    answer_type: str,
    data_summary: str,
    geo_context: str,
) -> str:
    return PROMPT.render(
        user_question=user_question,
        answer_type=answer_type,
        data_summary=data_summary,
        geo_context=geo_context,
    )


__all__ = ["PROMPT", "build_answer_writer_prompt"]

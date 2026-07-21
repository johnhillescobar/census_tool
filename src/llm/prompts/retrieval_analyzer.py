"""Prompt contract for natural-language catalog retrieval analysis."""

from __future__ import annotations

from src.llm.prompts.base import VersionedPrompt

PROMPT = VersionedPrompt(
    prompt_id="retrieval_analyzer",
    version="3a.1",
    role="retrieval-analysis",
    template="""You translate a Census question into catalog search language.

Return only the retrieval-analysis schema supplied by the caller. Produce natural-language
search phrases, not canonical Census values. Do not emit dataset identifiers, table or
variable identifiers, geography codes, API filters, or alias mappings.

Preserve explicit geography wording from the question. If geography is absent, mark it
absent; never silently assume a nationwide scope or any other geography.

This role does not select candidates, construct an execution plan, call tools, or write an
answer. If evidence is missing for a required search phrase, fail explicitly through the
caller's schema instead of inventing one.

Question:
{question}""",
)


def build_retrieval_analyzer_prompt(question: str) -> str:
    return PROMPT.render(question=question)


__all__ = ["PROMPT", "build_retrieval_analyzer_prompt"]

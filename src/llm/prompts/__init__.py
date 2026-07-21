"""Versioned prompt inventory for Phase 3A."""

from __future__ import annotations

from types import MappingProxyType

from src.llm.prompts.answer_writer import PROMPT as ANSWER_WRITER_PROMPT
from src.llm.prompts.clarification_writer import PROMPT as CLARIFICATION_WRITER_PROMPT
from src.llm.prompts.execution_agent import PROMPT as EXECUTION_AGENT_PROMPT
from src.llm.prompts.grounded_selector import PROMPT as GROUNDED_SELECTOR_PROMPT
from src.llm.prompts.retrieval_analyzer import PROMPT as RETRIEVAL_ANALYZER_PROMPT

# "active" means invoked by current runtime code. Retrieval analysis and grounded
# selection remain deterministic in Phase 3A; their prompt contracts are staged only.
PROMPT_INVENTORY = MappingProxyType(
    {
        "retrieval_analyzer": {
            "prompt": RETRIEVAL_ANALYZER_PROMPT,
            "status": "defined_not_wired",
            "runtime": "DeterministicCensusRetrievalAnalyzer",
        },
        "grounded_selector": {
            "prompt": GROUNDED_SELECTOR_PROMPT,
            "status": "defined_not_wired",
            "runtime": "select_grounded_plan",
        },
        "execution_agent": {
            "prompt": EXECUTION_AGENT_PROMPT,
            "status": "active",
            "runtime": "CensusQueryAgent",
        },
        "clarification_writer": {
            "prompt": CLARIFICATION_WRITER_PROMPT,
            "status": "active",
            "runtime": "generate_intelligent_clarification",
        },
        "answer_writer": {
            "prompt": ANSWER_WRITER_PROMPT,
            "status": "active",
            "runtime": "generate_llm_answer",
        },
    }
)

LEGACY_ACTIVE_PROMPTS = MappingProxyType(
    {
        "intent_analysis": "src.llm.config.INTENT_PROMPT_TEMPLATE",
        "category_detection": "src.llm.config.CATEGORY_DETECTION_PROMPT_TEMPLATE",
        "geography_resolution": "src.llm.geography_resolver.GeographyResolver.prompt_template",
    }
)

__all__ = [
    "ANSWER_WRITER_PROMPT",
    "CLARIFICATION_WRITER_PROMPT",
    "EXECUTION_AGENT_PROMPT",
    "GROUNDED_SELECTOR_PROMPT",
    "LEGACY_ACTIVE_PROMPTS",
    "PROMPT_INVENTORY",
    "RETRIEVAL_ANALYZER_PROMPT",
]

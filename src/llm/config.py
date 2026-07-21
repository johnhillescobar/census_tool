from typing import Final

LLM_CONFIG = {
    "provider": "openai",  # openai | anthropic | google
    "model": "gpt-5.5",  # gpt-5.5 | gpt-5.2 | gpt-4o | gpt-4o-mini | gpt-4.1
    "temperature": 0.1,
    "temperature_text": 0.5,
    "max_tokens": 50000,  # gpt-4o-mini max is 16384
    "timeout": 30,
    "fallback_model": "gpt-4o-mini",
}

# Provider-specific model mappings (for validation)
SUPPORTED_MODELS = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-5",
        "gpt-5.2",
        "gpt-5.5",
        "gpt-5-mini",
        "o1",
        "o1-preview",
        "o1-mini",
        "o3",
        "o3-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-5-20250929",
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ],
    "google": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-pro",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
}

INTENT_PROMPT_TEMPLATE = """
You are a census data expert assistant. Analyze the user's question and extract structured intent information.

User Question: "{user_question}"

Context:
- User Profile: {user_profile}
- Recent Queries: {recent_queries}

Extract and return JSON with these fields:
- is_census: boolean (is this a census data question?)
- answer_type: "single" | "series" | "table"
- measures: array of measure keywords (population, income, etc.)
- time: object with start_year, end_year if specified
- geo_hint: string containing any geographic references. If no specific location is mentioned, return the full user question text.
- confidence: float 0-1 (your confidence in this analysis)

Respond with ONLY valid JSON, no additional text.
"""

CATEGORY_DETECTION_PROMPT_TEMPLATE = """
# Role and Objective
You are a Census data expert. Your goal is to analyze the user's question and determine the most appropriate Census data category for their needs.

# Instructions
- Review the user's question: "{user_question}"
- Select which Census data category (from the categories outlined below) best fits the user's request.
- Provide your confidence score (float between 0.0 and 1.0) and your reasoning.
- If no clear category applies, or if the user's question is empty/missing, return nulls and an explanatory message.

# Census Data Categories
1. **Detail Tables** (`B/C-series`)
- Description: Provide granular, highly specific demographic information.
- Use case: When the user requests very specific breakdowns (e.g., counts, narrow measures).
- Example questions: "What's the total population?", "How many owner-occupied households?"

2. **Subject Tables** (`S-series`)
- Description: Summarize comprehensive topics, providing overviews.
- Use case: When the user requests general overviews or summaries about a particular topic.
- Example questions: "Give me an overview of age demographics", "Summarize employment data."

3. **Profile Tables** (`DP-series`)
- Description: Present a complete demographic or economic profile for a geographic area.
- Use case: When the user wants a holistic portrait of characteristics (demographic, social, economic, housing).
- Example questions: "Show me a demographic profile.", "Complete economic characteristics."

4. **Comparison Tables** (`CP-series`)
- Description: Organize data for comparing across groups or time.
- Use case: When the user is explicitly comparing or contrasting data (e.g., across states or time periods).
- Example questions: "Compare income across states", "How has poverty changed over time?"

5. **Selected Population Profiles** (`SPP`)
- Description: Provide population profiles for specific racial or ethnic groups.
- Use case: When the user requests details about specific groups (e.g., Hispanic, Latino, Asian, etc.).
- Example questions: "Hispanic population characteristics", "Asian demographic profile."

# Reasoning and Decision
- Analyze the user's question and:
1. Select the most relevant data category (see options below).
2. Assign a confidence score (0.0 to 1.0).
3. Clearly explain why you selected that category.

- If the user's question does not indicate a preference or is missing/empty, set all output fields to null and explain in the reasoning.

# Output Format
Return ONLY valid JSON in one of these valid formats:
```json
{{
"preferred_category": "detail",
"confidence": 0.85,
"reasoning": "The user is asking for specific counts, which aligns with Detail Tables."
}}
```
```json
{{
"preferred_category": null,
"confidence": null,
"reasoning": "The question does not provide enough category signal, so category and confidence are null."
}}
```

## Field Details
- `preferred_category`: One of "detail", "subject", "profile", "cprofile", "spp", or null if undetectable or no input.
- `confidence`: A floating-point value (0.0-1.0), or null if missing/empty input.
- `reasoning`: Brief rationale for the choice, or an explanatory message if input is missing/empty.

# Output Verbosity
- Respond in at most 2 short paragraphs, or if using bullets, limit to a maximum of 6 bullets, each 1 line long.
- Prioritize complete, actionable answers within this length cap; do not reduce completeness to shorten responses.

# Update Rules
- If an updated user question is provided, your update should be at most 1-2 sentences, unless the user specifically requests more detailed supervision.
"""

# Removed from runtime during Phase 3A. The classic ReAct prompt embedded canonical
# identifiers and geography mappings and was never used by the modern backend.
# This tombstone makes accidental reuse fail immediately instead of silently reviving it.
AGENT_PROMPT_TEMPLATE: Final[None] = None

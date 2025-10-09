import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LLM_CONFIG = {
    "provider": "openai",
    "model": "gpt-4.1",
    "temperature": 0.1,
    "temperature_text": 0.5,
    "max_tokens": 500,
    "timeout": 30,
    "fallback_model": "gpt-4o-mini",
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

CLARIFICATION_PROMPT_TEMPLATE = """
You are helping a user get census data. They asked: "{user_question}"

Available Data Options:
{available_options}

User Profile: {user_profile}

Generate a helpful, conversational clarification question that:
1. Acknowledges what they're looking for
2. Offers 2-3 specific options
3. Asks for their preference in a friendly way

Keep it under 100 words and be encouraging.
"""

ANSWER_PROMPT_TEMPLATE = """
You are a census data expert providing answers to users. Generate a natural, informative response.

User Question: "{user_question}"

Answer Type: {answer_type}
- "single": One specific value
- "series": Time series data showing trends
- "table": Multiple values for comparison

Data Summary:
{data_summary}

Geographic Context: {geo_context}

Requirements:
- Be conversational but professional
- Include the key numbers prominently with proper formatting

For SINGLE values:
- State the value clearly with context (year, location)
- Add brief interpretation if notable

For SERIES data:
- Describe the overall trend (increasing, decreasing, stable)
- Mention specific notable changes or turning points
- Include start and end values

For TABLE data:
- Highlight the highest and lowest values
- Point out interesting comparisons or patterns
- Organize information logically

General:
- Mention any important caveats or data limitations
- Keep under 250 words
- End with an offer to help with follow-up questions

Response:
"""

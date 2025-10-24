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

CATEGORY_DETECTION_PROMPT_TEMPLATE = """
You are a Census data expert. Analyze the user's question and determine which Census data category best fits their need.

User Question: "{user_question}"

Census Data Categories:

1. **Detail Tables** (B/C-series)
   - Granular, specific demographic measures
   - Use when: User wants specific, detailed breakdowns
   - Examples: "What's the total population?", "How many owner-occupied households?"
   
2. **Subject Tables** (S-series)  
   - Comprehensive topic overviews and summaries
   - Use when: User wants overview, summary, general information about a topic
   - Examples: "Give me an overview of age demographics", "Summarize employment data"
   
3. **Profile Tables** (DP-series)
   - Complete demographic/economic profiles
   - Use when: User wants full profile, comprehensive characteristics, or complete picture
   - Examples: "Show me a demographic profile", "Complete economic characteristics"
   
4. **Comparison Tables** (CP-series)
   - Data structured for comparing across groups or time
   - Use when: User wants to compare, contrast, or analyze changes
   - Examples: "Compare income across states", "How has poverty changed over time?"
   
5. **Selected Population Profiles** (SPP)
   - Race/ethnicity-specific population profiles
   - Use when: User asks specifically about Hispanic, Latino, Asian, or other racial/ethnic groups
   - Examples: "Hispanic population characteristics", "Asian demographic profile"

Analyze the user's question and determine:
1. Which category best fits their information need?
2. How confident are you? (0.0 to 1.0)
3. Why does this category fit?

Return ONLY valid JSON with this structure:
{{
    "preferred_category": "detail" | "subject" | "profile" | "cprofile" | "spp" | null,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation of why this category fits"
}}

If no specific category preference is detected, return null for preferred_category.
"""


AGENT_PROMPT_TEMPLATE = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action as valid JSON
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

TOOL USAGE GUIDE (all Action Inputs must be valid JSON):

1. geography_discovery - Discover and enumerate geography areas
   - List levels: {{"action": "list_levels", "dataset": "acs/acs5", "year": 2023}}
   - Enumerate areas: {{"action": "enumerate_areas", "level": "county", "parent": {{"state": "06"}}}}

2. resolve_area_name - Convert area names to Census codes
   - Get state code: {{"name": "California", "geography_type": "state"}}
   - Get county code: {{"name": "Los Angeles County", "geography_type": "county", "parent": {{"state": "06"}}}}
   
3. table_search - Find Census tables by topic
   - Search tables: {{"query": "population data"}}

4. census_api_call - Execute Census API query and fetch data with complex patterns support
   - Simple: {{"year": 2023, "dataset": "acs/acs5", "variables": ["NAME", "B01003_001E"], "geo_for": {{"county": "*"}}, "geo_in": {{"state": "06"}}}}
   - Subject table: {{"year": 2023, "dataset": "acs/acs5/subject", "variables": ["group(S0101)"], "geo_for": {{"state": "*"}}}}
   - Complex CBSA: {{"year": 2023, "dataset": "acs/acs5", "variables": ["NAME", "B01001_001E"], "geo_for": {{"state (or part)": "*"}}, "geo_in": {{"metropolitan statistical area/micropolitan statistical area": "35620"}}}}

5. table_validation - Validate table supports requested geography
   - Validate table: {{"table_code": "B01003", "geography_level": "county", "dataset": "acs/acs5"}}

6. pattern_builder - Build Census API URL patterns with support for all dataset categories
   - Detail table: {{"year": 2023, "dataset": "acs/acs5", "table_code": "B01003", "geo_for": {{"county": "*"}}, "geo_in": {{"state": "06"}}}}
   - Subject table: {{"year": 2023, "dataset": "acs/acs5/subject", "table_code": "S0101", "geo_for": {{"state": "*"}}, "table_category": "subject", "use_groups": true}}

7. create_chart - Create data visualizations from census data
   - Bar chart: {{"chart_type": "bar", "x_column": "NAME", "y_column": "B01003_001E", "title": "Population by County", "data": <census_api_call_result>}}
   - Line chart: {{"chart_type": "line", "x_column": "Year", "y_column": "Value", "title": "Population Trend", "data": <census_api_call_result>}}
   Note: The 'data' field should be the complete result from census_api_call tool (including success, data keys)

8. create_table - Export census data as formatted tables
   - CSV: {{"format": "csv", "filename": "ny_population", "title": "Population Data", "data": <census_api_call_result>}}
   - Excel: {{"format": "excel", "filename": "population_table", "title": "Population by County", "data": <census_api_call_result>}}
   - HTML: {{"format": "html", "title": "Population Report", "data": <census_api_call_result>}}
   Note: filename is optional (will auto-generate with timestamp if not provided)

CRITICAL OUTPUT FORMAT RULES:
When you have the final data, you MUST output EXACTLY this format on ONE line:

Thought: I now know the final answer
Final Answer: {{"census_data": {{"success": true, "data": [...actual data...]}}, "data_summary": "brief summary text", "reasoning_trace": "your steps", "answer_text": "natural language answer", "charts_needed": [...chart specifications...], "tables_needed": [...table specifications...]}}

RULES:
1. Write "Thought: I now know the final answer" on its own line
2. Write "Final Answer: " followed immediately by the complete JSON on the SAME line
3. The ENTIRE JSON object must be on ONE line with NO line breaks inside it
4. Compress the JSON - no pretty printing, no indentation, no newlines
5. Include all 6 keys: census_data, data_summary, reasoning_trace, answer_text, charts_needed, tables_needed

CORRECT example:
Final Answer: {{"census_data":{{"success":true,"data":[["NAME","B01003_001E"],["Los Angeles","9848406"]]}},"data_summary":"Population data for LA","reasoning_trace":"Queried B01003 table","answer_text":"LA has 9.8M people","charts_needed":[{{"type":"bar","title":"Population by County"}}],"tables_needed":[{{"format":"csv","filename":"la_population","title":"Population Data"}}]}}


WRONG examples (DO NOT DO THIS):
Final Answer: {{
    "census_data": {{
        "success": true
    }}
}}

WRONG - multi-line JSON will cause parsing errors. Keep it on ONE line!

REASONING PROCESS FOR COMPLEX CENSUS QUERIES:
1. For listing/enumeration → use geography_discovery with enumerate_areas (supports CBSAs, metropolitan divisions, NECTAs, etc.)
2. For area resolution → use resolve_area_name with appropriate geography_type (state, county, CBSA, metropolitan division, etc.)
3. For table finding → use table_search to find relevant tables by topic
4. For complex geography hierarchies → chain tools to resolve nested relationships (e.g., counties within CBSAs)
5. For API calls → use census_api_call with proper dataset category:
   - Detail tables: "acs/acs5" (B/C-series)
   - Subject tables: "acs/acs5/subject" (S-series) - use group(TABLE_CODE)
   - Profile tables: "acs/acs1/profile" (DP-series) - use group(TABLE_CODE)
   - Comparison tables: "acs/acs5/cprofile" (CP-series)
   - Selected Population Profiles: "acs/acs1/spp" (SPP-series)
6. Always validate table supports requested geography level before calling API

OUTPUT GENERATION GUIDELINES:
7. When user requests charts or visualizations, add to "charts_needed" array:
   - Format: [{{"type": "bar|line", "title": "descriptive title"}}]
   - Use "bar" for comparisons across locations, "line" for trends over time
   - Auto-generate meaningful titles based on data context

8. When user requests data export or tables, add to "tables_needed" array:
   - Format: [{{"format": "csv|excel|html", "filename": "optional_name", "title": "descriptive title"}}]
   - Use "csv" for basic export, "excel" for formatted reports, "html" for web display

9. Always include both arrays in Final Answer - use empty arrays [] if no output generation requested

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
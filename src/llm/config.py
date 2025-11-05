import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LLM_CONFIG = {
    "provider": "openai",  # openai | anthropic | google
    "model": "gpt-4.1",  # gpt-4.1 |gpt-5 | claude-sonnet-4-5-20250929 |gemini-2.5-flash
    "temperature": 0.1,
    "temperature_text": 0.5,
    "max_tokens": 20000,
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
        "gpt-5-mini",
        "o1",
        "o1-preview",
        "o1-mini",
        "o3",
        "o3-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-5-20250929",  # Latest Claude Sonnet 4.5
        "claude-3-5-sonnet-20241022",  # Deprecated but may still work
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ],
    "google": [
        "gemini-2.5-pro",  # Latest Gemini 2.5 Pro
        "gemini-2.5-flash",  # Latest Gemini 2.5 Flash
        "gemini-2.0-pro",  # Gemini 2.0 Pro
        "gemini-2.0-flash",  # Gemini 2.0 Flash
        "gemini-1.5-pro",  # Legacy Gemini 1.5 Pro
        "gemini-1.5-flash",  # Legacy Gemini 1.5 Flash
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

ANSWER TEXT REQUIREMENTS (CRITICAL - THIS IS YOUR PRIMARY OUTPUT):

The answer_text field is your main response to the user. Write it as if you're talking to a colleague.

Guidelines by question type:

1. SINGLE VALUE (population of a place, one number):
   - Template: "Location has a population of number people."
   - Include year/dataset context: "...according to 2023 ACS 5-Year estimates."
   - Example: "New York City has a population of 8,336,817 people (2023 ACS 5-Year data)."

2. COMPARISON (multiple places/values):
   - Start with overview: "Here's the population comparison for California counties:"
   - Highlight extremes: "Los Angeles County has the highest at 9.8M people, while Alpine County has the lowest at just 1,204."
   - Add 2-3 notable values in between
   - Example: "Los Angeles County leads with 9,848,011 people, followed by San Diego County at 3,298,634. Alpine County has the smallest population at just 1,204 residents."

3. TRENDS (time series):
   - Describe direction: "Population increased by 15% from 2015 to 2020"
   - Mention key points: starting value, ending value, notable changes
   - Example: "The population grew from 8.2M in 2015 to 9.4M in 2020, with the largest increase occurring between 2017-2018."

RULES:
- answer_text should be 1-3 sentences for simple queries, up to a paragraph for complex ones
- ALWAYS include actual numbers from census_data
- Format numbers with commas (9,848,011 not 9848011)
- Be conversational but professional
- Charts/tables are supplements - answer_text should stand alone

CRITICAL OUTPUT FORMAT RULES:
When you have the final data, you MUST output EXACTLY this format on ONE line:

Thought: I now know the final answer
Final Answer: {{"census_data": {{"success": true, "data": [...actual data...]}}, "data_summary": "brief summary text", "reasoning_trace": "your steps", "answer_text": "natural language answer", "charts_needed": [...chart specifications...], "tables_needed": [...table specifications...], "footnotes": ["footnote 1", "footnote 2", ...]}}

RULES:
1. Write "Thought: I now know the final answer" on its own line
2. Write "Final Answer: " followed immediately by the complete JSON on the SAME line
3. The ENTIRE JSON object must be on ONE line with NO line breaks inside it
4. Compress the JSON - no pretty printing, no indentation, no newlines
5. Include all 7 keys: census_data, data_summary, reasoning_trace, answer_text, charts_needed, tables_needed, footnotes
6. CRITICAL: Output COMPLETE, VALID JSON - NO ellipses (...), NO abbreviations, NO truncation
7. If data is very large (100+ columns), include ALL data without abbreviation - the JSON must be parseable

CORRECT example:
Final Answer: {{"census_data":{{"success":true,"data":[["NAME","B01003_001E"],["Los Angeles County","9,848,406"]]}},"data_summary":"Population data for Los Angeles County from 2023 ACS","reasoning_trace":"Resolved LA to Los Angeles County, queried B01003 table","answer_text":"Los Angeles County has a population of 9,848,406 people according to 2023 ACS 5-Year estimates.","charts_needed":[{{"type":"bar","title":"Population by County"}}],"tables_needed":[{{"format":"csv","filename":"la_population","title":"Population Data"}}],"footnotes":["Source: U.S. Census Bureau, 2023 American Community Survey 5-Year Estimates.","Margins of error not shown. For statistical significance, refer to Census Bureau documentation."]}}


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

CRITICAL: MINIMIZE DATA VOLUME
- For profile/subject/comparison tables (S/DP/CP series), DO NOT use group() unless user explicitly asks for "all variables" or "complete profile"
- Instead, use pattern_builder with custom variables list containing only relevant variables
- Example: User asks "Florida counties employment rate" → use CP03 table but specify only employment variables, not entire group
- Use table_search to identify which specific variables to request
- Only use group() syntax when: (a) user asks for complete profile, or (b) you need 10+ variables from same table
- Fetching entire groups can return 100+ variables causing slow responses and parsing failures

MULTI-YEAR TIME SERIES QUERIES:

For queries requesting data across multiple years (e.g., "2015 to 2020", "trends since 2010"):

1. IDENTIFY year range from user question
2. MAKE MULTIPLE census_api_call invocations - ONE PER YEAR:
   - Example: For "2015 to 2020" → make 6 separate calls (2015, 2016, 2017, 2018, 2019, 2020)
   - Use same dataset, variables, and geography for each year
   
3. AGGREGATE results into time series format:
   - Restructure data with columns: ["Year", "Measure Name", "<other geography columns>"]
   - Example output format:
     [["Year", "Median Household Income (USD)", "Geography"],
      ["2015", "53,889", "United States"],
      ["2016", "55,322", "United States"],
      ...]

4. CHARTS for time series:
   - ALWAYS use "line" chart type for multi-year trends
   - Set x_column to "Year"
   - Set y_column to the measure name
   
5. ANSWER TEXT for time series:
   - Describe overall trend: "increased by X%" or "decreased from Y to Z"
   - Mention starting value, ending value, and notable changes
   - Example: "Median household income increased from $53,889 in 2015 to $68,700 in 2020, representing a 27.5% growth."

6. ERROR HANDLING:
   - If a year is unavailable, note it in answer_text
   - Continue with available years
   - Example: "Data available for 2015-2019 and 2021-2023 (2020 data unavailable)"

Example multi-year reasoning:
Thought: User wants trends from 2015 to 2020. I need to query each year separately.
Action: census_api_call
Action Input: {{"year": 2015, "dataset": "acs/acs5/subject", "variables": ["S1903_C03_001E"], "geo_for": {{"us": "1"}}}}
Observation: [...2015 data...]
Thought: Now query 2016
Action: census_api_call
Action Input: {{"year": 2016, "dataset": "acs/acs5/subject", "variables": ["S1903_C03_001E"], "geo_for": {{"us": "1"}}}}
Observation: [...2016 data...]
... (repeat for 2017, 2018, 2019, 2020)
Thought: I now have all years. Restructure into time series format.
Final Answer: {{"census_data": {{"success": true, "data": [["Year", "Median Household Income (USD)"], ["2015", "53,889"], ["2016", "55,322"], ...]}}...}}

OUTPUT GENERATION GUIDELINES:
7. ALWAYS generate charts for census data visualization:
   - For SINGLE location questions: Include bar chart in "charts_needed"
   - For COMPARISON questions: Include bar chart in "charts_needed"
   - For TREND/time series questions: Include line chart in "charts_needed"
   - Format: [{{"type": "bar|line", "title": "descriptive title"}}]
   - Use "bar" for comparisons across locations or single values
   - Use "line" for trends over time
   - Auto-generate meaningful titles based on data context

8. When user requests data export or tables, add to "tables_needed" array:
   - Format: [{{"format": "csv|excel|html", "filename": "optional_name", "title": "descriptive title"}}]
   - Use "csv" for basic export, "excel" for formatted reports, "html" for web display

9. Always include both arrays in Final Answer - use empty arrays [] if no charts/tables needed

10. Generate footnotes array with data source citations and disclaimers:
   - ALWAYS include: Data source citation (e.g., "Source: U.S. Census Bureau, 2023 American Community Survey 5-Year Estimates.")
   - ALWAYS include: Statistical disclaimer (e.g., "Margins of error not shown. For statistical significance, refer to Census Bureau documentation.")
   - Include methodology notes if relevant (e.g., "Income values are adjusted for 2023 inflation using the Consumer Price Index (CPI-U).")
   - Include table codes used (e.g., "Census table(s) used: B01003.")
   - Include general disclaimer (e.g., "This tool is for informational purposes only. Verify critical data at census.gov.")
   - Format: ["footnote 1", "footnote 2", "footnote 3", ...]
   - Minimum 2 footnotes (source + disclaimer), typically 3-5 total

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

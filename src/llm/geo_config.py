"""
Geography reasoning prompts for Phase 9F
"""

GEOGRAPHY_SUMMARY_LEVEL_PROMPT = """
You are a US Census geography expert. Analyze the user's query and determine what geographic level (summary level) they need.

User Query: "{user_query}"
Intent: {intent}

Census Geography Levels (examples):
- "state" - US states (California, Texas, etc.)
- "county" - Counties within states
- "place" - Cities, towns
- "metropolitan statistical area/micropolitan statistical area" - Metro areas (MSAs)
- "school district (unified)" - School districts
- "tract" - Census tracts
- "zip code tabulation area" - ZIP codes (ZCTAs)
- "congressional district" - Congressional districts
[... and 136 more patterns]

Special Cases:
- If user wants "all X in Y" → They want enumeration (multiple areas)
- If user mentions specific name → Single area lookup
- If no geography mentioned → Use context or default to nation

Determine:
1. What summary level do they need?
2. Do they want a single area or enumerate all areas at this level?
3. What parent geography constraints (if any)?
4. Confidence level (0.0-1.0)

Return ONLY valid JSON:
{{
    "summary_level": "county" | "state" | "place" | etc.,
    "needs_enumeration": true | false,
    "parent_geography": {{"state": "06"}} or null,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Examples:
- "population of California" → {{"summary_level": "state", "needs_enumeration": false}}
- "all counties in California" → {{"summary_level": "county", "needs_enumeration": true, "parent_geography": {{"state": "California"}}}}
- "New York Metro Area" → {{"summary_level": "metropolitan statistical area/micropolitan statistical area", "needs_enumeration": false}}
"""

GEOGRAPHY_NAME_RESOLUTION_PROMPT = """
You are a US Census geography expert. Resolve a friendly geographic name to its Census code.

Friendly Name: "{friendly_name}"
Summary Level: {summary_level}
Available Areas: {available_areas}

Your task: Match the friendly name to one of the available areas.

Consider:
- Common abbreviations (NYC → New York City, LA → Los Angeles)
- Spelling variations
- Official vs common names
- State context if relevant

Return ONLY valid JSON:
{{
    "matched_code": "037" | null,
    "matched_name": "Los Angeles County, California",
    "confidence": 0.0-1.0,
    "reasoning": "explanation"
}}
"""

GEOGRAPHY_PATTERN_CONSTRUCTION_PROMPT = """
You are a US Census API expert. Construct the correct geography pattern for a Census API call.

Requirements:
- Summary Level: {summary_level}
- Area Code: {area_code}
- Parent Geographies: {parent_geographies}
- Needs Enumeration: {needs_enumeration}

Census API Geography Syntax:
- Single area: for=state:06
- Enumerate all: for=county:*&in=state:06
- Complex hierarchy: for=tract:*&in=county:037&in=state:06
- Spaces must be URL encoded: county%20subdivision

Construct the correct for=/in= pattern.

Return ONLY valid JSON:
{{
    "geography_pattern": "for=county:*&in=state:06",
    "url_encoded": true | false,
    "confidence": 0.0-1.0,
    "reasoning": "explanation"
}}
"""
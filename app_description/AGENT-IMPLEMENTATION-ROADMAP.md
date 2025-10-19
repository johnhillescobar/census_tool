# AGENT IMPLEMENTATION ROADMAP

**Date**: October 12, 2025  
**Goal**: Build a reasoning agent system for Census data retrieval  
**Success**: main.py handles complex queries correctly with agent-based reasoning

---

## 🎯 OBJECTIVE

Replace hardcoded logic with **3 cooperating agents** that reason through Census API complexity using tools.

---

## 📋 AGENT 1: Census Query Agent (PRIMARY)

### Purpose
Reason through user queries to build valid Census API specifications

### Tools To Build

#### Tool 1: GeographyDiscoveryTool
```python
class GeographyDiscoveryTool(BaseTool):
    """
    Discover available geography levels and enumerate areas
    """
    name = "geography_discovery"
    description = """
    Use this tool to:
    1. Check what geography levels are available for a dataset
    2. Enumerate all areas at a geography level
    3. Resolve geography names to FIPS codes
    
    Examples:
    - "What geography levels exist for acs/acs5 in 2023?"
    - "List all counties in California"
    - "What's the FIPS code for Los Angeles County?"
    """
    
    def _run(self, action: str, dataset: str = None, level: str = None, parent: str = None):
        if action == "list_levels":
            # Query geography.html or cached registry
            return self.registry.get_levels(dataset)
        
        elif action == "enumerate_areas":
            # Call Census API: get=NAME,GEO_ID&for={level}:*&in={parent}
            return self.census_api.enumerate_areas(level, parent)
        
        elif action == "resolve_name":
            # Fuzzy match name to FIPS code
            return self.registry.resolve_name(level, name)
```

#### Tool 2: TableSearchTool
```python
class TableSearchTool(BaseTool):
    """
    Search for relevant Census tables
    """
    name = "table_search"
    description = """
    Search ChromaDB for Census tables matching a concept.
    Returns table metadata including supported geographies.
    
    Examples:
    - "Find tables about median income"
    - "What tables have population data?"
    """
    
    def _run(self, query: str, category: str = None):
        # Search ChromaDB tables collection
        results = self.chroma.query(
            collection="census_tables",
            query_texts=[query],
            n_results=5,
            where={"category": category} if category else None
        )
        return self._format_results(results)
```

#### Tool 3: TableValidationTool
```python
class TableValidationTool(BaseTool):
    """
    Validate table supports requested geography
    """
    name = "validate_table_geography"
    description = """
    Check if a Census table supports a specific geography level.
    
    Examples:
    - "Does B01003 support county level?"
    - "What geography levels does S0101 support?"
    """
    
    def _run(self, table_code: str, geography_level: str = None):
        # Fetch table metadata
        metadata = self.census_api.get_table_metadata(table_code)
        
        if geography_level:
            supported = geography_level in metadata["geographies"]
            return {"supported": supported, "available": metadata["geographies"]}
        else:
            return {"geographies": metadata["geographies"]}
```

#### Tool 4: PatternBuilderTool
```python
class PatternBuilderTool(BaseTool):
    """
    Construct Census API URL patterns
    """
    name = "build_census_url"
    description = """
    Build a valid Census API URL from components.
    
    Inputs:
    - table_code: e.g., "B01003"
    - geography_pattern: e.g., "for=county:*&in=state:06"
    - year: e.g., 2023
    - category: e.g., "detail", "subject"
    
    Returns complete Census API URL
    """
    
    def _run(self, table_code: str, geography_pattern: str, year: int, category: str):
        # Build URL dynamically
        base = f"https://api.census.gov/data/{year}"
        
        if category == "subject":
            base += "/acs/acs5/subject"
        elif category == "profile":
            base += "/acs/acs1/profile"
        else:
            base += "/acs/acs5"
        
        # Add get parameter
        get_param = f"group({table_code})" if category in ["subject", "profile"] else f"{table_code}_001E"
        
        return f"{base}?get={get_param}&{geography_pattern}"
```

#### Tool 5: AreaResolutionTool
```python
class AreaResolutionTool(BaseTool):
    """
    Resolve friendly names to Census codes
    """
    name = "resolve_area_name"
    description = """
    Resolve a friendly geography name to its Census code.
    
    Examples:
    - "What's the code for California?" → "06"
    - "What's the code for New York City?" → "51000"
    - "What's the CBSA code for New York Metro?" → "35620"
    """
    
    def _run(self, name: str, geography_type: str):
        # Use geography registry + fuzzy matching
        return self.registry.resolve(name, geography_type)
```

### Agent Implementation

```python
# src/agents/census_query_agent.py

from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

class CensusQueryAgent:
    """
    Reasoning agent for Census queries
    Uses ReAct pattern with Census tools
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        # Initialize tools
        self.tools = [
            GeographyDiscoveryTool(),
            TableSearchTool(),
            TableValidationTool(),
            PatternBuilderTool(),
            AreaResolutionTool(),
        ]
        
        # Create ReAct agent
        self.agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self._build_prompt()
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )
    
    def _build_prompt(self):
        return PromptTemplate.from_template("""
You are a Census data expert helping users query the Census API.

Your task: Given a user's question, use the available tools to:
1. Determine what geography level is needed
2. Find relevant Census tables
3. Validate the table supports that geography
4. Construct a valid Census API URL

Available tools:
{tools}

Tool names: {tool_names}

Use this format:
Question: the user's question
Thought: reason about what to do next
Action: the tool to use
Action Input: the input to the tool
Observation: the tool's result
... (repeat Thought/Action/Observation as needed)
Thought: I now know the final answer
Final Answer: the complete Census API specification

Question: {input}
Thought: {agent_scratchpad}
""")
    
    def solve(self, user_query: str, intent: Dict) -> Dict:
        """
        Reason through the query and build API spec
        """
        result = self.agent_executor.invoke({
            "input": f"""
User query: {user_query}
Intent: {intent}

Build a valid Census API specification including:
- Table code
- Geography pattern (for=/in= format)
- Year
- Variables to retrieve
"""
        })
        
        return self._parse_result(result)
```

---

## 📋 AGENT 2: Data Retrieval Agent (SECONDARY)

### Purpose
Execute Census API queries and handle errors intelligently

### Tools To Build

#### Tool 1: CensusAPITool
```python
class CensusAPITool(BaseTool):
    """Execute Census API calls"""
    name = "census_api_call"
    description = "Make a Census API request and return data"
    
    def _run(self, url: str):
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": response.text, "status": response.status_code}
```

#### Tool 2: ErrorAnalysisTool
```python
class ErrorAnalysisTool(BaseTool):
    """Analyze Census API errors"""
    name = "analyze_census_error"
    description = "Parse Census API error messages and suggest fixes"
    
    def _run(self, error_text: str, url: str):
        # Parse common Census API errors
        if "invalid geography" in error_text.lower():
            return "Geography pattern not supported by this table"
        elif "unknown variable" in error_text.lower():
            return "Variable code doesn't exist in this dataset"
        # ... more error patterns
```

### Agent Implementation

```python
# src/agents/data_retrieval_agent.py

class DataRetrievalAgent:
    """
    Agent that executes queries and handles errors
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        self.tools = [
            CensusAPITool(),
            ErrorAnalysisTool(),
        ]
        
        self.agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self._build_prompt()
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )
    
    def execute(self, api_spec: Dict) -> Dict:
        """
        Try to execute the API spec, handle errors
        """
        result = self.agent_executor.invoke({
            "input": f"""
Execute this Census API query:
{api_spec}

If it fails, analyze the error and try to fix it.
Maximum 3 retry attempts.
"""
        })
        
        return result
```

---

## 📋 AGENT 3: Evaluation Agent (VALIDATOR)

### Purpose
Validate that the answer makes logical sense

### Implementation

```python
# src/agents/evaluation_agent.py

class EvaluationAgent:
    """
    Agent that validates answers for logical consistency
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
    
    def evaluate(self, user_query: str, api_spec: Dict, data: Dict) -> Dict:
        """
        Evaluate if the answer makes sense
        """
        prompt = f"""
You are evaluating a Census data retrieval.

User asked: "{user_query}"

System produced:
- Table: {api_spec['table_code']}
- Geography: {api_spec['geography_pattern']}
- Data: {data}

Evaluate:
1. Does the geography pattern match what the user asked for?
2. Are the variables appropriate for the question?
3. Do the data values look reasonable?
4. Is anything missing or incorrect?

Respond with:
- valid: true/false
- issues: list of problems found
- suggestions: how to fix them
"""
        
        response = self.llm.invoke(prompt)
        return self._parse_evaluation(response)
```

---

## 🚀 INTEGRATION PLAN

### Week 1: Build Core Agent with Tools (Days 1-7)

**Day 1-2**: Tool Development
- [ ] Build GeographyDiscoveryTool
- [ ] Build TableSearchTool
- [ ] Test tools independently

**Day 3-4**: Build Census Query Agent
- [ ] Implement CensusQueryAgent class
- [ ] Create ReAct prompt
- [ ] Wire up all 5 tools
- [ ] Test with simple query: "Population of New York City"

**Day 5**: Build Data Retrieval Agent
- [ ] Implement DataRetrievalAgent
- [ ] Add error handling logic
- [ ] Test with actual Census API

**Day 6**: Build Evaluation Agent
- [ ] Implement EvaluationAgent
- [ ] Define validation criteria
- [ ] Test with sample queries

**Day 7**: Integration
- [ ] Wire all 3 agents together
- [ ] Create agent orchestration layer
- [ ] Test end-to-end flow

### Week 2: Integration with main.py (Days 8-14)

**Day 8-9**: Replace Current Nodes
- [ ] Replace intent_node with agent call
- [ ] Replace geo_node with agent geography resolution
- [ ] Replace retrieve_node with agent table search

**Day 10-11**: Test with main.py
- [ ] Test all 6 example queries
- [ ] Fix integration issues
- [ ] Ensure no crashes

**Day 12-13**: Refinement
- [ ] Tune agent prompts
- [ ] Optimize tool performance
- [ ] Add logging of agent reasoning

**Day 14**: Validation
- [ ] All 6 queries work correctly
- [ ] Agent reasoning visible in logs
- [ ] Evaluation agent catches errors

---

## ✅ SUCCESS METRICS

Phase 9 complete when:
1. ✅ 3 agents implemented with proper tools
2. ✅ main.py uses agents (not hardcoded logic)
3. ✅ All 6 test queries return correct results
4. ✅ Agent reasoning traces visible
5. ✅ Evaluation agent flags incorrect answers
6. ✅ No crashes, no KeyErrors
7. ✅ Geography enumeration works correctly
8. ✅ Can handle NEW query types agent hasn't seen

---

## 🎯 IMMEDIATE NEXT STEPS

**TODAY** (October 12):
1. Fix the immediate crash (Fix 2 didn't apply correctly)
2. Start building GeographyDiscoveryTool
3. Start building TableSearchTool

**THIS WEEK**:
- Complete all 5 tools for Census Query Agent
- Build working ReAct agent with tools
- Test agent with one query end-to-end

**Definition of Success**: Agent reasons through "Compare population by county in California" and produces `for=county:*&in=state:06` through multi-step reasoning with tools, not hardcoded patterns.


# LangChain v1.0 Migration Plan

**Date**: 2025-01-XX  
**Status**: Planning Document  
**Purpose**: Step-by-step plan to migrate from LangChain v0.3.27 to LangChain v1.0

> **Repository layout note (2026):** This plan was written against older paths. The agent now lives at `src/agents/census_query_agent.py` (not `src/utils/agents/`). LangGraph nodes live under `src/workflows/` (not `src/nodes/`). Update mentally when following file references below.

---

## Quick Reference Checklist

### Critical Changes Required
- [ ] Update `langchain==0.3.27` → `langchain>=1.0.0` in `pyproject.toml` and `requirements.txt`
- [ ] Replace `create_react_agent` + `AgentExecutor` → `create_agent` in `census_query_agent.py`
- [ ] Convert `PromptTemplate` → `system_prompt` (string) for `create_agent`
- [ ] Update input format: `{"input": "..."}` → `{"messages": [{"role": "user", "content": "..."}]}`
- [ ] Verify output format: Check if `result` structure changed
- [ ] Update callback integration: `ConversationSummarizer` may need different API
- [ ] Test all agent functionality end-to-end

### Files to Modify
1. **`pyproject.toml`** - Dependency versions
2. **`requirements.txt`** - Dependency versions  
3. **`src/utils/agents/census_query_agent.py`** - Agent creation and invocation (CRITICAL)
4. **`src/llm/config.py`** - May need new `AGENT_SYSTEM_PROMPT` constant

### Files That Should Work Without Changes
- `app.py` - LangGraph APIs are stable
- All tool files (`src/tools/*.py`) - `BaseTool` is compatible
- `src/llm/factory.py` - Provider integrations should work
- `src/nodes/*.py` - Node structure unchanged

---

## Executive Summary

This document outlines the migration plan from LangChain v0.3.27 to LangChain v1.0. The migration involves:
- **LangChain**: v0.3.27 → v1.0 (breaking changes)
- **LangGraph**: v0.6.7 → v1.0 (mostly compatible, but deprecations)
- **Agent API**: `create_react_agent` + `AgentExecutor` → `create_agent` (new unified API)
- **Reasoning-node-first intent**: deterministic contracts and workflow/service steps must empower AI reasoning nodes/components and must not replace AI reasoning nodes/components, while preserving explicit reasoning-node execution ownership.

**Risk Level**: Medium-High  
**Estimated Time**: 4-6 hours  
**Testing Required**: Comprehensive (all existing tests + new compatibility tests)

---

## Current State Analysis

### What I Checked First
1. **Dependencies** (`pyproject.toml`, `requirements.txt`):
   - `langchain==0.3.27` (v0.x)
   - `langgraph>=0.6.7` (v0.x)
   - `langchain-core>=0.3.75` (should be compatible)
   - `langchain-openai>=0.3.32` (should be compatible)
   - `langchain-anthropic>=0.3.0` (should be compatible)
   - `langchain-google-genai>=2.0.0` (should be compatible)

2. **Current LangChain Usage**:
   - `src/utils/agents/census_query_agent.py`: Uses `AgentExecutor` + `create_react_agent`
   - `src/llm/factory.py`: Uses `langchain_openai.ChatOpenAI`, `langchain_anthropic.ChatAnthropic`
   - `app.py`: Uses `langgraph.graph.StateGraph` (should be compatible)
   - All tools inherit from `langchain_core.tools.BaseTool` (should be compatible)

3. **Key Files Requiring Changes**:
   - `src/utils/agents/census_query_agent.py` (CRITICAL - agent creation)
   - `src/llm/config.py` (may need prompt template updates)
   - `pyproject.toml` / `requirements.txt` (dependency updates)

---

## Breaking Changes in LangChain v1.0

### 1. Agent Creation API (CRITICAL)

**OLD (v0.3.27)**:
```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

agent = create_react_agent(
    llm=self.llm,
    tools=self.tools,
    prompt=self._build_prompt()  # PromptTemplate object
)

executor = AgentExecutor(
    agent=agent,
    tools=self.tools,
    verbose=True,
    max_iterations=30,
    handle_parsing_errors="...",
    callbacks=[self.summarizer],
)

result = executor.invoke({"input": user_query})
```

**NEW (v1.0)**:
```python
from langchain.agents import create_agent

# create_agent returns a Runnable that can be invoked directly
agent = create_agent(
    model=self.llm,  # Direct model, not wrapped
    tools=self.tools,
    system_prompt="You are a helpful assistant",  # String, not PromptTemplate
)

# Invoke with messages format
result = agent.invoke({
    "messages": [{"role": "user", "content": user_query}]
})
```

**Key Differences**:
- `create_react_agent` → `create_agent` (new unified API)
- `AgentExecutor` **deprecated** - `create_agent` returns a Runnable directly
- `prompt` parameter → `system_prompt` (string, not PromptTemplate)
- Input format: `{"input": "..."}` → `{"messages": [{"role": "user", "content": "..."}]}`
- Output format: May differ - need to verify structure

### 2. PromptTemplate Changes

**OLD**:
```python
from langchain.prompts import PromptTemplate

prompt = PromptTemplate.from_template(AGENT_PROMPT_TEMPLATE)
```

**NEW**:
- `PromptTemplate` still exists but may have API changes
- For `create_agent`, use `system_prompt` (string) instead
- Complex prompts may need restructuring

### 3. LangGraph Compatibility

**Status**: ✅ **Mostly Compatible**

- `StateGraph`, nodes, edges: **No changes** (stable API)
- `SqliteSaver`, `MemorySaver`: **No changes**
- `langgraph.prebuilt.create_react_agent`: **Deprecated** (but we don't use it)

**Action Required**: None for LangGraph core APIs

### 4. Tool Compatibility

**Status**: ✅ **Compatible**

- `langchain_core.tools.BaseTool`: **No changes**
- All existing tools should work without modification

---

## Migration Steps

### Phase 1: Dependency Updates (30 minutes)

#### Step 1.1: Update pyproject.toml
```toml
dependencies = [
    # ... existing dependencies ...
    "langchain>=1.0.0",  # Changed from ==0.3.27
    "langgraph>=1.0.0",  # Changed from >=0.6.7
    "langchain-core>=1.0.0",  # Changed from >=0.3.75
    "langchain-openai>=1.0.0",  # Changed from >=0.3.32
    "langchain-anthropic>=1.0.0",  # Changed from >=0.3.0
    "langchain-google-genai>=2.0.0",  # Keep (already v2+)
    # ... rest unchanged ...
]
```

#### Step 1.2: Update requirements.txt
```txt
langchain>=1.0.0
langgraph>=1.0.0
langchain-core>=1.0.0
langchain-openai>=1.0.0
langchain-anthropic>=1.0.0
# ... rest unchanged ...
```

#### Step 1.3: Install Dependencies
```bash
uv sync
# OR
pip install -r requirements.txt --upgrade
```

**Verification**:
```bash
uv run python -c "import langchain; print(langchain.__version__)"
# Should show: 1.0.x or higher
```

---

### Phase 2: Agent Migration (2-3 hours)

#### Step 2.1: Update CensusQueryAgent.__init__()

**File**: `src/utils/agents/census_query_agent.py`

**Changes Required**:

1. **Update imports**:
```python
# OLD
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

# NEW
from langchain.agents import create_agent
# Remove AgentExecutor import
# Keep PromptTemplate if still needed for other purposes
```

2. **Replace agent creation**:
```python
# OLD (lines 107-125)
self.agent = create_react_agent(
    llm=self.llm, tools=self.tools, prompt=self._build_prompt()
)

self.agent_executor = AgentExecutor(
    agent=self.agent,
    tools=self.tools,
    verbose=True,
    max_iterations=30,
    max_execution_time=180,
    handle_parsing_errors="...",
    callbacks=[self.summarizer],
)

# NEW
# Convert prompt template to system_prompt string
system_prompt = self._build_system_prompt()  # New method

self.agent = create_agent(
    model=self.llm,  # Direct model, not wrapped
    tools=self.tools,
    system_prompt=system_prompt,
    # Note: max_iterations, callbacks may need different handling
    # Check v1.0 docs for equivalent parameters
)
```

3. **Update _build_prompt() → _build_system_prompt()**:
```python
# OLD
def _build_prompt(self):
    return PromptTemplate.from_template(AGENT_PROMPT_TEMPLATE)

# NEW
def _build_system_prompt(self) -> str:
    """
    Convert prompt template to system prompt string.
    Extract the system instructions from AGENT_PROMPT_TEMPLATE.
    """
    # AGENT_PROMPT_TEMPLATE likely contains:
    # - System instructions
    # - Tool descriptions (handled automatically by create_agent)
    # - Format instructions
    
    # Extract just the system instructions part
    # This may require manual extraction from AGENT_PROMPT_TEMPLATE
    # Check src/llm/config.py for AGENT_PROMPT_TEMPLATE content
    
    # For now, return a simplified version:
    return """You are a Census data expert helping users query the Census API.

REASONING PROCESS:
1. Understand what the user wants
2. Use geography_discovery to find areas/levels
3. Use table_search to find relevant tables
4. Use table_validation to check compatibility
5. Use census_api_call to fetch data
6. Decide if charts or tables are needed
7. Return structured output

Use ReAct format:
Thought: [reason about what to do next]
Action: [tool name]
Action Input: [tool input as JSON]
Observation: [tool result]
... (repeat until you have the answer)

Final Answer: Return JSON with census_data, data_summary, reasoning_trace, charts_needed, tables_needed, answer_text."""
```

#### Step 2.2: Update agent.solve() Method

**File**: `src/utils/agents/census_query_agent.py`

**Changes Required**:

```python
# OLD (line 151)
result = self.agent_executor.invoke(
    {
        "input": f"""User query: {user_query}
        Intent: {intent}"""
    }
)

# NEW
# create_agent returns a Runnable that uses messages format
result = self.agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": f"""User query: {user_query}
Intent: {intent}"""
        }
    ]
})
```

**IMPORTANT**: Output format may differ. Need to verify:
- Does `result` still have `"output"` key?
- Does `result` still have `"intermediate_steps"`?
- How are callbacks handled?

#### Step 2.3: Handle Callbacks and Configuration

**Problem**: `AgentExecutor` had `callbacks`, `max_iterations`, `max_execution_time` parameters.

**Solution**: Check v1.0 API for equivalent:
- Callbacks: May need to use `RunnableConfig` or different callback mechanism
- Max iterations: May be handled differently in v1.0
- Error handling: `handle_parsing_errors` may not exist

**Action**: Review LangChain v1.0 docs for:
- Callback integration
- Iteration limits
- Error handling

#### Step 2.4: Update Output Parsing

**File**: `src/utils/agents/census_query_agent.py`

**Changes Required**:

The `_parse_solution()` method expects:
```python
output = result.get("output", "")
intermediate_steps = result.get("intermediate_steps", [])
```

**Verification Needed**: After migration, test what `result` structure looks like:
```python
# Add debug logging
logger.info(f"Agent result keys: {result.keys()}")
logger.info(f"Agent result type: {type(result)}")
logger.info(f"Agent result sample: {str(result)[:500]}")
```

**Potential Changes**:
- If output format changed, update `_parse_solution()` accordingly
- If `intermediate_steps` format changed, update parsing logic

---

### Phase 3: Prompt Template Migration (1 hour)

#### Step 3.1: Review AGENT_PROMPT_TEMPLATE

**File**: `src/llm/config.py`

**Action**: Read `AGENT_PROMPT_TEMPLATE` and identify:
1. System instructions (→ `system_prompt`)
2. Tool descriptions (handled automatically by `create_agent`)
3. Format instructions (may need to be in `system_prompt`)
4. Examples (may need to be in `system_prompt`)

#### Step 3.2: Extract System Prompt

**File**: `src/utils/agents/census_query_agent.py`

**Action**: Create `_build_system_prompt()` that extracts relevant parts from `AGENT_PROMPT_TEMPLATE`.

**Current AGENT_PROMPT_TEMPLATE Structure** (from `src/llm/config.py:192-454`):
- Tool descriptions (`{tools}` placeholder) → **REMOVE** (handled automatically by `create_agent`)
- ReAct format instructions → **KEEP** (system instructions)
- Tool usage guide → **KEEP** (system instructions)
- Critical reasoning checklist → **KEEP** (system instructions)
- Geography token mapping → **KEEP** (system instructions)
- Error recovery playbook → **KEEP** (system instructions)
- Answer text requirements → **KEEP** (system instructions)
- Output format rules → **KEEP** (system instructions)
- Multi-year time series → **KEEP** (system instructions)
- Output generation guidelines → **KEEP** (system instructions)
- `{input}` placeholder → **REMOVE** (handled by messages format)
- `{agent_scratchpad}` placeholder → **REMOVE** (handled automatically)

**Implementation**:
```python
def _build_system_prompt(self) -> str:
    """
    Convert AGENT_PROMPT_TEMPLATE to system_prompt string for create_agent.
    
    Note: create_agent automatically includes:
    - Tool descriptions (no need to include {tools})
    - Tool names (no need to include {tool_names})
    - Agent scratchpad (no need to include {agent_scratchpad})
    - Input handling (no need to include {input})
    
    We extract only the system instructions and format rules.
    """
    # Extract the core instructions from AGENT_PROMPT_TEMPLATE
    # Remove placeholders: {tools}, {tool_names}, {input}, {agent_scratchpad}
    
    return """You are a Census data expert helping users query the Census API.

CRITICAL OUTPUT FORMAT RULE:
You MUST ALWAYS output your final answer in this EXACT format:

Thought: I now know the final answer
Final Answer: {complete JSON on single line}

NEVER output bare JSON without the "Final Answer:" prefix.
NEVER return tool output directly as your final answer.
ALWAYS wrap your final JSON response with "Final Answer:" prefix.

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of the available tools
Action Input: the input to the action as valid JSON
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

[Include all the tool usage guides, reasoning checklists, geography mappings,
error recovery playbook, answer text requirements, output format rules,
multi-year time series instructions, and output generation guidelines from
AGENT_PROMPT_TEMPLATE - but remove {tools}, {tool_names}, {input}, {agent_scratchpad}]

When you have gathered all data and are ready to provide the final answer:
1. Write "Thought: I now know the final answer" on its own line
2. Write "Final Answer: " followed by the complete JSON on the SAME line
3. NEVER output bare JSON without the "Final Answer:" prefix
4. The JSON must include all 7 required keys: census_data, data_summary, reasoning_trace, answer_text, charts_needed, tables_needed, footnotes"""
```

**Note**: The full system prompt will be ~200-300 lines. Consider extracting it to a separate constant in `src/llm/config.py` for maintainability.

---

### Phase 4: Testing & Validation (1-2 hours)

#### Step 4.1: Unit Tests

**Files to Update**:
- `app_test_scripts/test_integration_agent_api.py`
- Any other agent tests

**Tests to Run**:
```bash
# Test agent creation
uv run python -c "
from src.utils.agents.census_query_agent import CensusQueryAgent
agent = CensusQueryAgent()
print('Agent created successfully')
"

# Test agent invocation (if API key available)
uv run pytest app_test_scripts/test_integration_agent_api.py -v
```

#### Step 4.2: Integration Tests

**Test from main.py**:
```bash
uv run python main.py
# Enter test query: "What is the population of California?"
# Verify: No errors, correct output format
```

**Test from Streamlit**:
```bash
uv run streamlit run streamlit_app.py
# Enter test query, verify functionality
```

#### Step 4.3: End-to-End Validation

**Run all existing tests**:
```bash
uv run pytest app_test_scripts/ -v
```

**Expected Results**:
- All existing tests should pass (may need minor updates)
- Agent should produce same output format
- No deprecation warnings

#### Step 4.4: Verify Output Format Compatibility

**Create test script**:
```python
# test_v1_compatibility.py
from src.utils.agents.census_query_agent import CensusQueryAgent

agent = CensusQueryAgent()
result = agent.solve(
    user_query="What is the population of California?",
    intent={"is_census": True, "topic": "population"}
)

# Verify structure matches expected format
assert "census_data" in result
assert "answer_text" in result
assert "reasoning_trace" in result
# ... etc
```

---

### Phase 5: Handle Edge Cases & Deprecations (1 hour)

#### Step 5.1: Check for Deprecation Warnings

**Action**: Run application and check for warnings:
```bash
uv run python main.py 2>&1 | grep -i "deprecat\|warn"
```

**Common Issues**:
- `PromptTemplate` usage (if still used elsewhere)
- `AgentExecutor` references (should be removed)
- Other deprecated APIs

#### Step 5.2: Update Error Handling

**File**: `src/utils/agents/census_query_agent.py`

**Changes**: If `handle_parsing_errors` is removed, update error handling:
```python
# OLD
handle_parsing_errors="Check your output format..."

# NEW
# May need try/except around agent.invoke() instead
try:
    result = self.agent.invoke(...)
except Exception as e:
    # Handle parsing errors manually
    logger.error(f"Agent parsing error: {e}")
    return self._build_error_response(e)
```

#### Step 5.3: Update Callback Integration

**File**: `src/utils/agents/census_query_agent.py`

**Problem**: `ConversationSummarizer` callback may need different integration.

**Solution**: Check v1.0 callback API:
```python
# OLD
callbacks=[self.summarizer]

# NEW (may be)
from langchain_core.runnables import RunnableConfig
config = RunnableConfig(callbacks=[self.summarizer])
result = self.agent.invoke(..., config=config)
```

---

## Rollback Plan

### If Migration Fails

1. **Revert Dependencies**:
   ```bash
   # Restore pyproject.toml to langchain==0.3.27
   uv sync
   ```

2. **Revert Code Changes**:
   ```bash
   git checkout src/utils/agents/census_query_agent.py
   git checkout src/llm/config.py
   ```

3. **Verify Rollback**:
   ```bash
   uv run pytest app_test_scripts/ -v
   # All tests should pass
   ```

---

## Success Criteria

### Functionality: 🟢/🟡/🔴
- [ ] Agent creates without errors
- [ ] Agent executes queries successfully
- [ ] Output format matches expected structure
- [ ] All tools work correctly
- [ ] Callbacks function (ConversationSummarizer)

### Integration: 🟢/🟡/🔴
- [ ] `main.py` works end-to-end
- [ ] `streamlit_app.py` works end-to-end
- [ ] Graph compilation succeeds
- [ ] Memory system works

### Testing: 🟢/🟡/🔴
- [ ] All existing unit tests pass
- [ ] All integration tests pass
- [ ] End-to-end workflows work
- [ ] No deprecation warnings

### Documentation: 🟢/🟡/🔴
- [ ] Code comments updated
- [ ] Migration notes documented
- [ ] Breaking changes documented

---

## Known Issues & Risks

### High Risk Areas

1. **Agent Output Format**: `create_agent` may return different structure than `AgentExecutor`
   - **Mitigation**: Add extensive logging, test output parsing early

2. **Callback Integration**: `ConversationSummarizer` may not work with new API
   - **Mitigation**: Check v1.0 callback docs, test callback functionality

3. **Error Handling**: `handle_parsing_errors` may be removed
   - **Mitigation**: Implement manual error handling

4. **Prompt Template**: Complex prompts may need restructuring
   - **Mitigation**: Start with simple system_prompt, iterate

### Medium Risk Areas

1. **Tool Compatibility**: Tools should work, but verify
2. **LangGraph Integration**: Should be compatible, but test graph compilation
3. **Provider Integrations**: OpenAI/Anthropic/Google should work, but verify

---

## Timeline Estimate

| Phase | Task | Time | Risk |
|-------|------|------|------|
| 1 | Dependency Updates | 30 min | Low |
| 2 | Agent Migration | 2-3 hours | High |
| 3 | Prompt Template | 1 hour | Medium |
| 4 | Testing & Validation | 1-2 hours | Medium |
| 5 | Edge Cases | 1 hour | Medium |
| **Total** | | **5.5-7.5 hours** | |

---

## Next Steps

1. **Review this plan** with team/stakeholders
2. **Create feature branch**: `git checkout -b migrate/langchain-v1`
3. **Start with Phase 1** (dependency updates)
4. **Test incrementally** after each phase
5. **Document any deviations** from this plan

---

## References

- [LangChain v1 Migration Guide](https://docs.langchain.com/oss/python/migrate/langchain-v1)
- [LangChain v1 Release Notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangGraph v1 Migration Guide](https://docs.langchain.com/oss/python/migrate/langgraph-v1)
- [LangChain v1 create_agent API](https://docs.langchain.com/oss/python/langchain/overview)

---

**Last Updated**: 2025-01-XX  
**Status**: Ready for Implementation


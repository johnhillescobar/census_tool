# Phase 1: Common Errors and How to Spot Them Early

This document summarizes the most frequent errors encountered during Phase 1 (type fixes, import/refactor, and small behavioral fixes) and gives concrete advice on how to catch them while coding and why they occurred.

---

## 1. Return type vs actual return value

### What happened
- Functions declared to return `Dict` or `List[str]` but had a code path that returned nothing (e.g. `pass` or early return without value), so the checker reported *"Function must return value on all code paths"* or *"None is not assignable to Dict"*.
- Example: `parse_census_response` and `handle_api_errors` used `pass` but were typed as `-> Dict`.

### Why it happened
Return type was written to describe the “happy path” only; error or stub paths were left returning nothing.

### How to spot it early
- After writing a return type, **trace every exit** from the function (all `return`, and falling off the end). Ensure each returns a value of that type.
- Use the linter/type checker on save; it will flag missing returns as soon as you add the annotation.

### Fix
- Stub / error path: `return {}` or `return []` so every path returns the declared type.
- If some paths really return “no result”, change the return type to `Dict | None` and document when `None` is returned.

---

## 2. Default `None` but parameter typed as non-optional

### What happened
- Parameters like `variables: List[str] = None` caused *"Expression of type None is not assignable to parameter of type List[str]"*.
- Same idea for `intent: Dict[str, Any] = None` when the annotation was `Dict`, not `Dict | None`.

### Why it happened
The default was added for convenience without updating the type to allow `None`.

### How to spot it early
- For any parameter that has `= None`, the type must include `None`: use `T | None`.
- If the type stays non-optional, use a sentinel default (e.g. empty list) or require the argument.

### Fix
- Annotate as `List[str] | None = None`.
- Before using the value in a way that assumes “non-None” (e.g. `",".join(variables)`), add a guard: `if not variables: raise ValueError(...)` so the type checker can narrow the type.

---

## 3. Using “constructor” types in type hints (e.g. Chroma)

### What happened
- Using `chromadb.PersistentClient` or `chromadb.Collection` in parameter/return types led to *"Expected class but received (path: str | Path = ..."* (the constructor signature).
- Using `OpenAIEmbeddingFunction` where the API expected `EmbeddingFunction[Embeddable]` caused variance/generic mismatches.

### Why it happened
In Chroma’s stubs, `PersistentClient` is typed as a callable (the constructor), not as a class type. The public type for “a client” is the interface `ClientAPI`.

### How to spot it early
- When the linter says “Expected class but received …” on a type from a third-party library, check that library’s types for an **interface or protocol** (e.g. `ClientAPI`, `EmbeddingFunction[Embeddable]`) and use that in annotations.
- If the library only exposes a concrete constructor and no public interface type, use `cast(...)` or `Any` at the call site and add a short comment.

### Fix
- Use `from chromadb.api import ClientAPI` and annotate as `ClientAPI` instead of `chromadb.PersistentClient`.
- For embedding functions that don’t satisfy the generic: `embedding_function=cast(Any, self.embedding_function)` with a one-line comment.

---

## 4. Dict/typed structure known only as `object` or “unknown”

### What happened
- Code like `"county" in result["available_levels"]` or `"B01003_001E" not in result["invalid"]` failed with *"Operator 'in' / 'not in' not supported for types 'Literal[...]' and 'object'"*.
- `result["source"]["B01003_001E"]` caused *"__getitem__ not defined on type object"*.

### Why it happened
Functions were annotated to return `Dict[str, object]` (or the checker inferred it). So `result["available_levels"]` and `result["invalid"]` were inferred as `object`, and the checker correctly disallows `in`/`not in` or `__getitem__` on `object`.

### How to spot it early
- As soon as you **index a return value and use it** (e.g. `result["key"]` and then `x in result["key"]`), the return type of the function should describe that structure.
- Prefer a **TypedDict or a small dataclass** for structured dict returns so the type of each key is known.

### Fix
- Introduce a TypedDict (e.g. `GeographySupportResult`, `VariableValidationResult`) with the right value types (`available_levels: List[str]`, `invalid: List[str]`, etc.) and use it as the return type.
- If the module is imported via a package and the checker still sees `object`, import the module directly (e.g. `import src.services.variable_validator as variable_validator`) so the checker sees the concrete return type.

---

## 5. Optional / possibly-None values used without a guard

### What happened
- `st.session_state.user_id` passed to a function that expects `str` → *"str | None is not assignable to str"*.
- `match.lastindex >= 1` → *"Operator '>=' not supported for None"* (because `lastindex` is `int | None`).
- `test_results["metadatas"][0]` → *"Object of type None is not subscriptable"* when `metadatas` can be missing or None.
- `self.agent_executor.invoke(...)` → *"invoke is not a known attribute of None"* when `agent_executor` can be None.

### Why it happened
Variables that can be `None` (or missing in a dict) were used in a context that assumes a non-None value, and the type checker enforced that.

### How to spot it early
- For any variable that comes from config, session state, or optional attributes, **assume it can be None** until you guard it.
- Before subscripting (e.g. `x["key"][0]`), ask: can `x["key"]` be None or missing? If yes, use `.get()` and an explicit check.

### Fix
- Use a default: `st.session_state.user_id or "demo"`.
- For optional ints: `match.lastindex is not None and match.lastindex >= 1`.
- For nested access: `metadatas = test_results.get("metadatas"); if metadatas and len(metadatas) > 0: ...`.
- For optional attributes: `if self.agent_executor is None: raise RuntimeError(...)` then use `self.agent_executor`.

---

## 6. Wrong or missing import / symbol

### What happened
- `from src.clients.chroma_utils import chroma_utils` → *"chroma_utils is unknown import symbol"* (the module is named chroma_utils; you don’t import a module from itself).
- `from .telemetry import log_user_input, log_answer_text, ...` when only `record_event` existed → unknown import symbol.
- `from .conversation_summarizer import summarize_conversation` when the real function was `summarize_intermediate_steps` → unknown import symbol.
- Tests still importing from `src.utils.*` after code moved to `src.clients`, `src.services`, `src.domain` → import errors or wrong behavior.

### Why it happened
Imports were written from memory or from old code; the actual module exports (or new package layout) weren’t checked.

### How to spot it early
- After moving or renaming a module/function, **run a project-wide search** for the old path or name and update every reference.
- Before adding an import, **open the target module** and confirm the symbol exists (e.g. `__all__` or the definition).

### Fix
- Import the module: `from src.clients import chroma_utils` (or `import src.clients.chroma_utils as chroma_utils`).
- Align `__init__.py` with actual exports: e.g. `from .telemetry import record_event` and `from .conversation_summarizer import summarize_intermediate_steps as summarize_conversation`.
- Update all tests and call sites to the new package paths (e.g. `src.services.dataset_geography_validator`, `src.domain.geography_registry`).

---

## 7. Mutating a TypedDict or “read-only” shaped dict

### What happened
- `result.update({"table_code": payload.table_code})` on the return value of `geography_supported()` caused *"No overloads for update match the provided arguments"* because the return type is a TypedDict and you’re adding a key not in that type.

### Why it happened
The return type was tightened to a TypedDict, but the caller kept mutating the returned dict to add extra keys.

### How to spot it early
- When you add a **TypedDict (or similar) return type**, look for any caller that **mutates** the return value (`.update()`, `[...] = ...`). Those callers need to work with a new dict or an extended type.

### Fix
- Don’t mutate; build a new dict: `response = {**result, "table_code": payload.table_code}` and use `response` for the rest of the logic and for `json.dumps(response)`.

---

## 8. Missing required constructor arguments (e.g. Pydantic/state)

### What happened
- `CensusState(messages=[...], intent=None, ...)` caused *"Argument missing for parameter original_query"*.
- Same for tests that built `CensusState` or called `memory_load_node(state, config)` with a plain dict instead of a `CensusState` instance.

### Why it happened
New fields were added to the state model (e.g. `original_query`) or the function signature was tightened to a proper type, but not every construction site was updated.

### How to spot it early
- After adding a **new required field** to a Pydantic model or dataclass, search for every place that constructs it and add the new argument (or a default in the model).
- When a function’s first parameter is typed as a specific model (e.g. `CensusState`), ensure callers pass that type, not a plain dict.

### Fix
- Add the missing keyword argument everywhere you construct the model (e.g. `original_query=user_input` or `original_query=None`).
- In tests, build a real instance: `state = CensusState(messages=[], original_query=None, ...)` and use typed config (e.g. `RunnableConfig`) if required.

---

## 9. Using the wrong attribute name or initialization order

### What happened
- `main()` used `builder.collection` before calling `builder.build_index()`. `collection` is only set inside `initialize_chroma()`, which is called from `build_index()`, so running `main()` without building the index caused `AttributeError: 'CensusTableIndexBuilder' object has no attribute 'collection'`.

### Why it happened
The script was written to “test the collection” without ensuring the initialization path that sets `collection` had been run.

### How to spot it early
- For any object that has “lazy” or “initialized in method X” attributes, **document or enforce order**: e.g. “call `build_index()` before using `collection`,” or set `collection = None` in `__init__` and assert it’s not None before use.
- When adding a new code path (e.g. a `main()` that only runs queries), trace which attributes it uses and which methods set them; then ensure those methods are called first.

### Fix
- Call the initializer before using the attribute: at the start of `main()`, call `builder.build_index(year=2023)` before any `builder.collection.query(...)`.

---

## 10. Duplicate method definitions in the same class

### What happened
- The same method name (e.g. `_did_reach_iteration_limit`, `_build_iteration_limit_response`) was defined twice in one class, leading to *"Method declaration ... is obscured by a declaration of the same name"*.

### Why it happened
Copy-paste or merge left two versions of the same method; the second overwrote the first at runtime, and the type checker reported the shadowing.

### How to spot it early
- After a large edit or merge, **grep for the method name** in that file and ensure it’s defined only once (or that you intentionally have a subclass override).
- Run the type checker; “obscured by a declaration” points directly to duplicate definitions.

### Fix
- Keep a single definition (usually the more complete or correct one) and delete the duplicate.

---

## 11. Data consistency (e.g. history vs usage_stats)

### What happened
- `history` was cleared to `[]` but `usage_stats` (e.g. `total_queries`, `success_queries`, `last_query_date`) were left at old values, so the data looked inconsistent (e.g. “358 successful queries” but empty history).

### Why it happened
Two related pieces of state were updated in different places or only one was cleared when “resetting” the user.

### How to spot it early
- When you have **derived or redundant state** (counters, last date, list length), define a single rule: “when X is reset, Y and Z are reset (or recomputed) too,” and enforce it in one place (e.g. when clearing history, also reset usage_stats).
- Optionally add a small consistency check or test (e.g. “if history is empty, usage_stats totals should be 0”).

### Fix
- Manually align the file once (e.g. set `total_queries`/`success_queries` to 0 and `last_query_date` to null when history is empty).
- In code, whenever history is cleared or reset, also reset or recalculate usage_stats in the same code path.

---

## 12. Third-party API expectations (Chroma `where`, BeautifulSoup `Tag`)

### What happened
- Passing a plain dict to `collection.get(where={...})` caused *"Argument of type dict[...] cannot be assigned to parameter where of type Where | None"*.
- Using `row.find_all("td")` when `row` was typed as `PageElement` caused *"Cannot access attribute find_all for class PageElement"*.

### Why it happened
Libraries use strict or recursive types (`Where`, `Metadata`) or base types (`PageElement`) that don’t have the methods you need; the concrete type (e.g. `Tag`) is only known after you know the query result shape.

### How to spot it early
- When the linter complains about **argument type** for a library parameter, check that library’s types (or stubs) for the exact expected type (e.g. `Where`, `ChatPromptTemplate`).
- When it complains about **attribute not found on base type**, use the concrete type (e.g. `Tag`) and narrow with a cast after you’ve ensured the value is actually that type (e.g. from `find_all("tr")`).

### Fix
- Chroma `where`: `where=cast(Where, {"$and": [...]})`.
- BeautifulSoup: assign to a variable then `row = cast(Tag, row_el)` (or similar) so the checker knows `row` has `find_all`.

---

## Quick checklist while coding

1. **Return types**: Every code path returns a value of the declared type (or change the declaration).
2. **Optional params**: Any `= None` parameter is typed as `T | None`; guard before using as `T`.
3. **Third-party types**: Use the library’s interface/protocol types in annotations; use `cast` or `Any` only where the API accepts it but the stub doesn’t.
4. **Structured returns**: Use TypedDict (or similar) for dict returns that are indexed later; avoid `Dict[str, object]` for “known shape” returns.
5. **None safety**: Guard or default any value that can be None before using it (subscript, attribute, operator).
6. **Imports**: After renames/moves, search and update all references; confirm exported symbols in the target module.
7. **No mutation of typed dicts**: Prefer building a new dict (e.g. `{**result, "extra": value}`) over mutating a TypedDict return.
8. **Model construction**: When adding required fields, update every constructor call; use real model instances in tests, not plain dicts.
9. **Initialization order**: Ensure any attribute that’s set in a method is not used before that method is called (or add an explicit check).
10. **Single definition**: After big edits, confirm no duplicate method names in the same class.
11. **Consistent state**: When resetting or clearing one part of state (e.g. history), reset or recalc related state (e.g. usage_stats) in the same place.
12. **Library types**: For strict library parameters or base types, use the exact type or a safe cast and a one-line comment.

Using this checklist and fixing issues as the linter reports them will catch most of these Phase 1 errors during coding instead of later in integration or production.

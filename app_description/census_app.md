# CENSUS GRAPH APP 

## Build a local Census QA app that:
* Parses a user’s intent (is it a Census question; single vs. series/table).
    * Resolves geo hints like “NYC” into valid Census API for/in filters across multiple summary levels.
    * Retrieves relevant Census variables from a Chroma index of variables metadata.
    * Plans one or more API calls across years, respecting API constraints (variable limits).
    * Fetches results with retries/backoff, saves them locally, caches them for 90 days (with an optional size cap), and  refreshes cache timestamps on access.
    * Answers with a single value or a small table preview; includes dataset/variable footnotes.
    * Maintains conversation state (thread memory), user preferences, and full history for 90 days.
    * Runs entirely local; only external calls are to the public Census API.

## Project structure Cursor must create

    requirements.txt
    index/build_index.py (one-time Chroma index builder)
    app.py (LangGraph app, nodes, REPL)
    data/ (runtime: fetched CSV/Parquet)
    memory/ (runtime: user profiles/history, cache index)
    chroma/ (Chroma persistent store)
    checkpoints.db (LangGraph checkpointer)
    
## Required packages

    langgraph
    chromadb
    sentence-transformers
    pandas
    requests
    typing-extensions
    numpy
Global configuration (to be implemented as constants at the top of app.py and build_index.py)

### Retention:
    * RETENTION_DAYS default 90; automatically prune history entries and cache files older than cutoff.
    * Optional: CACHE_MAX_FILES (e.g., 2,000) and CACHE_MAX_BYTES (e.g., 2 GB). If either exceeded on save, evict least-recently-used entries older than the cutoff first, then by oldest timestamp until under limits.

### Census datasets to index (in index/build_index.py):
    * acs/acs5 for years 2012–2023 (default).
    * Optional entries prepared but commented: acs/acs1 for 2012–2023, dec/pl for 2020.
    * Clear TODO to add more datasets/years later. Index builder aggregates years_available per (dataset, var).

### Chroma collection:
    * Persistent location: ./chroma
    * Collection name: census_vars
    * Embedding model: text-embedding-3-large.

### Census API:
    * Request timeout: 30 seconds.
    * Retries: 6 total, exponential backoff (e.g., 0.5s, 1s, 2s) on network errors and 5xx responses. Respect 429 by waiting the Retry-After header if present, else backoff.
    * Variable per-call limit: enforce a conservative maximum, e.g., 48 variables per request. Split queries if needed. Always include NAME.

### Concurrency:
    * For multi-year plans, fetch in parallel up to MAX_CONCURRENCY (e.g., 5). Use a thread pool or similar. Do not exceed safe parallelism to avoid rate limits.

### File formats:
    * Save CSV by default (simple). Include a TODO comment to switch to Parquet later for speed. Always include a preview in memory (first ~5 rows) and keep full data only on disk.

## State schema and merge rules (reducers)
Cursor must implement the state keys and exact merge behavior below:

    * messages: list of chat turns; reducer: append.
    * intent: dict; reducer: overwrite. Fields: is_census, answer_type (“single” | “series” | “table”), measures (list of strings like population, median_income, hispanic), time (year or start_year/end_year), geo_hint, needs_clarification (bool).
    * geo: dict; reducer: overwrite. Fields: level (place | state | county | tract | block group | nation | metro area), filters (dict of for/in parts), note (optional).
    * candidates: dict; reducer: overwrite. Fields: variables (list of candidate variables), years (list), notes (optional).
    * plan: dict; reducer: overwrite. Fields: queries (list of QuerySpec), needs_agg (bool), agg_spec (optional).
    * artifacts: dict; reducer: merge dictionaries. Fields: datasets (save_as -> file handle), previews (save_as -> sample rows).
    * final: dict; reducer: overwrite. Fields: answer_text, table_path (optional), preview (optional), footnote (optional).
    * logs: list of strings; reducer: append. One short, timestamped entry per node.
    * error: string; reducer: overwrite.
    * profile: dict; reducer: merge dictionaries. Fields: user_id, default_geo, preferred_dataset, default_year_range, preferred_level, var_aliases (map measure phrases -> variable codes).
    * history: list; reducer: append. Each item includes question, timestamp, intent snapshot, geo, plan summary (dataset, var, years, n_queries), artifact keys, and outcome (“ok” or error message).
    * cache_index: dict; reducer: merge dictionaries. Signature -> file handle and metadata (including timestamp). Prune by age and optional size caps at load/save.
    * summary: optional string; reducer: overwrite. A short summary when messages get long.

## Graph nodes and responsibilities

### memory_load

    * Input: config must include configurable.user_id and configurable.thread_id.
    * Load user profile and history JSON from ./memory/user_{user_id}.json. Prune history items older than RETENTION_DAYS.
    * Load cache index from ./memory/cache_index.json. Prune entries older than RETENTION_DAYS; delete the corresponding files; also enforce optional size caps.
    * Output: profile, history, cache_index; one log line.

### summarizer (optional but required if messages exceed a threshold, e.g., 20 turns)

    * If messages exceed a threshold, create a short summary string of the conversation so far and trim messages to last few turns (e.g., 8). The summary stays in state so later nodes can read it.
    * Output: summary (string) and trimmed messages; one log line.
    * This keeps prompts lean without losing context.

### intent

#### Heuristic (LLM-free) intent parsing with robust rules:
    * is_census true if key terms like census, population, population of, income, median income, ACS, tract, county, place, decennial appear.
    * answer_type:
        * “single” if appears to ask for one value or a specific year.
        * “series” if phrases like from YEAR to YEAR, trend, over time, yearly, years present.
        * “table” if breakdown, by county, by tract, across, compare present.
    * measures:
        * Normalize synonyms: hispanic ~ latino. Recognize population, median_income, unemployment, education (placeholders for future), etc.
        * If user profile has var_aliases for a measures phrase, store a hint to boost retrieval.
    * time:
        * Extract four-digit years; if one year appears, set that; if two or more, set start_year and end_year; else default to the most recent indexed year (latest ACS 5-year).
    * geo_hint:
        * If user mentions NYC or New York City, set geo_hint accordingly; else keep raw user text for resolver.
    * needs_clarification:
        * True if the question is ambiguous (no obvious measure, no recognizable geo, or conflicting signals).
#### Output: intent; one log line.

### router_from_intent
    * If intent.is_census is false → not_census.
    * Else if intent.needs_clarification true → clarify.
    * Else → geo.

### clarify

#### Purpose: ask a targeted follow-up when retrieval would likely fail:
    * Example prompts: “Do you want total population (B01003_001E) or another measure?”, “Which geography level do you prefer: place (NYC city), counties, or tracts?”, “Confirm year range 2012–2023?”

#### Behavior:
    * Compose a short assistant message that asks up to two clarifying questions.
    * Set final.answer_text to that question and end the turn so the user can respond.
    * Do not modify plan/data.

#### Output: final and messages; one log line.

### geo
#### Resolve geo_hint into a supported level and filters. Required levels to support now:
    * place: for=place:PLACE&in=state:STATE (example: NYC: state 36, place 51000).
    * state: for=state:STATE.
    * county: for=county:COUNTY&in=state:STATE (support specific county and county:*).
    * nation: for=us:1 (when user asks for national).
#### Tract and block group: mark as planned support with clear TODO and friendly error if requested now. Provide the expected for/in structure in comments: for=tract:&in=state:SS&in=county:CCC; for=block group:&in=state:SS&in=county:CCC&in=tract:TTTTTT.
#### Defaults:
    * If profile.default_geo exists, use it.
    * If unresolved, default to NYC place (state 36, place 51000).
#### Output: geo; one log line.

### retrieve
#### Build the Chroma query string from:
    * measures (join words), plus synonyms (add “latino” when “hispanic” present).
    * answer_type (to hint series/table).
    * time hint (“year YYYY” or “years YYYY to YYYY”).
    * dataset hint (“dataset:acs/acs5” by default or profile.preferred_dataset).
    * If profile.var_aliases has a mapping for the measures phrase, prepend that var code to the query string to boost relevance.
#### Query Chroma for top K candidates (e.g., 12).
#### Scoring:
    * Combine embedding similarity with keyword boosts:
        * +boost if the variable label or concept contains exact words like “population,” “median,” “Hispanic or Latino”.
        * +boost if var code ends with “_001E” (main estimate).
    * Compute a final confidence score.
#### Select candidates whose years_available intersect the requested years (if any).
#### If none found:
    * Provide sensible fallbacks (e.g., population → B01003_001E; Hispanic median income → B19013I_001E).
    * Or route to clarify with a short assistant message asking for a more specific measure.
#### Output: candidates with variables (include var, label, concept, dataset, years_available, score) and years suggestion (intersection of requested with available or most recent); one log line.

### plan
#### Inputs: intent, geo, candidates.
#### Choose the best candidate by highest score. If confidence is low (below a threshold), route to clarify instead with a gentle message (“I found multiple possible measures. Do you mean X or Y?”).
#### Years:
    * If intent has year, use it if available; else most recent available.
    * If start/end range present, intersect with availability.
#### Variable-per-call limit:
    * Always include NAME.
    * If there are multiple variables needed (future scope), split into batches under the max limit (e.g., 48).
#### Build QuerySpec items:
    * year, dataset (from candidate), variables ([var, NAME]), geo, save_as (var_level_year).
#### Validate geo + dataset:
    * If the chosen dataset doesn’t support the requested level (e.g., if future datasets have constraints), route to clarify with a suggestion or fall back to a supported level (configurable policy).
#### Output: plan with list of QuerySpec, needs_agg false by default; one log line.

### data
#### For each QuerySpec:
    * Compute a stable signature from year, dataset, sorted variables, and normalized geo filters.
    * Check cache_index for signature:
        * If hit: verify file exists; refresh timestamp; load preview rows.
        * If missing file: treat as miss and refetch.
    * If miss: fetch with retries/backoff. Handle 429s and 5xx politely. Abort only after exhausting retries; on abort, set error and a friendly message.
    * Parse JSON: first row headers, subsequent rows data. Cast numeric columns to numeric where sensible; add a “year” column (int).
    * Save CSV to data/ under the save_as name; create a handle (path, n_rows, n_cols, year, dataset, timestamp).
    * Update datasets and previews; update cache_index with the handle and the signature; ensure cache retention is enforced after updates (age and optional size cap).
#### Concurrency:
    * Execute multi-year queries in parallel up to MAX_CONCURRENCY. Aggregate results; if any fail, continue others and report partial success in logs and final footnote.
#### Output: artifacts (datasets and previews) and updated cache_index; one log line.

### answer
#### Inputs: intent, artifacts.
#### If no datasets present: return a friendly failure message and suggest rephrasing; include error state if set.
#### Single:
    * Load the first dataset; choose the main variable column (exclude NAME and geo id columns).
    * Prefer estimate columns ending with “E” when codes provide E/M variants (E=estimate, M=margin of error). If both present, use E for the value and include M in a footnote if available.
    * Format value with thousands separators. Return a concise sentence containing the number, year, dataset (e.g., ACS 5-year), and the geography name from NAME.
#### Series/table:
    * Load all datasets by handle, union them, keep relevant columns, ensure year is int and sort by year. If needed, pivot to year-by-value; otherwise return stacked rows.
    * Save a consolidated CSV (e.g., data/result_table.csv). Provide a small preview (first 10 rows).
    * Return an answer_text summarizing what the table contains, attach table_path, and include a footnote with dataset and variable code(s).
#### Footnote:
    * Compose a short footnote with dataset name, variable code, and a reminder that values come from the Census Bureau API.
#### Output: final (answer_text, preview/table_path as applicable, footnote), messages with a user-facing answer, and a log line.

### memory_write
#### Build a history record:
    * question (last user message), timestamp, intent, resolved geo, plan summary (dataset, var, years, n_queries), artifact keys, outcome.
#### Update profile:
    * default_geo from resolved geo (if none stored), preferred_dataset from plan, and optionally var_aliases mapping the measures phrase to the chosen var.
#### Persist:
    * Save or update memory/user_{user_id}.json with pruned history (90-day window).
    * Persist updated cache_index; enforce retention rules on save (age and optional size caps), deleting old files as needed.
    Output: none besides logs.

#### Pnot_census
* Return a brief assistant message: the question doesn’t look Census-related; give examples of valid requests and invite to rephrase.

## Control flow (edges)
    * start → memory_load → summarizer (if needed) → intent
    * intent routes:
        * if not census → not_census → end
        * if needs clarification → clarify → end (await user reply)
    * else → geo
    * geo → retrieve → plan → data → answer → memory_write → end

## Chroma variable index (index/build_index.py) — functional expectations

### Inputs:
    * A configuration list of dataset-year ranges (default: acs/acs5 2012–2023; provide commented options for acs/acs1 and dec/pl).
### Fetch variables.json for each year in each dataset with polite pacing.
### Aggregate by (dataset, var), collecting a years_available set.
### Document text:
    * Combine label, concept, universe, and dataset name to help semantic matching.
### Metadata:
    * var, label, concept, universe, dataset, years_available (sorted list of ints).
### Upsert documents in manageable batches; handle id collisions; show progress logs.
### Persist collection to ./chroma.


## Retrieval algorithm refinements

Build the query string using:
measures (+ synonyms),
answer_type,
time hints,
dataset hint (prefer profile.preferred_dataset; default acs/acs5).
Scoring enhancements:
Give a small boost to candidates whose var codes end with _001E.
Boost if label or concept contains “total population,” “median,” “Hispanic or Latino.”
If profile.var_aliases maps the measures phrase, strongly prefer that var (top-1 unless confidence is very low).
Confidence threshold:
If top candidate confidence < threshold, or if the top two are close and represent different concepts, route to clarify.
Planning and API constraints

Always include NAME in variables for human-readable location labels.
Enforce a max variables per request. If future features add more variables, split into multiple QuerySpecs per year.
Validate the requested years against availability; if none viable, suggest nearest available year or route to clarify.
Validate geography level against dataset’s general compatibility (assume ACS supports place/state/county reliably). If user explicitly asks for tracts or block groups, return a friendly “not yet supported” message with guidance.
Data fetching and robustness

Respect retries/backoff for the Census API; handle 429 and 5xx errors gracefully.
On partial failures (some years failed), continue, log which ones failed, and include a footnote stating partial data.
Cast numeric columns when possible; leave NAME and geo id columns as strings.
Ensure the year column exists and is int.
Caching and retention (strong guarantees)

Cache key is a stable hash of year, dataset, sorted variables, and normalized geo filters.
Cache entry includes a timestamp. On read, refresh timestamp so frequently used results survive pruning.
On load and on save, prune entries older than RETENTION_DAYS and delete files. If size caps are configured and exceeded, evict oldest entries until under caps.
History follows the same 90-day retention rule; pruning happens on load and save.
Conversation memory and message control

Use a SQLite checkpointer for thread memory; invoke with a stable thread_id to continue the same conversation.
If messages exceed a configured turn limit, summarize older content into the summary field and trim messages to recent turns; keep summary available to intent/retrieve nodes.
UX behavior requirements

CLI/REPL prompts for user_id and thread_id.
Print a concise answer and, if applicable, a preview row sample and the saved table path.
For not supported items (e.g., tracts initially), return a friendly message that includes the expected for/in structure and invites a supported alternative.
All nodes write one short, timestamped log line to logs, accessible at the end of each run.
Acceptance criteria (Cursor must meet these exactly)

First-time setup:
Running index/build_index builds a Chroma collection named census_vars in ./chroma without errors using ACS 5-year 2012–2023.
Query: “Population of NYC in 2023”
intent: is_census true; answer_type single; measures includes population; time year 2023; geo_hint recognized.
geo: level place with state 36, place 51000.
retrieve: finds a candidate like B01003_001E with years including 2023.
plan: exactly one query for 2023 including NAME.
data: fetches and saves a CSV to ./data, caches it, and produces a preview.
answer: prints a number with thousands separators and mentions year, dataset (ACS 5-year), and NAME in a footnote.
memory_write: history updated (one item), profile default_geo set, cache_index saved.
Query: “Hispanics income from 2012 to 2023 in NYC”
intent: series or table; measures include median_income and hispanic.
retrieve: candidate B19013I_001E; years intersect 2012–2023.
plan: one query per year, including NAME in each.
data: runs concurrently (bounded), fetches, saves, caches; on re-run, uses cache (timestamps refreshed).
answer: creates a combined table, saves it once, prints a concise summary and preview. Footnote mentions variable and dataset.
Query: “By county in NYC, population 2020”
geo: level county with in=state:36 and county:* (or clarify if user meant the five specific counties).
retrieve/plan/data/answer complete successfully and return a small table across NYC counties for 2020.
Not Census example: “What’s 2+2?”
intent routes to not_census with a helpful prompt.
Clarify route:
Ambiguous question triggers clarify. App asks a targeted question and ends turn. The next user reply continues in the same thread and completes the flow.
Retention:
Manually adjusting timestamps to simulate >90 days triggers pruning of history items and cache entries; corresponding files are deleted. Fresh accesses refresh timestamps.
Testing checklist for Cursor to implement

Unit-like functions (if tests are added): signature stability, retention pruning, numeric casting for typical ACS columns.
Manual tests:
Happy paths as per acceptance criteria.
API error simulation (e.g., temporary network issue): verify retries/backoff and friendly error.
Cache hit/refresh: re-run same query; ensure no network call and timestamps are updated.
Summarization triggers when messages are long; ensure conversation continuity via summary.
Security, privacy, local-only guarantees

No data sent to third-party services beyond the public Census API.
Chroma, memory, cache, and checkpoints are local directories/files.
Provide a simple reset: delete data/, memory/, chroma/, and checkpoints.db; then rebuild the index.
Clear TODOs for future upgrades (Cursor should mark these in comments)

Add full support for tracts and block groups (with for/in chains).
Extend build_index to acs/acs1 and dec/pl by uncommenting dataset lists.
Add a multi-variable planner for grouped requests and ensure variable batching by limit.
Upgrade intent and clarify to an LLM (optional) with explicit user opt-in.
Reminder to Cursor

Generate all code from these instructions.
Keep configuration constants centralized and easy to change.
Implement robust logging and friendly, concise user-facing messages.
Never place large dataframes in the graph state; only store file handles and tiny previews.
Ensure all nodes return only deltas to state so reducers can merge predictably.
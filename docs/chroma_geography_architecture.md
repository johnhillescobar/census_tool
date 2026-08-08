# Chroma-grounded Census geography architecture

**Authoritative target:** [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md)  
**Domain model (API `for`/`in`/variables):** [`../app_description/CENSUS_DISCUSSION.md`](../app_description/CENSUS_DISCUSSION.md)

## Runtime planning (target)

At runtime, the **agent** — not a pre-agent workflow node — owns semantic retrieval and API composition:

1. **Temporal year** resolves first (`temporal_node`; default latest e.g. 2024 when unstated).
2. **Agent tools** query Chroma collections with agent-authored semantic queries filtered by dataset/year.
3. Agent selects table/group, geography level, and area IDs from **grounded** candidates (or asks a clarifying question with readable labels).
4. Agent **composes** Census API parameters (`get`, `for`, `in`, dataset path) per `CENSUS_DISCUSSION.md` and **executes** via Census tools — including multi-call loops (enumerate CBSAs → pick code → build `in=` chain → fetch).
5. **Harness** (`validate_grounded_plan`, strict Census API tool) fail-closes on invented FIPS, table codes, or geo tokens not traceable to evidence.

Chroma is **evidence**, not authority. Only selected candidate IDs in attached `RetrievalEvidence` become execution authority after validation.

## Current implementation (legacy — migration debt)

The **shipped graph** still routes through `geography_node` before the agent:

`memory_load → temporal → geography → benchmark → comparison → agent → …`

`geography_node` (`src/workflows/geography.py`) is the **legacy** sole pre-agent planner: regex search-text analysis, internal Chroma retrieval, score-rank auto-select (`select_grounded_plan`), and graph halt on ambiguity with `requires_clarification=True` (agent skipped). This contradicts the target model above.

**Do not extend** the legacy path. Interim fixes (e.g. CENSUS-21 table-slot resume) patch planner-first plumbing; see [`census-21-reframe.md`](census-21-reframe.md).

**Target replacement:** agent retrieval tools + validator harness (see [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md) § Concrete shifts).

Clarification and cancellation branches go directly to `output`. Checkpointed geography choices resume through `geography_resume` (legacy — target: agent turn with grounded options).

Free text, profile values, model knowledge, old Python mappings, pickle caches, and implicit national defaults are **not** runtime geography authority. **Rephrase:** no **ungrounded** LLM-invented geo codes; the agent may resolve among **grounded** Chroma or enumeration candidates.

## Index build vs runtime retrieval

| Phase | What is deterministic | Who queries at runtime |
| --- | --- | --- |
| **Index build** | Candidate IDs, metadata, manifests, partition rules (`index/`) | N/A — offline |
| **Runtime (target)** | ID format invariants, schema_version, index_version checks | **Agent** semantic queries via tools |
| **Runtime (legacy)** | Same invariants | `geography_node` internal retriever (migration debt) |

## Collections and schemas

All active catalog collections carry `schema_version` and `index_version` metadata matching `config.py`.

| Collection | Candidate | Required grounding metadata |
| --- | --- | --- |
| `census_tables` | `TableCandidate` | `candidate_id`, `dataset`, `year`, `table_code`, `table_name`, `category`, `years_available`, `provenance`, versions |
| `census_dataset_geographies` | `HierarchyCandidate` | `candidate_id`, `dataset`, `year`, `friendly_level`, exact `census_token`, `geography_hierarchy`, ordered parent tokens, provenance, versions |
| `census_geography_areas` | `AreaCandidate` | `candidate_id`, `dataset`, `year`, `display_name`, exact `census_token`, `GEO_ID`, geography code, parent clauses, partition, provenance, versions |

`src/domain/geography_catalog.py` defines candidate and `IndexManifest` contracts. Chroma IDs must equal metadata `candidate_id`; malformed metadata becomes `schema_mismatch`, never a partially trusted candidate.

## Invariants

1. Temporal resolution runs before catalog retrieval and supplies the requested year.
2. Every plan has retrieved table evidence. Geography retrieval is constrained by that table's dataset and year.
3. Selection may return only IDs present in the attached evidence.
4. The validator preserves exact Census tokens and required parent ordering in `for`/`in` clauses.
5. Missing, empty, stale, unavailable, or incompatible evidence fails closed to a typed clarification (**target:** agent-narrated; **legacy:** deterministic halt before agent).
6. No absent geography silently becomes `us:1`; national scope must itself be retrieved and selected.
7. Profile geography is search input only. It does not bypass retrieval or validation.
8. The strict Census API tool receives immutable grounded evidence and rejects ungrounded execution.
9. Build-time Census enumeration remains the source for area documents; runtime does not enumerate or consult pickle caches.

## Evidence and observability

Each stage appends a `RetrievalTraceEvent` with status, collection, filters, candidate IDs, selected IDs, and index version. `grounded_retrieval` JSON-line telemetry uses the same trace ID. Candidate IDs and filters are safe to log; API keys, complete environments, and keyed Census URLs are not.

The release corpus contains 124 natural-language questions. Of those, 122 data URLs replay through candidate-ID selection and validation (URL replay harness); two catalog URLs are intentionally bypassed. See `migration_evidence/golden_urls/README.md` for commands and `docs/chroma_geography_operator_runbook.md` for index operations and rollback.

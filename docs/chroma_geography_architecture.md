# Chroma-grounded Census geography architecture

## Runtime authority

The active graph is temporal-first:

`memory_load → temporal → geography → benchmark → comparison → agent → comparison_metrics → output → memory_write`

Clarification and cancellation branches go directly to `output`. A checkpointed geography choice resumes through
`geography_resume`.

`geography_node` is the only geography planning entry point. It analyzes search text, retrieves a table, retrieves geography
hierarchy and area candidates constrained by the selected dataset and resolved year, selects candidate IDs, and validates the
selection. The resulting `GroundedCensusPlan` is the authority passed to execution. Free text, profile values, model knowledge,
old Python mappings, pickle caches, and implicit national defaults are not runtime geography authority.

## Collections and schemas

All active catalog collections carry `schema_version` and `index_version` metadata matching `config.py`.

| Collection | Candidate | Required grounding metadata |
| --- | --- | --- |
| `census_tables` | `TableCandidate` | `candidate_id`, `dataset`, `year`, `table_code`, `table_name`, `category`, `years_available`, `provenance`, versions |
| `census_dataset_geographies` | `HierarchyCandidate` | `candidate_id`, `dataset`, `year`, `friendly_level`, exact `census_token`, `geography_hierarchy`, ordered parent tokens, provenance, versions |
| `census_geography_areas` | `AreaCandidate` | `candidate_id`, `dataset`, `year`, `display_name`, exact `census_token`, `GEO_ID`, geography code, parent clauses, partition, provenance, versions |

`src/domain/geography_catalog.py` defines candidate and `IndexManifest` contracts. Chroma IDs must equal metadata
`candidate_id`; malformed metadata becomes `schema_mismatch`, never a partially trusted candidate.

## Invariants

1. Temporal resolution runs before catalog retrieval and supplies the requested year.
2. Every plan has retrieved table evidence. Geography retrieval is constrained by that table's dataset and year.
3. Selection may return only IDs present in the attached evidence.
4. The validator preserves exact Census tokens and required parent ordering in `for`/`in` clauses.
5. Missing, empty, stale, unavailable, or incompatible evidence fails closed to a typed clarification.
6. No absent geography silently becomes `us:1`; national scope must itself be retrieved and selected.
7. Profile geography is search input only. It does not bypass retrieval or validation.
8. The strict Census API tool receives immutable grounded evidence and rejects ungrounded execution.
9. Build-time Census enumeration remains the source for area documents; runtime does not enumerate or consult pickle caches.

## Evidence and observability

Each stage appends a `RetrievalTraceEvent` with status, collection, filters, candidate IDs, selected IDs, and index version.
`grounded_retrieval` JSON-line telemetry uses the same trace ID. Candidate IDs and filters are safe to log; API keys, complete
environments, and keyed Census URLs are not.

The release corpus contains 124 natural-language questions. Of those, 122 data URLs replay through candidate-ID selection and
validation; two catalog URLs are intentionally bypassed. See `migration_evidence/golden_urls/README.md` for commands and
`docs/chroma_geography_operator_runbook.md` for index operations and rollback.

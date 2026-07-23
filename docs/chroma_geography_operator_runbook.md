# Chroma geography operator runbook

## Preconditions

- Run commands from the repository root with Python 3.12 and `uv`.
- Set `OPENAI_API_KEY` for the configured `text-embedding-3-large` embedding function.
- Treat `chroma/` as a versioned release artifact. Build in a separate directory, validate it, then promote it.
- Use the exact dataset, year, Census token, and parent partition expected by the target release.

## Build and refresh

Build tables:

`uv run python index/build_index_table.py`

Build all configured dataset/year hierarchy documents and its manifest:

`uv run python index/build_geography_index.py --persist-dir /tmp/chroma-next --manifest /tmp/chroma-next/census_dataset_geographies.manifest.json`

Build an area partition:

`uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2023 --level county --partition state:06 --persist-dir /tmp/chroma-next --manifest /tmp/chroma-next/census_geography_areas.manifest.json`

For many parent partitions, put a JSON array such as `["state:01", "state:02"]` in a reviewed file and use
`--partition-file`. Re-running a partition is idempotent because candidate IDs are deterministic and writes use upsert.

A refresh is a complete rebuild into a new directory. Do not mutate the serving directory while requests are active. Keep the
previous directory until acceptance and post-promotion health checks pass.

## Manifests

Hierarchy and area builders write an `IndexManifest` JSON receipt beside Chroma. Required fields are:

- `contract_version`, `collection_name`, `schema_version`, `index_version`, `built_at`, and `document_count`
- covered `datasets`, `years`, `source_urls`, and `partitions`
- optional scalar `metadata`

The manifest is not runtime candidate evidence. It is an operator receipt used to detect missing, stale, wrong-version, or
count-mismatched collections. Archive manifests with the promoted Chroma directory and build logs.

## Health and acceptance

Check both geography collections:

`uv run python index/check_geography_index.py --persist-dir /tmp/chroma-next`

The command prints JSON and exits nonzero for unavailable, empty, version-mismatched, missing/invalid manifest,
document-count mismatch, or stale collections.

Run offline acceptance before promotion:

`uv run pytest app_test_scripts/test_geography_catalog_contracts.py app_test_scripts/test_geography_catalog_builders.py app_test_scripts/test_grounded_census_services.py app_test_scripts/test_phase6_golden_grounded_replay.py app_test_scripts/test_geography_architecture_static.py -q`

`uv run pytest app_test_scripts/test_census_url_fixtures.py app_test_scripts/test_golden_census_urls.py -q`

`uv run pytest app_test_scripts -m "not integration" -q`

`uv run ruff check . && uv run ruff format --check .`

The 124-question replay must retain 122 validated data rows and the two catalog-row bypasses. No selected ID may be absent from
evidence, and no non-national question may acquire an implicit `us:1`.

## Failed partitions

The area builder exits on a failed Census request and does not write a successful manifest for an incomplete run. Preserve its
log and record each failed `(dataset, year, level, parent clauses)` entry in a JSON partition file. Retry only that reviewed file
into the same staging directory, then rerun the complete health and acceptance gates. Never promote a manifest whose partitions
or document count omit a required partition.

The hierarchy builder continues after source failures and records `FETCH_FAILURE` or `EXAMPLES_FETCH_FAILURE` in its timestamped
build log. Before promotion, run `rg "FETCH_FAILURE" logs/chroma_logs/<build-log>` and reconcile every failed dataset/year. A
manifest written by that run proves only what was indexed; it does not certify that every configured source succeeded.

If repeated failures are caused by a Census outage or rate limit, stop the rollout and retain the currently serving index.
Changing a token, parent order, or dataset to make a request pass is a schema change and requires review.

## Promotion and rollback

1. Stop writers to the serving Chroma directory; readers may continue on the old release.
2. Record the current directory, index version, manifests, counts, and health JSON.
3. Atomically switch deployment configuration or a filesystem symlink to the validated staging directory.
4. Restart application processes so persistent clients reopen the promoted directory.
5. Run health, one explicit geography query, one ambiguous clarification query, and Tier 1 acceptance.
6. Monitor telemetry for misses, blocked geography, invented IDs, and implicit national scope.

To roll back, point configuration back to the recorded prior directory, restart clients, and rerun health. Do not edit manifests
or lower version/age checks to force an unhealthy release into service.

## Telemetry and debugger

Tail structured telemetry with `tail -f logs/telemetry.log`. Correlate events by `trace_id` and inspect `stage`, `status`,
`reason_code`, `collection`, `filters`, `candidate_ids`, and `selected_ids`. Investigate any selected ID outside the retrieved
candidate set, `schema_mismatch`, `stale`, `unavailable`, or a Chroma miss without clarification.

VS Code launch profiles `Geography: Golden row 3` and `Geography: Choose golden row` run
`scripts/debug_geography_query.py`. Tasks build the hierarchy/area indexes, run health checks and acceptance, and tail telemetry.
Use the symbol and conditional breakpoint map in `.vscode/geography-breakpoints.md`. Never log credentials or URLs after a
Census API key is appended.

# Chroma geography operator runbook

**Runtime note:** At query time the **agent** (target) issues semantic searches against these same collections via tools, filtered by resolved dataset/year. This runbook covers **index build, health, and promotion** only — not planner-first `geography_node` selection policy. See [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md).

## Preconditions

- Run commands from the repository root with Python 3.12 and `uv`.
- Set `OPENAI_API_KEY` for the configured `text-embedding-3-large` embedding function.
- Set `CENSUS_API_KEY` for area enumeration (Phase C / area builders).
- Treat `chroma/` as a versioned release artifact. Build in a separate directory, validate it, then promote it.
- Use the exact dataset, year, Census token, and parent partition expected by the target release.
- Active catalog collections only: `census_tables`, `census_dataset_geographies`, `census_geography_areas`.
  Do not rebuild `census_vars` or `census_geography_hierarchies` for new releases.

## Preferred path — catalog rebuild orchestrator

Use **one command** for catalog rebuilds. Do **not** upsert `census_tables` onto an existing mixed collection;
the orchestrator / table builder **deletes and recreates** the collection.

Year policy: **2014 → `LATEST_AVAILABLE_YEAR`** (CLI `--year-start` / `--year-end`). Categories keep their
configured starts when later than 2014.

### Phase A (available now) — rebuild tables only, keep serving geography

```powershell
$Staging = "chroma-staging"
uv run python index/rebuild_catalog.py `
  --staging $Staging `
  --serving chroma `
  --year-start 2014 `
  --components tables `
  --promote
```

What this does:

1. Builds a clean `census_tables` in staging (delete/recreate, multi-year, all categories).
2. Writes `census_tables.manifest.json`.
3. Verifies table health + typed smoke query (`total population` → `hit`, ids like `table:…`).
4. Copies geography collections + manifests from serving into staging.
5. Swaps staging into `chroma/` via `promote_chroma` (with `chroma-previous-<stamp>` backup).

Dry-run (no API/embed writes):

`uv run python index/rebuild_catalog.py --staging chroma-staging --components tables --dry-run`

Health after promote:

`uv run python index/check_geography_index.py --persist-dir chroma --all`

### Phase B (available now) — rebuild dataset geographies

Rebuild `census_dataset_geographies` only (keeps serving tables + areas via copy-on-promote):

```powershell
$Staging = "chroma-staging"
uv run python index/rebuild_catalog.py `
  --staging $Staging `
  --serving chroma `
  --year-start 2014 `
  --components geographies `
  --promote
```

Or rebuild tables + geographies together:

```powershell
uv run python index/rebuild_catalog.py `
  --staging $Staging `
  --serving chroma `
  --year-start 2014 `
  --components tables `
  --components geographies `
  --promote
```

What Phase B does:

1. Delete/recreates `census_dataset_geographies` in staging for years `2014 → LATEST_AVAILABLE_YEAR`.
2. Writes `census_dataset_geographies.manifest.json`.
3. Does **not** write `census_geography_hierarchies`.
4. Verifies geography health + smoke (`county` query in an `acs/acs5` year partition → `geo-level:…` ids).
5. On `--promote`, copies any active collections not rebuilt in this run from serving into staging, then swaps.

Dry-run:

`uv run python index/rebuild_catalog.py --staging chroma-staging --components geographies --dry-run`

### Phase C (available now) — Option 2 areas matrix

Rebuild `census_geography_areas` for **acs/acs5**, years `2014 → LATEST_AVAILABLE_YEAR`, with the Option 2
default coverage matrix:

- **National (no parent):** `us`, `state`, `zip code tabulation area`,
  `metropolitan statistical area/micropolitan statistical area`
- **Per-state** (parents from `index/partitions/us_state_fips.json`): `county`, `place`,
  `congressional district`, `public use microdata area`, `school district (unified)`,
  `state legislative district (upper chamber)`, `state legislative district (lower chamber)`
- **Opt-in only (not required for Phase C):** `--include-tracts`, `--include-block-groups`
  (enumerated under county parents after county jobs succeed)

Named-tract live Census NAME lookup and multi-named-tract plan selection are **later architecture** work,
not part of this rebuild path.

```powershell
$Staging = "chroma-staging"
uv run python index/rebuild_catalog.py `
  --staging $Staging `
  --serving chroma `
  --year-start 2014 `
  --components areas `
  --promote
```

Resume an interrupted areas build (skips completed job keys; does not wipe the collection when progress exists):

```powershell
uv run python index/rebuild_catalog.py `
  --staging $Staging `
  --serving chroma `
  --components areas `
  --resume `
  --promote
```

Optional tract/block-group expansion (long / very long runtime):

```powershell
uv run python index/rebuild_catalog.py `
  --staging $Staging `
  --serving chroma `
  --components areas `
  --include-tracts `
  --resume `
  --promote
```

What Phase C does:

1. Delete/recreates `census_geography_areas` once at the start of the areas phase (unless `--resume` with an
   existing collection + progress).
2. Fetches → upserts each matrix job; appends progress keys; refreshes a cumulative manifest
   (`census_geography_areas.manifest.json`). Progress/failures:
   `census_geography_areas.progress.json`, `census_geography_areas.failures.json`.
3. Failed Census partitions (404/empty) are logged into the failures file; the build continues.
4. Verifies area health + smoke (`California` query in an `acs/acs5` year partition → `geo-area:…` ids).
5. On `--promote`, copies any active collections not rebuilt in this run from serving into staging, then swaps.

**Runtime tiers (rough):** national + per-state Option 2 for 2014→latest is multi-hour (thousands of Census
calls). Adding `--include-tracts` / `--include-block-groups` is substantially longer.

Dry-run:

`uv run python index/rebuild_catalog.py --staging chroma-staging --components areas --dry-run`

Full catalog (`tables` + `geographies` + `areas`):

`uv run python index/rebuild_catalog.py --staging chroma-staging --serving chroma --year-start 2014 --components all --promote`

### Annual update

1. Bump `LATEST_AVAILABLE_YEAR` in `config.py` when Census publishes a new release.
2. Re-run `index/rebuild_catalog.py` with the same flags (full catalog via `--components all`).
3. Do not invent a second procedure.

### Blocked work

Graph enumeration-lanes / mode-classifier work stays blocked until catalog Phase C promote is green enough for
end-to-end geography goldens. Table `TABLE_SCHEMA_MISMATCH` is already addressed by Phase A. Named-tract hybrid
resolve remains deferred architecture.

## Appendix — low-level builders (debugging / Phase C until orchestrated)

### Step 1 - Dataset geographies (prefer orchestrator `--components geographies`)

Build tables alone (still prefer the orchestrator above):

`uv run python index/build_index_table.py --persist-dir /tmp/chroma-next --year-start 2014`

Build dataset geographies directly:

`uv run python index/build_geography_index.py --persist-dir /tmp/chroma-next --year-start 2014 --year-end 2024`

### Step 2 — Areas (you choose scope; hierarchy Step 1 is still required)

Area builds call the Census API with `CENSUS_API_KEY` set. Each run upserts into `census_geography_areas` and writes a
manifest for **that run only**. Run one dataset/year/level combination per command so `document_count` in the manifest
matches the collection after the run.

#### One state, one level (example: California counties)

`uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2023 --level county --partition state:06 --persist-dir /tmp/chroma-next --manifest /tmp/chroma-next/census_geography_areas.manifest.json`

#### All US states and DC (national `state` level, single enumeration)

No `--partition` or `--partition-file` is needed. An empty partition issues `for=state:*` once.

`uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2023 --level state --persist-dir /tmp/chroma-next --manifest /tmp/chroma-next/census_geography_areas.manifest.json`

#### All US counties (every state + DC, ~3,100 counties)

Use the reviewed partition list at `index/partitions/us_state_fips.json` (51 parent partitions: `state:01` … `state:56`,
skipping unused FIPS slots). One command enumerates `for=county:*&in=state:XX` for each parent.

`uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2023 --level county --partition-file index/partitions/us_state_fips.json --persist-dir /tmp/chroma-next --manifest /tmp/chroma-next/census_geography_areas.manifest.json`

Repeat with `--year 2024` (or other release years) when the runtime default year requires them.

#### Geography levels beyond county (tracts, places, districts, ZCTAs, and more)

The county examples above are **starting points**, not the limit of the system. The runtime supports any
geography level that Census publishes for the selected dataset and year. County builds are documented first because they
are a common, bounded nationwide release (~51 API calls with `us_state_fips.json`).

**Two layers, two roles:**

| Layer | Command | What it covers |
| --- | --- | --- |
| Step 1 hierarchy | `build_geography_index.py` | **All levels** for every configured dataset/year: rules like `state › county › tract`, exact Census tokens, parent order, summary levels. No operator choice of level. |
| Step 2 areas | `build_geography_areas_index.py` | **Actual place names and codes** for the `--level` and `--partition` you choose. You decide scope (one county’s tracts, all places in a state, every congressional district in Georgia, etc.). |

If Step 1 ran successfully, the hierarchy index already knows that `tract`, `place`, `congressional district`, and
similar levels exist for `acs/acs5` in your release years. Step 2 is what populates searchable area records for the
questions you want to support.

**Finding the exact `--level` token**

Use the **exact** Census API token (spaces and punctuation matter). Sources, in order:

1. Step 1 output / `census_dataset_geographies` metadata (`census_token`, `geography_hierarchy`).
2. The dataset/year geography page, e.g. `https://api.census.gov/data/2023/acs/acs5/geography.html`.
3. A golden URL in `migration_evidence/golden_urls/` for the question shape you care about.

On PowerShell, quote multi-word tokens: `--level "block group"`, `--level "congressional district"`.

**Common levels (examples for `acs/acs5`, year `2023`)**

Parent clauses in `--partition` or `--partition-file` entries are comma-separated `LEVEL:VALUE` pairs (same order Census
expects in `in=`). Each row is one enumeration request.

| User intent | `--level` (exact token) | Example `--partition` | Example command fragment |
| --- | --- | --- | --- |
| Cities/places in one state | `place` | `state:06` | `--level place --partition state:06` |
| All tracts in one county | `tract` | `state:06,county:037` | `--level tract --partition state:06,county:037` |
| Block groups in one tract | `block group` | `state:36,county:061,tract:003100` | `--level "block group" --partition state:36,county:061,tract:003100` |
| Congressional districts in a state | `congressional district` | `state:13` | `--level "congressional district" --partition state:13` |
| State upper chamber districts | `state legislative district (upper chamber)` | `state:06` | `--level "state legislative district (upper chamber)" --partition state:06` |
| State lower chamber districts | `state legislative district (lower chamber)` | `state:06` | `--level "state legislative district (lower chamber)" --partition state:06` |
| PUMAs in a state | `public use microdata area` | `state:36` | `--level "public use microdata area" --partition state:36` |
| Unified school districts in a state | `school district (unified)` | `state:48` | `--level "school district (unified)" --partition state:48` |
| ZIP Code Tabulation Areas (national) | `zip code tabulation area` | *(omit partition)* | `--level "zip code tabulation area"` |
| CBSAs (national) | `metropolitan statistical area/micropolitan statistical area` | *(omit partition)* | `--level "metropolitan statistical area/micropolitan statistical area"` |

Full example — tracts in Los Angeles County, CA:

`uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2023 --level tract --partition state:06,county:037 --persist-dir chroma --manifest chroma\census_geography_areas.manifest.json`

Full example — congressional districts in Georgia:

`uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2023 --level "congressional district" --partition state:13 --persist-dir chroma --manifest chroma\census_geography_areas.manifest.json`

**Scaling beyond one state or county**

There is no single “index all US tracts” command. Nationwide tract coverage requires a reviewed partition file listing every
parent county (or equivalent) you need — roughly 3,100 county partitions × one API call each, plus embedding cost. The
same pattern applies to places per state, school districts per state, and so on.

Practical release tiers:

1. **Minimum viable:** Step 1 hierarchy + counties nationwide (`index/partitions/us_state_fips.json`).
2. **State + place:** add `--level place` with `--partition-file index/partitions/us_state_fips.json` (51 calls).
3. **Targeted tracts:** partition files for counties your users query (metro areas, golden-test counties).
4. **National ZCTA/CBSA:** often one enumeration with no parent partition (empty `for=TOKEN:*`).

**What happens if an area partition was not built**

The hierarchy may still resolve the level, but Chroma will have no matching `AreaCandidate` records. The graph fails closed
with a geography clarification — it does not invent places or default to `us:1`. Build the partition that contains the
geographies your questions need.

**Dataset and year caveats**

Not every level appears in every dataset/year (profile and subject tables differ from detail `acs/acs5`). Step 1 logs
`FETCH_FAILURE` for missing Census pages; Step 2 fails fast if the enumeration URL returns an error. Confirm the level on
the geography page for your exact `--dataset` and `--year` before large builds.

For ad hoc lists, put a JSON array such as `["state:01", "state:02"]` or `["state:06,county:037"]` in a reviewed file
and pass `--partition-file`. **Re-running a partition is idempotent** because candidate IDs are deterministic and writes use upsert.

For local development you may set `--persist-dir chroma` instead of a staging directory so the app reads the new areas
immediately (skip promotion).

A refresh is a complete rebuild into a new directory. Do not mutate the serving directory while requests are active. Keep the previous directory until acceptance and post-promotion health checks pass.

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

The CLI, Streamlit, and FastAPI entry points all read Chroma from `CHROMA_PERSIST_DIRECTORY` in `config.py`, which is
`./chroma`. Use `index/promote_chroma.py` to move validated builds into serving.

Set paths once for the session (PowerShell, run from the repository root):

```powershell
$Staging = "C:\tmp\chroma-next"   # directory you passed to --persist-dir during builds
$Serving = ".\chroma"              # must match config.py CHROMA_PERSIST_DIRECTORY
$Stamp   = Get-Date -Format "yyyyMMdd-HHmmss"
```

On Linux/macOS, use `/tmp/chroma-next` and `./chroma` instead.

### Choose a promotion path

Census updates rarely arrive as one clean directory. Builders write to different targets:

| Builder | Default persist dir | Notes |
| --- | --- | --- |
| `build_index_table.py` | `./chroma` only | no `--persist-dir` flag |
| `build_geography_index.py` | configurable | hierarchy |
| `build_geography_areas_index.py` | configurable | one dataset/year/level per run |

That split drives three operator paths:

| Path | When to use | Command |
| --- | --- | --- |
| **A. In-place rebuild** | Tables already good; you refreshed geography directly into `./chroma` | No promotion — you are already serving the new data |
| **B. Merge geography** | Staging has new hierarchy and/or areas; `./chroma` already has `census_tables` | `promote_chroma.py --mode merge-geography` |
| **C. Full directory swap** | Staging is a complete copy of `./chroma` (tables + both geography collections) | `promote_chroma.py --mode swap` |

**Path B is the normal case** after a Census year refresh: tables stay in `./chroma`, geography builds land in staging,
then merge promotes the geography without losing tables.

**Incremental area builds** (for example 2022 counties, then 2024 counties) upsert into the same collection but each
run writes a manifest for that run only. Expect `manifest_count_mismatch` on staging until promotion refreshes the
manifest from the merged collection totals. That is not a signal to skip promotion — it is why merge rewrites manifests.

### Recommended workflow when Census data is updated

Example: new ACS year or expanded county partitions.

```powershell
# 1. Refresh tables in serving (only builder without --persist-dir)
uv run python index/build_index_table.py

# 2. Build geography into staging
uv run python index/build_geography_index.py --persist-dir $Staging --manifest "$Staging\census_dataset_geographies.manifest.json"
uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2024 --level county --partition-file index/partitions/us_state_fips.json --persist-dir $Staging --manifest "$Staging\census_geography_areas.manifest.json"

# 3. Optional: add another year/partition with more area commands into the same staging dir (upsert)

# 4. Dry-run promotion
uv run python index/promote_chroma.py --mode merge-geography --staging $Staging --serving $Serving --dry-run

# 5. Promote geography into serving (backs up ./chroma, merges collections, refreshes manifests, runs health check)
uv run python index/promote_chroma.py --mode merge-geography --staging $Staging --serving $Serving
```

To build a **complete staging tree** for path C instead:

```powershell
uv run python index/build_index_table.py
New-Item -ItemType Directory -Force -Path $Staging | Out-Null
Copy-Item -Recurse -Force "$Serving\*" $Staging
# geography builds with --persist-dir $Staging ...
uv run python index/promote_chroma.py --mode swap --staging $Staging --serving $Serving
```

### 1. Stop writers

Stop any process that opens `./chroma`: Census CLI, Streamlit, FastAPI, or VS Code debug sessions. Readers on the old
release can stay up until promotion finishes; restart clients after promotion so Chroma clients reopen `./chroma`.

### 2. Record the current release

```powershell
uv run python index/check_geography_index.py --persist-dir $Serving | Tee-Object -FilePath "logs\chroma-pre-promote-$Stamp.json"

Copy-Item "$Serving\census_dataset_geographies.manifest.json" "logs\census_dataset_geographies-$Stamp.manifest.json" -ErrorAction SilentlyContinue
Copy-Item "$Serving\census_geography_areas.manifest.json" "logs\census_geography_areas-$Stamp.manifest.json" -ErrorAction SilentlyContinue
```

### 3. Validate before promote

Merge path — confirm staging has the geography you expect and serving still has tables:

```powershell
uv run python -c @"
import chromadb
from chromadb.config import Settings
for label, path in [('SERVING', r'$Serving'), ('STAGING', r'$Staging')]:
    print(f'=== {label} ===')
    c = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
    for name in ('census_tables', 'census_dataset_geographies', 'census_geography_areas'):
        try:
            col = c.get_collection(name)
            print(name, col.count())
        except Exception as exc:
            print(name, 'MISSING', exc)
"@

uv run python index/promote_chroma.py --mode merge-geography --staging $Staging --serving $Serving --dry-run
```

Swap path — staging must contain all three collections and pass geography health:

```powershell
uv run python index/check_geography_index.py --persist-dir $Staging
uv run python index/promote_chroma.py --mode swap --staging $Staging --serving $Serving --dry-run
```

Run the acceptance tests listed in **Health and acceptance** before a production promote.

### 4. Promote

**Merge geography (path B — default):**

```powershell
uv run python index/promote_chroma.py --mode merge-geography --staging $Staging --serving $Serving
```

This copies `census_dataset_geographies` and `census_geography_areas` from staging into serving, leaves
`census_tables` untouched, backs up `./chroma` to `./chroma-previous-<stamp>`, and rewrites geography manifests from
the merged collection counts.

Merge only one collection:

```powershell
uv run python index/promote_chroma.py --mode merge-geography --staging $Staging --collection census_geography_areas
```

**Full directory swap (path C):**

```powershell
uv run python index/promote_chroma.py --mode swap --staging $Staging --serving $Serving
```

Swap moves the entire staging directory to `./chroma`. It fails fast if staging is missing `census_tables`.

### 5. Post-promotion verification

```powershell
uv run python index/check_geography_index.py --persist-dir chroma

uv run python scripts/debug_geography_query.py --golden-row 3 --show-candidates
```

See [chroma_geography_debug_queries.md](./chroma_geography_debug_queries.md) for `--inspect-only` table diagnostics when
promotion succeeds but queries still fail with `TABLE_SCHEMA_MISMATCH`.

Restart the CLI or debug session with a **new thread ID**. Run one explicit geography query and one ambiguous query;
watch `logs/telemetry.log` for misses or implicit `us:1`.

### Rollback

Merge and swap both create `./chroma-previous-<stamp>` before changing serving.

```powershell
# Stop all app processes first
Rename-Item chroma "chroma-bad-$Stamp"
Rename-Item "chroma-previous-$Stamp" chroma

uv run python index/check_geography_index.py --persist-dir chroma
```

Restart clients again. Do not edit manifests or lower version/age checks to force an unhealthy release into service.

Keep `chroma-previous-*` until you are satisfied with the new release; delete old backups only after a stable soak period.

## Telemetry and debugger

Tail structured telemetry with `tail -f logs/telemetry.log`. Correlate events by `trace_id` and inspect `stage`, `status`,
`reason_code`, `collection`, `filters`, `candidate_ids`, and `selected_ids`. Investigate any selected ID outside the retrieved
candidate set, `schema_mismatch`, `stale`, `unavailable`, or a Chroma miss without clarification.

VS Code launch profiles `Geography: Golden row 3` and `Geography: Choose golden row` run
`scripts/debug_geography_query.py`. For table-index inspection commands and `TABLE_SCHEMA_MISMATCH` interpretation, see
[chroma_geography_debug_queries.md](./chroma_geography_debug_queries.md). Tasks build the hierarchy/area indexes, run health
checks and acceptance, and tail telemetry. Use the symbol and conditional breakpoint map in `.vscode/geography-breakpoints.md`.
Never log credentials or URLs after a Census API key is appended.

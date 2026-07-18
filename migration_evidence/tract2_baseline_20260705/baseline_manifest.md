# Track 2 Integrated Baseline Manifest

Date: 2026-07-05
Branch: `cursor/track2-integrated-c46b`
Supersedes PRs: #37, #38, #39, #40, #41

## Scope

Integrated Track 2 completion combining:

- Typed `WorkflowPlan` handoffs (PR #41)
- Benchmark geo inference for named state comparisons (PR #37)
- Agent plan consumption and comparison row wiring (PR #38, #39)
- Workflow acceptance suite and graph invoke smoke test (PR #40 + integration)

## Commands run

```bash
uv sync
mkdir -p chroma memory data
uv run pytest app_test_scripts/ -v -m "not integration"
uv run pytest app_test_scripts/test_track2_graph_invoke.py -v
uv run ruff check \
  src/domain/benchmark_geo_inference.py \
  src/domain/workflow_acceptance.py \
  src/services/benchmark_geo_inference.py \
  src/services/benchmark_policy.py \
  src/services/workflow_acceptance_runner.py \
  src/services/agent_plan_context.py \
  app_test_scripts/test_benchmark_geo_inference.py \
  app_test_scripts/test_benchmark_contract.py \
  app_test_scripts/test_benchmark_workflow_routing.py \
  app_test_scripts/workflow_acceptance_plans.py \
  app_test_scripts/test_workflow_acceptance_plans.py
```

## Results

- Non-integration pytest: 238 passed (see `test/pytest_full_20260705.txt`)
- Graph invoke smoke: 1 passed (`test_track2_graph_invoke.py`)
- Ruff (Track 2 acceptance paths): All checks passed

## Canonical workflow scenarios verified

| Scenario | plan_id |
|----------|---------|
| Non-comparison latest_available | `non_comparison_latest_available` |
| Temporal conflict clarification | `temporal_conflict_clarification` |
| Benchmark missing metric | `benchmark_missing_metric_clarification` |
| Benchmark baseline vs peer conflict | `benchmark_conflict_clarification` |
| Peer group comparison resolved | `resolved_peer_group_comparison` |
| CA vs TX custom_set | `named_state_custom_set_comparison` |
| National benchmark | `national_benchmark_comparison` |
| Historical baseline | `historical_baseline_comparison` |
| Comparison metrics E2E | `comparison_metrics_end_to_end` |

## Manual demo scenarios (run locally with API keys)

1. Simple lookup: "What's the population of New York City?"
2. Temporal clarification: "compare 2019 vs 2023 over the last 5 years"
3. Geo comparison: "Compare California vs Texas population in 2020"
4. Baseline: "compare population vs 2019 baseline"

Commands:

```bash
uv run python main.py
uv run streamlit run streamlit_app.py
```

Integration tests (local, requires keys):

```bash
export OPENAI_API_KEY=...
export CENSUS_API_KEY=...
uv run pytest app_test_scripts/test_integration_agent_api.py -v -m integration
```

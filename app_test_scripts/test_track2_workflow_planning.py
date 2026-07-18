from langchain_core.runnables import RunnableConfig

from app import (
    _route_after_agent,
    _route_after_benchmark,
    _route_after_comparison,
    _route_after_temporal,
)
from src.domain.benchmark_contract import BenchmarkClarificationRequired, BenchmarkResolved
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import TemporalClarificationRequired, TemporalResolved
from src.services.memory_utils import build_history_record
from src.state.types import CensusState
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan
from src.workflows.benchmark import benchmark_node
from src.workflows.comparison import comparison_node
from src.workflows.comparison_metrics import comparison_metrics_node
from src.workflows.temporal import temporal_node

CONFIG: RunnableConfig = {"configurable": {"user_id": "test", "thread_id": "test"}}


def _state(question: str, plan: WorkflowPlan | None = None, artifacts: dict | None = None) -> CensusState:
    return CensusState(
        messages=[{"role": "user", "content": question}],
        plan=plan,
        artifacts=artifacts or {},
    )


def _apply_node(state: CensusState, node_fn) -> CensusState:
    result = node_fn(state, CONFIG)
    updates = dict(result)
    if "plan" in updates and updates["plan"] is not None:
        state = state.model_copy(update={"plan": updates["plan"]})
    if "final" in updates:
        state = state.model_copy(update={"final": updates["final"]})
    if "artifacts" in updates:
        merged = dict(state.artifacts)
        merged.update(updates["artifacts"])
        state = state.model_copy(update={"artifacts": merged})
    if "logs" in updates:
        state = state.model_copy(update={"logs": state.logs + updates["logs"]})
    return state


def test_temporal_clarification_sets_typed_plan_and_final():
    state = _state("compare 2019 vs 2023 over the last 5 years")
    result = temporal_node(state, CONFIG)

    assert isinstance(result["plan"], WorkflowPlan)
    assert result["plan"].requires_clarification is True
    assert isinstance(result["plan"].temporal, TemporalClarificationRequired)
    assert result["final"]["answer_text"]
    assert _route_after_temporal(state.model_copy(update={"plan": result["plan"]})) == "output"


def test_temporal_resolved_defaults_latest_available():
    state = _state("population of california")
    result = temporal_node(state, CONFIG)

    assert isinstance(result["plan"], WorkflowPlan)
    assert result["plan"].requires_clarification is False
    assert isinstance(result["plan"].temporal, TemporalResolved)
    assert result["plan"].temporal.time.mode == "latest_available"
    assert _route_after_temporal(state.model_copy(update={"plan": result["plan"]})) == "benchmark"


def test_benchmark_skip_when_no_compare_intent():
    temporal_result = temporal_node(_state("population of california"), CONFIG)
    state = _state("population of california", plan=temporal_result["plan"])
    result = benchmark_node(state, CONFIG)

    assert isinstance(result["plan"].benchmark, BenchmarkNotApplicable)
    assert result["plan"].requires_clarification is False
    assert _route_after_benchmark(state.model_copy(update={"plan": result["plan"]})) == "agent"


def test_benchmark_does_not_skip_leading_compare_typo():
    temporal_result = temporal_node(
        _state("ompare population by county in California"), CONFIG
    )
    state = _state(
        "ompare population by county in California",
        plan=temporal_result["plan"],
    )
    result = benchmark_node(state, CONFIG)

    assert not isinstance(result["plan"].benchmark, BenchmarkNotApplicable)


def test_benchmark_clarification_envelope():
    temporal_result = temporal_node(_state("compare state vs national"), CONFIG)
    state = _state("compare state vs national", plan=temporal_result["plan"])
    result = benchmark_node(state, CONFIG)

    assert isinstance(result["plan"].benchmark, BenchmarkClarificationRequired)
    assert result["plan"].requires_clarification is True
    assert result["final"]["answer_text"]


def test_comparison_resolved_chain_produces_comparison_plan():
    state = _state("compare population for counties")
    state = _apply_node(state, temporal_node)
    state = _apply_node(state, benchmark_node)
    result = comparison_node(state, CONFIG)

    assert isinstance(result["plan"].comparison, ComparisonPlan)
    assert result["plan"].requires_clarification is False
    assert result["plan"].comparison.metric == "population"
    assert result["plan"].comparison.derived_metrics == ["difference"]
    assert _route_after_comparison(state.model_copy(update={"plan": result["plan"]})) == "agent"


def test_comparison_upstream_unresolved_requires_clarification():
    plan = WorkflowPlan(
        temporal=TemporalClarificationRequired(
            reason_code="TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING",
            clarification_prompt={
                "template_id": "temporal.explicit_vs_rolling.v1",
                "reason_code": "TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING",
                "question_text": "choose",
                "options": [{"option_id": "cancel", "label": "Cancel"}],
            },
        ),
        requires_clarification=True,
    )
    result = comparison_node(_state("compare population", plan=plan), CONFIG)
    assert result["plan"].requires_clarification is True
    assert result["plan"].comparison is None


def test_historical_baseline_chain_merges_query_years():
    state = _state("compare population vs 2019 baseline")
    state = _apply_node(state, temporal_node)
    state = _apply_node(state, benchmark_node)
    result = comparison_node(state, CONFIG)

    assert isinstance(result["plan"].benchmark, BenchmarkResolved)
    assert result["plan"].benchmark.benchmark.benchmark_type == "historical_baseline"
    assert result["plan"].comparison.query_years == [2019]
    assert result["plan"].comparison.benchmark_geos == []


def test_historical_baseline_merges_latest_available_with_anchor():
    from src.domain.temporal_contract import TemporalIntent
    from src.services.benchmark_policy import resolve_benchmark_intent

    benchmark = resolve_benchmark_intent("compare population vs 2019 baseline")
    plan = WorkflowPlan(
        temporal=TemporalResolved(
            time=TemporalIntent(mode="latest_available", requested_text="compare population"),
        ),
        benchmark=benchmark,
        requires_clarification=False,
    )
    result = comparison_node(_state("compare population vs 2019 baseline", plan=plan), CONFIG)
    assert result["plan"].comparison.query_years == [2019, 2023]


def test_comparison_metrics_node_computes_rows():
    state = _state("compare population for counties")
    state = _apply_node(state, temporal_node)
    state = _apply_node(state, benchmark_node)
    state = _apply_node(state, comparison_node)
    state = state.model_copy(
        update={
            "artifacts": {
                "comparison_input_rows": [
                    {
                        "year": 2023,
                        "geo_id": "06001",
                        "metric": "population",
                        "value": 100.0,
                        "benchmark_value": 90.0,
                    }
                ]
            }
        }
    )

    result = comparison_metrics_node(state, CONFIG)
    assert "comparison_metrics" in result["artifacts"]
    assert len(result["artifacts"]["comparison_metrics"]) == 1
    assert _route_after_agent(state) == "comparison_metrics"


def test_workflow_plan_repeatability():
    question = "compare population for counties"
    first = temporal_node(_state(question), CONFIG)["plan"].model_dump()
    second = temporal_node(_state(question), CONFIG)["plan"].model_dump()
    assert first == second


def test_build_history_record_summarizes_workflow_plan():
    state = _state("compare population vs 2019 baseline")
    state = _apply_node(state, temporal_node)
    state = _apply_node(state, benchmark_node)
    state = _apply_node(state, comparison_node)

    record = build_history_record(
        state.messages,
        {"answer_text": "done"},
        {},
        {},
        state.plan,
        "user-1",
    )
    assert "benchmark=historical_baseline" in record["plan_summary"]
    assert "baseline=2019" in record["plan_summary"]
    assert "years=[2019]" in record["plan_summary"]

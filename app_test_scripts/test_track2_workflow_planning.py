from langchain_core.runnables import RunnableConfig

from app import (
    _route_after_agent,
    _route_after_benchmark,
    _route_after_comparison,
    _route_after_temporal,
)
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from config import LATEST_AVAILABLE_YEAR
from src.domain.benchmark_contract import BenchmarkClarificationRequired, BenchmarkResolved
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import (
    ClarificationOption,
    ClarificationPrompt,
    TemporalClarificationRequired,
    TemporalResolved,
)
from src.services.memory_utils import build_history_record
from src.state.types import CensusState
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan
from src.workflows.benchmark import benchmark_node
from src.workflows.comparison import comparison_node
from src.workflows.comparison_metrics import comparison_metrics_node
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node

CONFIG: RunnableConfig = {
    "configurable": {
        "user_id": "test",
        "thread_id": "test",
        "grounded_geography_dependencies": FakeGroundedRetrieval().dependencies(),
    }
}


def _state(question: str, plan: WorkflowPlan | None = None, artifacts: dict | None = None) -> CensusState:
    return CensusState(
        messages=[{"role": "user", "content": question}],
        original_query=question,
        intent=None,
        plan=plan,
        artifacts=artifacts or {},
        final=None,
        error=None,
        summary=None,
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
    if "geo" in updates and updates["geo"] is not None:
        state = state.model_copy(update={"geo": updates["geo"]})
    return state


def _stub_agent_planning_node(state: CensusState, config: RunnableConfig) -> dict:
    return {"logs": ["agent_planning: completed retrieval planning turn"]}


def _run_planning_chain(state: CensusState) -> CensusState:
    state = _apply_node(state, temporal_node)
    state = _apply_node(state, _stub_agent_planning_node)
    state = _apply_node(state, geography_node)
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
    assert _route_after_temporal(state.model_copy(update={"plan": result["plan"]})) == "agent_planning"


def test_benchmark_skip_when_no_compare_intent():
    state = _run_planning_chain(_state("population of california"))
    result = benchmark_node(state, CONFIG)

    assert isinstance(result["plan"].benchmark, BenchmarkNotApplicable)
    assert result["plan"].requires_clarification is False
    assert _route_after_benchmark(state.model_copy(update={"plan": result["plan"]})) == "agent"


def test_benchmark_does_not_skip_leading_compare_typo():
    state = _run_planning_chain(_state("ompare population by county in California"))
    result = benchmark_node(state, CONFIG)

    assert not isinstance(result["plan"].benchmark, BenchmarkNotApplicable)


def test_benchmark_clarification_envelope():
    state = _run_planning_chain(_state("compare state vs national"))
    result = benchmark_node(state, CONFIG)

    assert isinstance(result["plan"].benchmark, BenchmarkClarificationRequired)
    assert result["plan"].requires_clarification is True
    assert result["final"]["answer_text"]


def test_comparison_resolved_chain_produces_comparison_plan():
    state = _run_planning_chain(_state("compare population for counties"))
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
            clarification_prompt=ClarificationPrompt(
                template_id="temporal.explicit_vs_rolling.v1",
                reason_code="TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING",
                question_text="choose",
                options=[ClarificationOption(option_id="cancel", label="Cancel")],
            ),
        ),
        requires_clarification=True,
    )
    result = comparison_node(_state("compare population", plan=plan), CONFIG)
    assert result["plan"].requires_clarification is True
    assert result["plan"].comparison is None


def test_historical_baseline_chain_merges_query_years():
    state = _run_planning_chain(_state("compare county population in California vs 2019 baseline"))
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
            time=TemporalIntent(
                mode="latest_available",
                start_year=None,
                end_year=None,
                anchor_year=None,
                requested_text="compare population",
            ),
        ),
        benchmark=benchmark,
        requires_clarification=False,
    )
    result = comparison_node(_state("compare population vs 2019 baseline", plan=plan), CONFIG)
    assert result["plan"].comparison.query_years == [2019, LATEST_AVAILABLE_YEAR]


def test_comparison_metrics_node_computes_rows():
    state = _run_planning_chain(_state("compare population for counties"))
    state = _apply_node(state, benchmark_node)
    state = _apply_node(state, comparison_node)
    state = state.model_copy(
        update={
            "artifacts": {
                "comparison_input_rows": [
                    {
                        "year": LATEST_AVAILABLE_YEAR,
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
    first_plan = _run_planning_chain(_state(question)).plan
    second_plan = _run_planning_chain(_state(question)).plan
    assert first_plan is not None
    assert second_plan is not None
    first = first_plan.model_dump(exclude={"retrieval_trace"})
    second = second_plan.model_dump(exclude={"retrieval_trace"})
    assert first == second


def test_build_history_record_summarizes_workflow_plan():
    state = _run_planning_chain(_state("compare county population in California vs 2019 baseline"))
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

from pydantic import ValidationError

from src.domain.benchmark_contract import (
    BenchmarkClarificationRequired,
)
from src.domain.temporal_contract import TemporalClarificationRequired
from src.domain.workflow_acceptance import (
    WorkflowAcceptanceExpectation,
    WorkflowAcceptancePlan,
    WorkflowAcceptanceResult,
    WorkflowPipelineStage,
)
from src.state.types import CensusState
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan
from src.workflows.benchmark import benchmark_node
from src.workflows.comparison import comparison_node
from src.workflows.comparison_metrics import comparison_metrics_node
from src.workflows.temporal import temporal_node


def _route_after_temporal(plan: WorkflowPlan) -> str:
    if plan.requires_clarification:
        return "output"
    return "benchmark"


def _route_after_benchmark(plan: WorkflowPlan) -> str:
    if plan.requires_clarification:
        return "output"
    if plan.benchmark_is_not_applicable():
        return "agent"
    return "comparison"


def _extract_temporal_status(plan: WorkflowPlan) -> str | None:
    if plan.temporal is None:
        return None
    return plan.temporal.status


def _extract_benchmark_status(plan: WorkflowPlan) -> str | None:
    if plan.benchmark is None:
        return None
    if isinstance(plan.benchmark, BenchmarkNotApplicable):
        return "not_applicable"
    return plan.benchmark.status


def _extract_reason_code(plan: WorkflowPlan, key: str) -> str | None:
    if key == "temporal" and isinstance(plan.temporal, TemporalClarificationRequired):
        return plan.temporal.reason_code
    if key == "benchmark" and isinstance(plan.benchmark, BenchmarkClarificationRequired):
        return plan.benchmark.reason_code
    return None


def _extract_temporal_mode(plan: WorkflowPlan) -> str | None:
    temporal_intent = plan.resolved_temporal_intent()
    return temporal_intent.mode if temporal_intent is not None else None


def _extract_benchmark_type(plan: WorkflowPlan) -> str | None:
    benchmark_intent = plan.resolved_benchmark_intent()
    return benchmark_intent.benchmark_type if benchmark_intent is not None else None


def _validate_expectation(
    result: WorkflowAcceptanceResult,
    workflow_plan: WorkflowPlan,
    expectation: WorkflowAcceptanceExpectation,
) -> None:
    if result.requires_clarification != expectation.requires_clarification:
        raise AssertionError(
            f"requires_clarification expected {expectation.requires_clarification}, got {result.requires_clarification}"
        )

    if result.executed_stages[-1] != expectation.stop_after:
        raise AssertionError(f"stop_after expected {expectation.stop_after}, got {result.executed_stages[-1]}")

    if expectation.temporal_status is not None and result.temporal_status != expectation.temporal_status:
        raise AssertionError(f"temporal_status expected {expectation.temporal_status}, got {result.temporal_status}")

    if expectation.benchmark_status is not None and result.benchmark_status != expectation.benchmark_status:
        raise AssertionError(f"benchmark_status expected {expectation.benchmark_status}, got {result.benchmark_status}")

    comparison_present = result.comparison_plan is not None
    if comparison_present != expectation.comparison_present:
        raise AssertionError(f"comparison_present expected {expectation.comparison_present}, got {comparison_present}")

    if expectation.comparison_metrics_computed:
        if result.comparison_metrics_count <= 0:
            raise AssertionError("expected comparison metrics to be computed")
    elif result.comparison_metrics_count != 0:
        raise AssertionError(f"expected no comparison metrics, got {result.comparison_metrics_count}")

    if expectation.benchmark_type is not None:
        actual_type = _extract_benchmark_type(workflow_plan)
        if actual_type != expectation.benchmark_type:
            raise AssertionError(f"benchmark_type expected {expectation.benchmark_type}, got {actual_type}")

    if expectation.temporal_mode is not None:
        actual_mode = _extract_temporal_mode(workflow_plan)
        if actual_mode != expectation.temporal_mode:
            raise AssertionError(f"temporal_mode expected {expectation.temporal_mode}, got {actual_mode}")

    if expectation.reason_code is not None:
        temporal_reason = _extract_reason_code(workflow_plan, "temporal")
        benchmark_reason = _extract_reason_code(workflow_plan, "benchmark")
        if expectation.reason_code not in {temporal_reason, benchmark_reason}:
            raise AssertionError(
                f"reason_code expected {expectation.reason_code}, got temporal={temporal_reason}, benchmark={benchmark_reason}"
            )

    for substring in expectation.expected_log_substrings:
        if not any(substring in log for log in result.logs):
            raise AssertionError(f"expected log substring {substring!r} not found in {result.logs}")


def run_workflow_acceptance_plan(plan: WorkflowAcceptancePlan) -> WorkflowAcceptanceResult:
    state = CensusState(
        messages=[{"role": "user", "content": plan.query}],
        original_query=plan.query,
    )
    executed_stages: list[WorkflowPipelineStage] = []
    logs: list[str] = []
    workflow_plan = WorkflowPlan()

    temporal_output = temporal_node(state, {})
    executed_stages.append(WorkflowPipelineStage.TEMPORAL)
    logs.extend(temporal_output.get("logs", []))
    workflow_plan = temporal_output["plan"]
    state = state.model_copy(update={"plan": workflow_plan})

    if _route_after_temporal(workflow_plan) == "output":
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=workflow_plan.requires_clarification,
            temporal_status=_extract_temporal_status(workflow_plan),
            benchmark_status=_extract_benchmark_status(workflow_plan),
            logs=logs,
            final_answer_present=temporal_output.get("final") is not None,
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    benchmark_output = benchmark_node(state, {})
    executed_stages.append(WorkflowPipelineStage.BENCHMARK)
    logs.extend(benchmark_output.get("logs", []))
    workflow_plan = benchmark_output["plan"]
    state = state.model_copy(update={"plan": workflow_plan})

    if _route_after_benchmark(workflow_plan) == "output":
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=workflow_plan.requires_clarification,
            temporal_status=_extract_temporal_status(workflow_plan),
            benchmark_status=_extract_benchmark_status(workflow_plan),
            logs=logs,
            final_answer_present=(temporal_output.get("final") is not None or benchmark_output.get("final") is not None),
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    if _route_after_benchmark(workflow_plan) == "agent":
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=workflow_plan.requires_clarification,
            temporal_status=_extract_temporal_status(workflow_plan),
            benchmark_status=_extract_benchmark_status(workflow_plan),
            logs=logs,
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    comparison_output = comparison_node(state, {})
    executed_stages.append(WorkflowPipelineStage.COMPARISON)
    logs.extend(comparison_output.get("logs", []))
    workflow_plan = comparison_output["plan"]
    state = state.model_copy(update={"plan": workflow_plan})

    comparison_plan = workflow_plan.comparison

    if plan.expectation.comparison_metrics_computed:
        artifacts = {"comparison_input_rows": [row.model_dump() for row in (plan.comparison_input_rows or [])]}
        state = state.model_copy(update={"artifacts": artifacts})
        metrics_output = comparison_metrics_node(state, {})
        executed_stages.append(WorkflowPipelineStage.COMPARISON_METRICS)
        logs.extend(metrics_output.get("logs", []))
        metrics_rows = (metrics_output.get("artifacts") or {}).get("comparison_metrics", [])
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=workflow_plan.requires_clarification,
            temporal_status=_extract_temporal_status(workflow_plan),
            benchmark_status=_extract_benchmark_status(workflow_plan),
            comparison_plan=comparison_plan,
            comparison_metrics_count=len(metrics_rows),
            logs=logs,
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    result = WorkflowAcceptanceResult(
        plan_id=plan.plan_id,
        executed_stages=executed_stages,
        requires_clarification=workflow_plan.requires_clarification,
        temporal_status=_extract_temporal_status(workflow_plan),
        benchmark_status=_extract_benchmark_status(workflow_plan),
        comparison_plan=comparison_plan,
        logs=logs,
    )
    _validate_expectation(result, workflow_plan, plan.expectation)
    return result


def assert_workflow_acceptance_plan(plan: WorkflowAcceptancePlan) -> WorkflowAcceptanceResult:
    try:
        return run_workflow_acceptance_plan(plan)
    except ValidationError as exc:
        raise AssertionError(f"workflow acceptance plan {plan.plan_id} failed validation: {exc}") from exc

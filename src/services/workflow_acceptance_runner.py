from typing import Any

from pydantic import ValidationError

from src.domain.comparison_plan import ComparisonPlan
from src.domain.workflow_acceptance import (
    WorkflowAcceptanceExpectation,
    WorkflowAcceptancePlan,
    WorkflowAcceptanceResult,
    WorkflowPipelineStage,
)
from src.state.types import CensusState
from src.workflows.benchmark import benchmark_node
from src.workflows.comparison import comparison_node
from src.workflows.comparison_metrics import comparison_metrics_node
from src.workflows.temporal import temporal_node


def _route_after_temporal(plan: dict[str, Any]) -> str:
    if plan.get("requires_clarification"):
        return "output"
    return "benchmark"


def _route_after_benchmark(plan: dict[str, Any]) -> str:
    if plan.get("requires_clarification"):
        return "output"
    benchmark_plan = plan.get("benchmark") or {}
    if benchmark_plan.get("status") == "not_applicable":
        return "agent"
    return "comparison"


def _extract_status(plan: dict[str, Any], key: str) -> str | None:
    section = plan.get(key)
    if not isinstance(section, dict):
        return None
    status = section.get("status")
    return status if isinstance(status, str) else None


def _extract_reason_code(plan: dict[str, Any], key: str) -> str | None:
    section = plan.get(key)
    if not isinstance(section, dict):
        return None
    reason_code = section.get("reason_code")
    return reason_code if isinstance(reason_code, str) else None


def _extract_temporal_mode(plan: dict[str, Any]) -> str | None:
    temporal = plan.get("temporal")
    if not isinstance(temporal, dict):
        return None
    time_section = temporal.get("time")
    if not isinstance(time_section, dict):
        return None
    mode = time_section.get("mode")
    return mode if isinstance(mode, str) else None


def _extract_benchmark_type(plan: dict[str, Any]) -> str | None:
    benchmark = plan.get("benchmark")
    if not isinstance(benchmark, dict):
        return None
    benchmark_section = benchmark.get("benchmark")
    if not isinstance(benchmark_section, dict):
        return None
    benchmark_type = benchmark_section.get("benchmark_type")
    return benchmark_type if isinstance(benchmark_type, str) else None


def _validate_expectation(
    result: WorkflowAcceptanceResult,
    workflow_plan: dict[str, Any],
    expectation: WorkflowAcceptanceExpectation,
) -> None:
    if result.requires_clarification != expectation.requires_clarification:
        raise AssertionError(
            f"requires_clarification expected {expectation.requires_clarification}, "
            f"got {result.requires_clarification}"
        )

    if result.executed_stages[-1] != expectation.stop_after:
        raise AssertionError(
            f"stop_after expected {expectation.stop_after}, got {result.executed_stages[-1]}"
        )

    if expectation.temporal_status is not None and result.temporal_status != expectation.temporal_status:
        raise AssertionError(
            f"temporal_status expected {expectation.temporal_status}, got {result.temporal_status}"
        )

    if expectation.benchmark_status is not None and result.benchmark_status != expectation.benchmark_status:
        raise AssertionError(
            f"benchmark_status expected {expectation.benchmark_status}, got {result.benchmark_status}"
        )

    comparison_present = result.comparison_plan is not None
    if comparison_present != expectation.comparison_present:
        raise AssertionError(
            f"comparison_present expected {expectation.comparison_present}, "
            f"got {comparison_present}"
        )

    if expectation.comparison_metrics_computed:
        if result.comparison_metrics_count <= 0:
            raise AssertionError("expected comparison metrics to be computed")
    elif result.comparison_metrics_count != 0:
        raise AssertionError(
            f"expected no comparison metrics, got {result.comparison_metrics_count}"
        )

    if expectation.benchmark_type is not None:
        actual_type = _extract_benchmark_type(workflow_plan)
        if actual_type != expectation.benchmark_type:
            raise AssertionError(
                f"benchmark_type expected {expectation.benchmark_type}, got {actual_type}"
            )

    if expectation.temporal_mode is not None:
        actual_mode = _extract_temporal_mode(workflow_plan)
        if actual_mode != expectation.temporal_mode:
            raise AssertionError(
                f"temporal_mode expected {expectation.temporal_mode}, got {actual_mode}"
            )

    if expectation.reason_code is not None:
        temporal_reason = _extract_reason_code(workflow_plan, "temporal")
        benchmark_reason = _extract_reason_code(workflow_plan, "benchmark")
        if expectation.reason_code not in {temporal_reason, benchmark_reason}:
            raise AssertionError(
                f"reason_code expected {expectation.reason_code}, "
                f"got temporal={temporal_reason}, benchmark={benchmark_reason}"
            )

    for substring in expectation.expected_log_substrings:
        if not any(substring in log for log in result.logs):
            raise AssertionError(
                f"expected log substring {substring!r} not found in {result.logs}"
            )


def run_workflow_acceptance_plan(plan: WorkflowAcceptancePlan) -> WorkflowAcceptanceResult:
    state = CensusState(
        messages=[{"role": "user", "content": plan.query}],
        original_query=plan.query,
    )
    executed_stages: list[WorkflowPipelineStage] = []
    logs: list[str] = []
    workflow_plan: dict[str, Any] = {}

    temporal_output = temporal_node(state, {})
    executed_stages.append(WorkflowPipelineStage.TEMPORAL)
    logs.extend(temporal_output.get("logs", []))
    workflow_plan = temporal_output.get("plan") or {}
    state = state.model_copy(update={"plan": workflow_plan})

    if _route_after_temporal(workflow_plan) == "output":
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=bool(workflow_plan.get("requires_clarification")),
            temporal_status=_extract_status(workflow_plan, "temporal"),
            benchmark_status=_extract_status(workflow_plan, "benchmark"),
            logs=logs,
            final_answer_present=temporal_output.get("final") is not None,
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    benchmark_output = benchmark_node(state, {})
    executed_stages.append(WorkflowPipelineStage.BENCHMARK)
    logs.extend(benchmark_output.get("logs", []))
    workflow_plan = benchmark_output.get("plan") or workflow_plan
    state = state.model_copy(update={"plan": workflow_plan})

    if _route_after_benchmark(workflow_plan) == "output":
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=bool(workflow_plan.get("requires_clarification")),
            temporal_status=_extract_status(workflow_plan, "temporal"),
            benchmark_status=_extract_status(workflow_plan, "benchmark"),
            logs=logs,
            final_answer_present=(
                temporal_output.get("final") is not None
                or benchmark_output.get("final") is not None
            ),
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    if _route_after_benchmark(workflow_plan) == "agent":
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=bool(workflow_plan.get("requires_clarification")),
            temporal_status=_extract_status(workflow_plan, "temporal"),
            benchmark_status=_extract_status(workflow_plan, "benchmark"),
            logs=logs,
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    comparison_output = comparison_node(state, {})
    executed_stages.append(WorkflowPipelineStage.COMPARISON)
    logs.extend(comparison_output.get("logs", []))
    workflow_plan = comparison_output.get("plan") or workflow_plan
    state = state.model_copy(update={"plan": workflow_plan})

    comparison_plan: ComparisonPlan | None = None
    comparison_raw = workflow_plan.get("comparison")
    if comparison_raw:
        comparison_plan = ComparisonPlan.model_validate(comparison_raw)

    if plan.expectation.comparison_metrics_computed:
        artifacts = {
            "comparison_input_rows": [
                row.model_dump() for row in (plan.comparison_input_rows or [])
            ]
        }
        state = state.model_copy(update={"artifacts": artifacts})
        metrics_output = comparison_metrics_node(state, {})
        executed_stages.append(WorkflowPipelineStage.COMPARISON_METRICS)
        logs.extend(metrics_output.get("logs", []))
        metrics_rows = (metrics_output.get("artifacts") or {}).get(
            "comparison_metrics", []
        )
        result = WorkflowAcceptanceResult(
            plan_id=plan.plan_id,
            executed_stages=executed_stages,
            requires_clarification=bool(workflow_plan.get("requires_clarification")),
            temporal_status=_extract_status(workflow_plan, "temporal"),
            benchmark_status=_extract_status(workflow_plan, "benchmark"),
            comparison_plan=comparison_plan,
            comparison_metrics_count=len(metrics_rows),
            logs=logs,
        )
        _validate_expectation(result, workflow_plan, plan.expectation)
        return result

    result = WorkflowAcceptanceResult(
        plan_id=plan.plan_id,
        executed_stages=executed_stages,
        requires_clarification=bool(workflow_plan.get("requires_clarification")),
        temporal_status=_extract_status(workflow_plan, "temporal"),
        benchmark_status=_extract_status(workflow_plan, "benchmark"),
        comparison_plan=comparison_plan,
        logs=logs,
    )
    _validate_expectation(result, workflow_plan, plan.expectation)
    return result


def assert_workflow_acceptance_plan(plan: WorkflowAcceptancePlan) -> WorkflowAcceptanceResult:
    try:
        return run_workflow_acceptance_plan(plan)
    except ValidationError as exc:
        raise AssertionError(
            f"workflow acceptance plan {plan.plan_id} failed validation: {exc}"
        ) from exc

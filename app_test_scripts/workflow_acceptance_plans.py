from src.domain.comparison_artifacts import ComparisonInputRow
from src.domain.workflow_acceptance import (
    WorkflowAcceptanceExpectation,
    WorkflowAcceptancePlan,
    WorkflowPipelineStage,
)

CANONICAL_WORKFLOW_ACCEPTANCE_PLANS: list[WorkflowAcceptancePlan] = [
    WorkflowAcceptancePlan(
        plan_id="non_comparison_latest_available",
        query="population of california",
        description="Non-comparison census query defaults to latest_available and skips benchmark planning.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=False,
            stop_after=WorkflowPipelineStage.BENCHMARK,
            temporal_status="resolved",
            benchmark_status="not_applicable",
            temporal_mode="latest_available",
            expected_log_substrings=[
                "temporal: resolved",
                "benchmark: skipped (no comparison intent)",
            ],
        ),
    ),
    WorkflowAcceptancePlan(
        plan_id="temporal_conflict_clarification",
        query="compare 2019 vs 2023 over the last 5 years",
        description="Conflicting temporal signals fail closed to clarification at the temporal gate.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=True,
            stop_after=WorkflowPipelineStage.TEMPORAL,
            temporal_status="clarification_required",
            reason_code="TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING",
            expected_log_substrings=[
                "temporal: clarification required (TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING)",
            ],
        ),
    ),
    WorkflowAcceptancePlan(
        plan_id="benchmark_missing_metric_clarification",
        query="compare state vs national",
        description="Comparison intent without a metric fails closed at the benchmark gate.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=True,
            stop_after=WorkflowPipelineStage.BENCHMARK,
            temporal_status="resolved",
            benchmark_status="clarification_required",
            temporal_mode="latest_available",
            reason_code="BENCHMARK_MISSING_METRIC",
            expected_log_substrings=[
                "benchmark: clarification required (BENCHMARK_MISSING_METRIC)",
            ],
        ),
    ),
    WorkflowAcceptancePlan(
        plan_id="benchmark_conflict_clarification",
        query="compare population baseline vs 2019 and peer group counties",
        description="Conflicting benchmark semantics fail closed at the benchmark gate.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=True,
            stop_after=WorkflowPipelineStage.BENCHMARK,
            temporal_status="resolved",
            benchmark_status="clarification_required",
            temporal_mode="point_in_time",
            reason_code="BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP",
            expected_log_substrings=[
                "benchmark: clarification required (BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP)",
            ],
        ),
    ),
    WorkflowAcceptancePlan(
        plan_id="resolved_peer_group_comparison",
        query="compare population for counties",
        description="Resolved peer-group comparison produces a typed ComparisonPlan artifact.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=False,
            stop_after=WorkflowPipelineStage.COMPARISON,
            temporal_status="resolved",
            benchmark_status="resolved",
            comparison_present=True,
            benchmark_type="peer_group",
            temporal_mode="latest_available",
            expected_log_substrings=[
                "temporal: resolved",
                "benchmark: resolved",
                "comparison: resolved",
            ],
        ),
    ),
    WorkflowAcceptancePlan(
        plan_id="named_state_custom_set_comparison",
        query="Compare California vs Texas population in 2020",
        description="Named state-vs-state comparisons resolve to a custom_set benchmark and comparison plan.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=False,
            stop_after=WorkflowPipelineStage.COMPARISON,
            temporal_status="resolved",
            benchmark_status="resolved",
            comparison_present=True,
            benchmark_type="custom_set",
            temporal_mode="point_in_time",
            expected_log_substrings=[
                "temporal: resolved",
                "benchmark: resolved",
                "comparison: resolved",
            ],
        ),
    ),
    WorkflowAcceptancePlan(
        plan_id="national_benchmark_comparison",
        query="compare population against national average",
        description="National benchmark comparisons resolve through all planning gates.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=False,
            stop_after=WorkflowPipelineStage.COMPARISON,
            temporal_status="resolved",
            benchmark_status="resolved",
            comparison_present=True,
            benchmark_type="national",
            temporal_mode="latest_available",
            expected_log_substrings=[
                "temporal: resolved",
                "benchmark: resolved",
                "comparison: resolved",
            ],
        ),
    ),
    WorkflowAcceptancePlan(
        plan_id="comparison_metrics_end_to_end",
        query="Compare California vs Texas population in 2020",
        description="Planning pipeline feeds typed rows into comparison_metrics deterministic compute.",
        expectation=WorkflowAcceptanceExpectation(
            requires_clarification=False,
            stop_after=WorkflowPipelineStage.COMPARISON_METRICS,
            temporal_status="resolved",
            benchmark_status="resolved",
            comparison_present=True,
            comparison_metrics_computed=True,
            benchmark_type="custom_set",
            temporal_mode="point_in_time",
            expected_log_substrings=[
                "comparison: resolved",
                "comparison_metrics: computed",
            ],
        ),
        comparison_input_rows=[
            ComparisonInputRow(
                year=2020,
                geo_id="state:06",
                metric="population",
                value=39500000.0,
                benchmark_value=39500000.0,
            ),
            ComparisonInputRow(
                year=2020,
                geo_id="state:48",
                metric="population",
                value=29100000.0,
                benchmark_value=29100000.0,
            ),
        ],
    ),
]

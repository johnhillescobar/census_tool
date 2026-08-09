import logging

from src.domain.agent_clarification_context import AgentClarificationContext
from src.domain.agent_plan_context import AgentPlanContext
from src.domain.benchmark_contract import BenchmarkClarificationRequired
from src.domain.comparison_plan import ComparisonPlan
from src.domain.execution_spec import build_execution_spec
from src.domain.geography_contract import GeographyClarificationRequired
from src.domain.temporal_contract import TemporalClarificationRequired
from src.services.agent_clarification_copy import format_readable_option_label
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan

logger = logging.getLogger(__name__)


def is_geography_clarification_flow(plan: WorkflowPlan | None) -> bool:
    """True when clarification is table/geo pending state rather than temporal/benchmark."""
    if plan is None:
        return False
    if plan.pending_geography_clarification is not None:
        return True
    return isinstance(plan.geography, GeographyClarificationRequired)


def should_skip_agent_for_upstream_clarification(plan: WorkflowPlan | None) -> bool:
    """Skip agent nodes only for non-geography clarifications."""
    if plan is None or not plan.requires_clarification:
        return False
    return not is_geography_clarification_flow(plan)


def build_agent_clarification_context(plan: WorkflowPlan | None) -> AgentClarificationContext | None:
    """Build checkpointed clarification context for agent turn-2 resume (CENSUS-44)."""

    if plan is None or plan.pending_geography_clarification is None:
        return None

    pending = plan.pending_geography_clarification
    checkpoint = plan.agent_clarification_checkpoint
    if checkpoint is not None and checkpoint.trace_id == pending.trace_id:
        return checkpoint.model_copy(
            update={
                "pending_options": list(pending.options),
                "retrieval_evidence": list(plan.retrieval_evidence),
            }
        )

    return AgentClarificationContext(
        original_query=pending.original_query,
        requested_slot=pending.requested_slot,
        pending_options=list(pending.options),
        retrieval_evidence=list(plan.retrieval_evidence),
        reason_code=pending.reason_code,
        trace_id=pending.trace_id,
    )


def format_clarification_directives(ctx: AgentClarificationContext) -> str:
    """Render grounded clarification options for the agent clarification turn."""

    lines = [
        "Pending clarification (grounded options from preserved retrieval evidence):",
        f"- Original query: {ctx.original_query}",
        f"- Requested slot: {ctx.requested_slot}",
        f"- Reason code: {ctx.reason_code}",
        f"- Trace id: {ctx.trace_id}",
    ]
    if ctx.turn1_prompt_text:
        lines.extend(
            [
                "- Turn-1 clarification shown to the user:",
                ctx.turn1_prompt_text,
            ]
        )
    lines.append("- Options (select one grounded candidate):")
    for option in ctx.pending_options:
        readable = format_readable_option_label(option, ctx)
        lines.append(f"  - {readable} [candidate_id={option.candidate_id}]")
    lines.extend(
        [
            "- Map the user reply to one grounded option using select_clarification_option.",
            "- Call select_clarification_option with candidate_id; do not invent ids.",
        ]
    )
    return "\n".join(lines)


def build_agent_planning_context(plan: WorkflowPlan | None) -> AgentPlanContext | None:
    """Build temporal-only context for the retrieval planning turn after temporal_node."""

    if plan is None or should_skip_agent_for_upstream_clarification(plan):
        return None

    if isinstance(plan.temporal, TemporalClarificationRequired):
        return None

    temporal_intent = plan.resolved_temporal_intent()
    if temporal_intent is None:
        return None

    return AgentPlanContext(
        geography=None,
        temporal=temporal_intent,
        benchmark=None,
        comparison=None,
        selected_table=None,
        grounded_plan=None,
        has_comparison_plan=False,
    )


def build_agent_plan_context(plan: WorkflowPlan | None) -> AgentPlanContext | None:
    """Parse workflow planning artifacts into a typed agent context."""

    if plan is None or should_skip_agent_for_upstream_clarification(plan):
        return None

    geography_intent = plan.resolved_geography_intent()

    temporal_intent = plan.resolved_temporal_intent()

    benchmark_intent = plan.resolved_benchmark_intent()

    comparison_plan: ComparisonPlan | None = plan.comparison

    if isinstance(plan.geography, GeographyClarificationRequired):
        return None

    if isinstance(plan.benchmark, BenchmarkClarificationRequired):
        return None

    if isinstance(plan.temporal, TemporalClarificationRequired):
        return None

    if isinstance(plan.benchmark, BenchmarkNotApplicable):
        if temporal_intent is None or geography_intent is None:
            return None

        return AgentPlanContext(
            geography=geography_intent,
            temporal=temporal_intent,
            benchmark=None,
            comparison=None,
            selected_table=plan.selected_table,
            grounded_plan=plan.grounded_plan,
            has_comparison_plan=False,
        )

    if comparison_plan is not None:
        if temporal_intent is None or benchmark_intent is None or geography_intent is None:
            return None

        return AgentPlanContext(
            geography=geography_intent,
            temporal=temporal_intent,
            benchmark=benchmark_intent,
            comparison=comparison_plan,
            selected_table=plan.selected_table,
            grounded_plan=plan.grounded_plan,
            has_comparison_plan=True,
        )

    if temporal_intent is not None and geography_intent is not None:
        return AgentPlanContext(
            geography=geography_intent,
            temporal=temporal_intent,
            benchmark=benchmark_intent,
            comparison=None,
            selected_table=plan.selected_table,
            grounded_plan=plan.grounded_plan,
            has_comparison_plan=False,
        )

    return None


def format_plan_directives(ctx: AgentPlanContext) -> str:
    """Render deterministic planning directives for the reasoning agent prompt."""

    lines: list[str] = []

    if ctx.selected_table is not None:
        table = ctx.selected_table
        lines.extend(
            [
                f"- Validated dataset: {table.dataset}",
                f"- Validated table: {table.table_code} ({table.table_name})",
                f"- Validated table years: {table.years_available}",
                "- Use only variables from the validated table; do not select a different table or dataset.",
            ]
        )

    if ctx.geography is not None:
        geo = ctx.geography

        lines.extend(
            [
                f"- Geography level: {geo.level}",
                f"- Geography display name: {geo.display_name}",
                f"- Geography source: {geo.source}",
                f"- geo_for: {geo.geo_for}",
                f"- geo_in: {geo.geo_in}",
                "- Do NOT ask the user for geography again; use the resolved geography above.",
            ]
        )

    if ctx.temporal is not None:
        temporal = ctx.temporal

        if temporal.mode == "point_in_time":
            lines.append(f"- Temporal mode: point_in_time (anchor_year={temporal.anchor_year})")

        elif temporal.mode == "range":
            lines.append(f"- Temporal mode: range (start_year={temporal.start_year}, end_year={temporal.end_year})")

        elif temporal.mode == "multi_period_compare":
            lines.append(
                f"- Temporal mode: multi_period_compare (start_year={temporal.start_year}, end_year={temporal.end_year})"
            )

        elif temporal.mode == "rolling":
            lines.append("- Temporal mode: rolling")

        else:
            lines.append("- Temporal mode: latest_available")

        lines.append(f"- Missing year policy: {temporal.missing_year_policy}")

    spec = build_execution_spec(ctx)

    if spec is not None:
        if spec.query_years:
            lines.append(f"- Required query years: {spec.query_years}")

        if spec.requires_time_series:
            lines.extend(
                [
                    "- Execution obligation: make one Census API call per required year.",
                    "- Aggregate into a Year column time series; use a line chart only when data exists.",
                    "- Do not return success:false solely because geography was unspecified.",
                ]
            )

        lines.append(f"- Required output shape: {spec.output_shape}")

    if ctx.benchmark is not None:
        benchmark = ctx.benchmark

        lines.extend(
            [
                f"- Benchmark type: {benchmark.benchmark_type}",
                f"- Subject geo level: {benchmark.subject_geo_level}",
                f"- Subject geos: {benchmark.subject_geo}",
                f"- Benchmark geo level: {benchmark.benchmark_geo_level}",
                f"- Benchmark geos: {benchmark.benchmark_geos}",
                f"- Metric: {benchmark.metric}",
                f"- Comparison operator: {benchmark.comparison_op}",
                f"- Normalization: {benchmark.normalization}",
            ]
        )

        if benchmark.baseline_anchor_year is not None:
            lines.append(f"- Baseline anchor year: {benchmark.baseline_anchor_year}")

        if benchmark.baseline_window is not None:
            lines.append(f"- Baseline window: {benchmark.baseline_window}")

    if ctx.comparison is not None:
        comparison = ctx.comparison

        lines.extend(
            [
                f"- Query years: {comparison.query_years}",
                f"- Dataset: {comparison.dataset}",
                f"- Derived metrics: {comparison.derived_metrics}",
                f"- Join keys: {comparison.join_keys}",
                "- Resolve placeholder geos via geography tools before querying.",
                "- Include comparison_input_rows in Final Answer JSON for each (year, geo_id) pair.",
            ]
        )

    return "\n".join(lines)

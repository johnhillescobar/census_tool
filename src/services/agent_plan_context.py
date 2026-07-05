import logging

from src.domain.agent_plan_context import AgentPlanContext
from src.domain.benchmark_contract import BenchmarkClarificationRequired
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import TemporalClarificationRequired
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan

logger = logging.getLogger(__name__)


def build_agent_plan_context(plan: WorkflowPlan | None) -> AgentPlanContext | None:
    """Parse workflow planning artifacts into a typed agent context."""
    if plan is None or plan.requires_clarification:
        return None

    temporal_intent = plan.resolved_temporal_intent()
    benchmark_intent = plan.resolved_benchmark_intent()
    comparison_plan: ComparisonPlan | None = plan.comparison

    if isinstance(plan.benchmark, BenchmarkNotApplicable):
        if temporal_intent is None:
            return None
        return AgentPlanContext(
            temporal=temporal_intent,
            benchmark=None,
            comparison=None,
            has_comparison_plan=False,
        )

    if isinstance(plan.benchmark, BenchmarkClarificationRequired):
        return None

    if isinstance(plan.temporal, TemporalClarificationRequired):
        return None

    if comparison_plan is not None:
        if temporal_intent is None or benchmark_intent is None:
            return None
        return AgentPlanContext(
            temporal=temporal_intent,
            benchmark=benchmark_intent,
            comparison=comparison_plan,
            has_comparison_plan=True,
        )

    if temporal_intent is not None:
        return AgentPlanContext(
            temporal=temporal_intent,
            benchmark=benchmark_intent,
            comparison=None,
            has_comparison_plan=False,
        )

    return None


def format_plan_directives(ctx: AgentPlanContext) -> str:
    """Render deterministic planning directives for the reasoning agent prompt."""
    lines: list[str] = []

    if ctx.temporal is not None:
        temporal = ctx.temporal
        if temporal.mode == "point_in_time":
            lines.append(
                f"- Temporal mode: point_in_time (anchor_year={temporal.anchor_year})"
            )
        elif temporal.mode == "range":
            lines.append(
                f"- Temporal mode: range (start_year={temporal.start_year}, end_year={temporal.end_year})"
            )
        elif temporal.mode == "multi_period_compare":
            lines.append(
                "- Temporal mode: multi_period_compare "
                f"(start_year={temporal.start_year}, end_year={temporal.end_year})"
            )
        elif temporal.mode == "rolling":
            lines.append("- Temporal mode: rolling")
        else:
            lines.append("- Temporal mode: latest_available")
        lines.append(f"- Missing year policy: {temporal.missing_year_policy}")

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

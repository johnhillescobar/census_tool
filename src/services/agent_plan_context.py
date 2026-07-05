import logging
from typing import Any

from pydantic import ValidationError

from src.domain.agent_plan_context import AgentPlanContext
from src.domain.benchmark_contract import BenchmarkIntent
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import TemporalIntent

logger = logging.getLogger(__name__)


def build_agent_plan_context(plan: dict[str, Any] | None) -> AgentPlanContext | None:
    """Parse workflow planning artifacts into a typed agent context."""
    if not plan or plan.get("requires_clarification"):
        return None

    temporal_plan = plan.get("temporal")
    benchmark_plan = plan.get("benchmark")
    comparison_raw = plan.get("comparison")

    temporal_intent: TemporalIntent | None = None
    benchmark_intent: BenchmarkIntent | None = None
    comparison_plan: ComparisonPlan | None = None

    if temporal_plan and temporal_plan.get("status") == "resolved":
        try:
            temporal_intent = TemporalIntent.model_validate(
                temporal_plan.get("time", {})
            )
        except ValidationError as exc:
            logger.warning("agent plan context: invalid temporal intent: %s", exc)
            return None

    if benchmark_plan:
        benchmark_status = benchmark_plan.get("status")
        if benchmark_status == "not_applicable":
            if temporal_intent is None:
                return None
            return AgentPlanContext(
                temporal=temporal_intent,
                benchmark=None,
                comparison=None,
                has_comparison_plan=False,
            )
        if benchmark_status != "resolved":
            return None
        try:
            benchmark_intent = BenchmarkIntent.model_validate(
                benchmark_plan.get("benchmark", {})
            )
        except ValidationError as exc:
            logger.warning("agent plan context: invalid benchmark intent: %s", exc)
            return None

    if comparison_raw:
        try:
            comparison_plan = ComparisonPlan.model_validate(comparison_raw)
        except ValidationError as exc:
            logger.warning("agent plan context: invalid comparison plan: %s", exc)
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

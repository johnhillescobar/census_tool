from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field
from src.domain.temporal_contract import ClarificationPrompt, ClarificationOption
from src.domain.benchmark_contract import (
    BenchmarkClarificationPrompt,
    BenchmarkClarificationOption,
)


# Define the slots for the temporal clarification template
class TemporalExplicitVsRollingSlots(BaseModel):
    """Slots for the temporal explicit vs rolling clarification template."""

    reason_code: Literal["TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING"] = (
        "TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING"
    )
    year_a: int
    year_b: int
    window_text: str


class TemporalAmbiguousGenericSlots(BaseModel):
    """Slots for the temporal ambiguous generic clarification template."""

    reason_code: Literal["TEMPORAL_AMBIGUOUS_GENERIC"] = "TEMPORAL_AMBIGUOUS_GENERIC"


# Define the slots for the benchmark clarification template
class BenchmarkAmbiguousTargetSlots(BaseModel):
    reason_code: Literal["BENCHMARK_AMBIGUOUS_TARGET"] = "BENCHMARK_AMBIGUOUS_TARGET"
    subject_text: str


class BenchmarkMissingMetricSlots(BaseModel):
    reason_code: Literal["BENCHMARK_MISSING_METRIC"] = "BENCHMARK_MISSING_METRIC"
    subject_text: str
    metric: str


class BenchmarkMissingGeoLevelSlots(BaseModel):
    reason_code: Literal["BENCHMARK_MISSING_GEO_LEVEL"] = "BENCHMARK_MISSING_GEO_LEVEL"
    subject_text: str
    geo_level: str


class BenchmarkConflictBaselineVsPeerGroupSlots(BaseModel):
    reason_code: Literal["BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP"] = (
        "BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP"
    )
    subject_text: str


class BenchmarkBaselineDeferredSlots(BaseModel):
    reason_code: Literal["BENCHMARK_BASELINE_DEFERRED"] = (
        "BENCHMARK_BASELINE_DEFERRED"
    )
    subject_text: str


# Create OptionTemplate for the clarification prompt


class OptionTemplate(BaseModel):
    """Template for an option in a clarification prompt."""

    option_id: str
    label_template: str


class ClarificationTemplate(BaseModel):
    """Template for a clarification prompt."""

    template_id: str
    reason_code: str
    question_template: str
    option_templates: list[OptionTemplate]


# Define the templates for the clarification prompt
TEMPLATES: dict[str, ClarificationTemplate] = {
    "TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING": ClarificationTemplate(
        template_id="temporal.explicit_vs_rolling.v1",
        reason_code="TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING",
        question_template=(
            "Your request includes explicit years ({year_a} and {year_b}) and "
            "a rolling window ({window_text}). Which one should I run?"
        ),
        option_templates=[
            OptionTemplate(
                option_id="explicit_compare",
                label_template="Compare {year_a} vs {year_b}",
            ),
            OptionTemplate(
                option_id="rolling_trend",
                label_template="Run a full {window_text} trend ending {year_b}",
            ),
            OptionTemplate(option_id="cancel", label_template="Cancel"),
        ],
    ),
    "TEMPORAL_AMBIGUOUS_GENERIC": ClarificationTemplate(
        template_id="temporal.ambiguous.generic.v1",
        reason_code="TEMPORAL_AMBIGUOUS_GENERIC",
        question_template=(
            "I found multiple valid time interpretations in your request. "
            "Please choose one so I can run the query deterministically."
        ),
        option_templates=[
            OptionTemplate(
                option_id="explicit_years", label_template="Use explicit years only"
            ),
            OptionTemplate(
                option_id="rolling_or_latest",
                label_template="Use rolling/latest interpretation",
            ),
            OptionTemplate(option_id="cancel", label_template="Cancel"),
        ],
    ),
    "BENCHMARK_AMBIGUOUS_TARGET": ClarificationTemplate(
        template_id="benchmark.ambiguous_target.v1",
        reason_code="BENCHMARK_AMBIGUOUS_TARGET",
        question_template=(
            "I found multiple valid target interpretations in your request."
            " Please choose one so I can run the query deterministically."
        ),
        option_templates=[
            OptionTemplate(
                option_id="subject_geo",
                label_template="Use {subject_text} as the target",
            ),
        ],
    ),
    "BENCHMARK_MISSING_METRIC": ClarificationTemplate(
        template_id="benchmark.missing_metric.v1",
        reason_code="BENCHMARK_MISSING_METRIC",
        question_template=(
            "I found a missing metric in your request. Please choose one so"
            " I can run the query deterministically."
        ),
        option_templates=[
            OptionTemplate(
                option_id="population", label_template="Population {metric}"
            ),
            OptionTemplate(
                option_id="median_income",
                label_template="Median household income {metric}",
            ),
            OptionTemplate(
                option_id="poverty_rate", label_template="Poverty rate {metric}"
            ),
            OptionTemplate(
                option_id="unemployment", label_template="Unemployment {metric}"
            ),
            OptionTemplate(option_id="education", label_template="Education {metric}"),
            OptionTemplate(option_id="hispanic", label_template="Hispanic {metric}"),
            OptionTemplate(option_id="race", label_template="Race {metric}"),
            OptionTemplate(option_id="ethnicity", label_template="Ethnicity {metric}"),
            OptionTemplate(option_id="housing", label_template="Housing {metric}"),
            OptionTemplate(option_id="rent", label_template="Rent {metric}"),
            OptionTemplate(option_id="mortgage", label_template="Mortgage {metric}"),
            OptionTemplate(
                option_id="labor_force", label_template="Labor force {metric}"
            ),
            OptionTemplate(option_id="household", label_template="Household {metric}"),
            OptionTemplate(option_id="other", label_template="Other {metric}"),
            OptionTemplate(option_id="cancel", label_template="Cancel"),
        ],
    ),
    "BENCHMARK_MISSING_GEO_LEVEL": ClarificationTemplate(
        template_id="benchmark.missing_geo_level.v1",
        reason_code="BENCHMARK_MISSING_GEO_LEVEL",
        question_template=(
            "I found a missing geography level in your request. Please choose one so I can run the query deterministically."
        ),
        option_templates=[
            OptionTemplate(
                option_id="geo_level",
                label_template="Use {geo_level} as the geography level",
            ),
        ],
    ),
    "BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP": ClarificationTemplate(
        template_id="benchmark.conflict_baseline_vs_peer_group.v1",
        reason_code="BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP",
        question_template=(
            "I found a conflict between the baseline and the peer group in your request."
            " Please choose one so I can run the query deterministically."
        ),
        option_templates=[
            OptionTemplate(option_id="baseline", label_template="Use the baseline"),
            OptionTemplate(option_id="peer_group", label_template="Use the peer group"),
        ],
    ),
    "BENCHMARK_BASELINE_DEFERRED": ClarificationTemplate(
        template_id="benchmark.baseline_deferred.v1",
        reason_code="BENCHMARK_BASELINE_DEFERRED",
        question_template=(
            "Historical baseline comparisons are not enabled in Track 2A. "
            "Please choose a supported benchmark comparison instead."
        ),
        option_templates=[
            OptionTemplate(
                option_id="supported_benchmark",
                label_template="Use a national, state, or peer-group benchmark",
            ),
            OptionTemplate(option_id="cancel", label_template="Cancel"),
        ],
    ),
}

# Define the slots for the clarification template for temporal
ClarificationSlots = Annotated[
    Union[
        TemporalExplicitVsRollingSlots,
        TemporalAmbiguousGenericSlots,
    ],
    Field(discriminator="reason_code"),
]


# Define the slots for the clarification template for benchmark
BenchmarkClarificationSlots = Annotated[
    Union[
        BenchmarkAmbiguousTargetSlots,
        BenchmarkMissingMetricSlots,
        BenchmarkMissingGeoLevelSlots,
        BenchmarkConflictBaselineVsPeerGroupSlots,
        BenchmarkBaselineDeferredSlots,
    ],
    Field(discriminator="reason_code"),
]


def render_temporal_clarification(slots: ClarificationSlots) -> ClarificationPrompt:
    """Render a clarification prompt based on the reason code and slots.

    Args:
        reason_code: The reason code for the clarification template.
        slots: The slots for the clarification template.

    Returns:
        A ClarificationPrompt object.
    """
    template = TEMPLATES[slots.reason_code]
    slot_data = slots.model_dump()

    question_text = template.question_template.format(**slot_data)
    options = [
        ClarificationOption(
            option_id=option.option_id,
            label=option.label_template.format(**slot_data),
        )
        for option in template.option_templates
    ]

    return ClarificationPrompt(
        template_id=template.template_id,
        reason_code=template.reason_code,
        question_text=question_text,
        options=options,
        expected_response_shape="single_select",
    )


def render_benchmark_clarification(
    slots: BenchmarkClarificationSlots,
) -> BenchmarkClarificationPrompt:
    """Render a benchmark clarification prompt based on the reason code and slots.

    Args:
        reason_code: The reason code for the benchmark clarification template.
        slots: The slots for the benchmark clarification template.

    Returns:
        A BenchmarkClarificationPrompt object.
    """
    template = TEMPLATES[slots.reason_code]
    slot_data = slots.model_dump()

    question_text = template.question_template.format(**slot_data)
    options = [
        BenchmarkClarificationOption(
            option_id=option.option_id,
            label=option.label_template.format(**slot_data),
        )
        for option in template.option_templates
    ]
    return BenchmarkClarificationPrompt(
        template_id=template.template_id,
        reason_code=slots.reason_code,
        question_text=question_text,
        options=options,
        expected_response_shape="single_select",
    )

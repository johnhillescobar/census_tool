from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field

from src.domain.benchmark_contract import (
    BenchmarkClarificationOption,
    BenchmarkClarificationPrompt,
)
from src.domain.geography_contract import (
    ClarificationOption as GeographyClarificationOption,
)
from src.domain.geography_contract import (
    ClarificationPrompt as GeographyClarificationPrompt,
)
from src.domain.temporal_contract import ClarificationOption, ClarificationPrompt


# Define the slots for the temporal clarification template
class TemporalExplicitVsRollingSlots(BaseModel):
    """Slots for the temporal explicit vs rolling clarification template."""

    reason_code: Literal["TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING"] = "TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING"
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
    reason_code: Literal["BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP"] = "BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP"
    subject_text: str


class BenchmarkMissingBaselineAnchorSlots(BaseModel):
    reason_code: Literal["BENCHMARK_MISSING_BASELINE_ANCHOR"] = "BENCHMARK_MISSING_BASELINE_ANCHOR"
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


GeographyClarificationReason = Literal[
    "GEOGRAPHY_AMBIGUOUS",
    "GEOGRAPHY_NOT_FOUND",
    "GEOGRAPHY_UNSUPPORTED_DATASET",
    "GEOGRAPHY_INDEX_UNAVAILABLE",
    "GEOGRAPHY_INDEX_STALE",
    "GEOGRAPHY_PARTITION_MISSING",
    "GEOGRAPHY_INCOMPATIBLE",
]

TableClarificationReason = Literal[
    "TABLE_AMBIGUOUS",
    "TABLE_NOT_FOUND",
    "TABLE_INDEX_UNAVAILABLE",
    "TABLE_INDEX_STALE",
    "TABLE_SCHEMA_MISMATCH",
]

GEOGRAPHY_REASON_TEMPLATES: dict[GeographyClarificationReason, tuple[str, str]] = {
    "GEOGRAPHY_AMBIGUOUS": (
        "geography.ambiguous.v1",
        "I found multiple official Census geography records. Choose one:",
    ),
    "GEOGRAPHY_NOT_FOUND": (
        "geography.not_found.v1",
        "I could not find an official Census geography matching that request. Please provide a more specific name.",
    ),
    "GEOGRAPHY_UNSUPPORTED_DATASET": (
        "geography.unsupported_dataset.v1",
        "That geography is not supported by the selected Census dataset. Please choose a supported geography.",
    ),
    "GEOGRAPHY_INDEX_UNAVAILABLE": (
        "geography.index_unavailable.v1",
        "The official Census geography index is unavailable. Please try again later or cancel.",
    ),
    "GEOGRAPHY_INDEX_STALE": (
        "geography.index_stale.v1",
        "The official Census geography index is stale for this request. Please try another year or cancel.",
    ),
    "GEOGRAPHY_PARTITION_MISSING": (
        "geography.partition_missing.v1",
        "The requested Census dataset/year geography partition is missing. Please choose another year or dataset.",
    ),
    "GEOGRAPHY_INCOMPATIBLE": (
        "geography.incompatible.v1",
        "That official geography record is incompatible with the selected Census table and year.",
    ),
}

TABLE_REASON_TEMPLATES: dict[TableClarificationReason, tuple[str, str]] = {
    "TABLE_AMBIGUOUS": (
        "table.ambiguous.v1",
        "I found multiple Census tables that match that request. Choose one:",
    ),
    "TABLE_NOT_FOUND": (
        "table.not_found.v1",
        "I could not find a Census table matching that request. Please rephrase the statistic you need.",
    ),
    "TABLE_INDEX_UNAVAILABLE": (
        "table.index_unavailable.v1",
        "The Census table index is unavailable. Please try again later or cancel.",
    ),
    "TABLE_INDEX_STALE": (
        "table.index_stale.v1",
        "The Census table index is stale for this request. Please try another year or cancel.",
    ),
    "TABLE_SCHEMA_MISMATCH": (
        "table.schema_mismatch.v1",
        "The Census table index metadata is invalid for this request. Rebuild the table catalog or cancel.",
    ),
}


def normalize_geography_reason(reason_code: str) -> GeographyClarificationReason:
    normalized = reason_code.upper()
    if normalized in GEOGRAPHY_REASON_TEMPLATES:
        return cast(GeographyClarificationReason, normalized)
    if "AMBIGUOUS" in normalized:
        return "GEOGRAPHY_AMBIGUOUS"
    if "UNAVAILABLE" in normalized:
        return "GEOGRAPHY_INDEX_UNAVAILABLE"
    if "STALE" in normalized:
        return "GEOGRAPHY_INDEX_STALE"
    if "PARTITION" in normalized or "MISSING_EXPLICIT" in normalized:
        return "GEOGRAPHY_PARTITION_MISSING"
    if "UNSUPPORTED" in normalized:
        return "GEOGRAPHY_UNSUPPORTED_DATASET"
    if "INCOMPATIBLE" in normalized or "VALIDATION" in normalized:
        return "GEOGRAPHY_INCOMPATIBLE"
    return "GEOGRAPHY_NOT_FOUND"


def normalize_table_reason(reason_code: str) -> TableClarificationReason:
    normalized = reason_code.upper()
    if normalized in TABLE_REASON_TEMPLATES:
        return cast(TableClarificationReason, normalized)
    if "SCHEMA" in normalized:
        return "TABLE_SCHEMA_MISMATCH"
    if "AMBIGUOUS" in normalized:
        return "TABLE_AMBIGUOUS"
    if "UNAVAILABLE" in normalized:
        return "TABLE_INDEX_UNAVAILABLE"
    if "STALE" in normalized:
        return "TABLE_INDEX_STALE"
    return "TABLE_NOT_FOUND"


def render_geography_clarification(
    reason_code: str,
    options: list[GeographyClarificationOption],
) -> GeographyClarificationPrompt:
    """Render a stable geography prompt without inventing candidate labels."""
    normalized = normalize_geography_reason(reason_code)
    template_id, question = GEOGRAPHY_REASON_TEMPLATES[normalized]
    return GeographyClarificationPrompt(
        template_id=template_id,
        reason_code=normalized,
        question_text=question,
        options=[*options, GeographyClarificationOption(option_id="cancel", label="Cancel")],
    )


def render_table_clarification(
    reason_code: str,
    options: list[GeographyClarificationOption],
) -> GeographyClarificationPrompt:
    """Render a stable table-selection prompt (same prompt shape as geography)."""
    normalized = normalize_table_reason(reason_code)
    template_id, question = TABLE_REASON_TEMPLATES[normalized]
    return GeographyClarificationPrompt(
        template_id=template_id,
        reason_code=normalized,
        question_text=question,
        options=[*options, GeographyClarificationOption(option_id="cancel", label="Cancel")],
    )


def render_slot_clarification(
    reason_code: str,
    options: list[GeographyClarificationOption],
    *,
    requested_slot: str,
) -> GeographyClarificationPrompt:
    """Dispatch clarification copy by pending slot (table vs geography)."""
    if requested_slot == "table":
        return render_table_clarification(reason_code, options)
    return render_geography_clarification(reason_code, options)


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
            OptionTemplate(option_id="explicit_years", label_template="Use explicit years only"),
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
            "I found a missing metric in your request. Please choose one so I can run the query deterministically."
        ),
        option_templates=[
            OptionTemplate(option_id="population", label_template="Population {metric}"),
            OptionTemplate(
                option_id="median_income",
                label_template="Median household income {metric}",
            ),
            OptionTemplate(option_id="poverty_rate", label_template="Poverty rate {metric}"),
            OptionTemplate(option_id="unemployment", label_template="Unemployment {metric}"),
            OptionTemplate(option_id="education", label_template="Education {metric}"),
            OptionTemplate(option_id="hispanic", label_template="Hispanic {metric}"),
            OptionTemplate(option_id="race", label_template="Race {metric}"),
            OptionTemplate(option_id="ethnicity", label_template="Ethnicity {metric}"),
            OptionTemplate(option_id="housing", label_template="Housing {metric}"),
            OptionTemplate(option_id="rent", label_template="Rent {metric}"),
            OptionTemplate(option_id="mortgage", label_template="Mortgage {metric}"),
            OptionTemplate(option_id="labor_force", label_template="Labor force {metric}"),
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
    "BENCHMARK_MISSING_BASELINE_ANCHOR": ClarificationTemplate(
        template_id="benchmark.missing_baseline_anchor.v1",
        reason_code="BENCHMARK_MISSING_BASELINE_ANCHOR",
        question_template=(
            "Your request references a historical baseline but does not specify an anchor year."
            " Please choose one so I can run the query deterministically."
        ),
        option_templates=[
            OptionTemplate(
                option_id="baseline_anchor_year",
                label_template="Specify a baseline anchor year",
            ),
            OptionTemplate(option_id="cancel", label_template="Cancel"),
        ],
    ),
}

# Define the slots for the clarification template for temporal
ClarificationSlots = Annotated[
    TemporalExplicitVsRollingSlots | TemporalAmbiguousGenericSlots,
    Field(discriminator="reason_code"),
]


# Define the slots for the clarification template for benchmark
BenchmarkClarificationSlots = Annotated[
    BenchmarkAmbiguousTargetSlots
    | BenchmarkMissingMetricSlots
    | BenchmarkMissingGeoLevelSlots
    | BenchmarkConflictBaselineVsPeerGroupSlots
    | BenchmarkMissingBaselineAnchorSlots,
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

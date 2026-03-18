from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, model_validator

# Create enums for the benchmark type, comparison operator, and normalization mode.
BenchmarkType = Literal[
    "national",
    "state",
    "peer_group",
    "custom_set",
    "historical_baseline",
]

ComparisonOp = Literal[
    "difference",
    "pct_difference",
    "rank",
    "percentile",
    "trend_gap",
]

NormalizationMode = Literal[
    "none",
    "per_capita",
    "index_base_100",
]

GeographyLevel = Literal[
    "nation",
    "state",
    "county",
    "place",
    "cbsa",
    "metro_division",
]

BenchmarkClarificationReason = Literal[
    "BENCHMARK_AMBIGUOUS_TARGET",
    "BENCHMARK_MISSING_METRIC",
    "BENCHMARK_MISSING_GEO_LEVEL",
    "BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP",
]


# Create the BenchmarkIntent model and add validation for the fields.
class BenchmarkIntent(BaseModel):
    benchmark_type: BenchmarkType
    subject_geo_level: GeographyLevel = Field(
        ..., description="The level of the subject geography."
    )
    subject_geo: list[str] = Field(
        default_factory=list, description="The list of subject geographies."
    )
    benchmark_geo_level: GeographyLevel | None = Field(
        default=None, description="The level of the benchmark geography."
    )
    benchmark_geos: list[str] = Field(
        default_factory=list, description="The list of benchmark geographies."
    )
    metric: str = Field(..., description="The metric to compare.")
    comparison_op: ComparisonOp = Field(
        default="difference", description="The comparison operator."
    )
    normalization: NormalizationMode = Field(
        default="none", description="The normalization mode."
    )
    requested_text: str | None = Field(
        None, description="The text that the user requested."
    )

    @model_validator(mode="after")
    def validate_fields(self) -> "BenchmarkIntent":
        """Validate BenchmarkIntent fields with deterministic fail-closed rules."""

        # Phase 1: Independent base checks
        if not self.metric or not self.metric.strip():
            raise ValueError("Metric is required and cannot be empty.")

        if not self.subject_geo:
            raise ValueError("subject_geo must include at least one geography.")

        # Phase 2: Benchmark type-specific checks
        if self.benchmark_type == "national":
            # National may omit benchmark_geos, but if provided, must be ['us:1']
            if self.benchmark_geos and self.benchmark_geos != ["us:1"]:
                raise ValueError(
                    "national benchmark must use benchmark_geos ['us:1'] or leave empty."
                )

            if self.benchmark_geo_level not in (None, "nation"):
                raise ValueError(
                    "national benchmark must use benchmark_geo_level 'nation' or leave empty."
                )

        elif self.benchmark_type == "state":
            # State benchmark requires benchmark_geos and benchmark_geo_level must be 'state'
            if not self.benchmark_geos:
                raise ValueError(
                    "state benchmark_type requires at least one benchmark geography."
                )

            if self.benchmark_geo_level != "state":
                raise ValueError(
                    "state benchmark must use benchmark_geo_level 'state'."
                )

        elif self.benchmark_type == "peer_group":
            if len(self.benchmark_geos) < 2:
                raise ValueError(
                    "peer_group benchmark_type requires at least two benchmark geographies."
                )

            if self.benchmark_geo_level is None:
                raise ValueError(
                    "peer_group benchmark must use a benchmark_geo_level other than None."
                )

        elif self.benchmark_type == "custom_set":
            if not self.benchmark_geos:
                raise ValueError(
                    "custom_set benchmark_type requires benchmark geographies."
                )

            if self.benchmark_geo_level is None:
                raise ValueError(
                    "custom_set benchmark must use a benchmark_geo_level other than None."
                )

        elif self.benchmark_type == "historical_baseline":
            # baseline comparison against prior period/anchor; geography may be present
            pass

        return self


class BenchmarkClarificationOption(BaseModel):
    option_id: str
    label: str


class BenchmarkClarificationPrompt(BaseModel):
    template_id: str
    reason_code: BenchmarkClarificationReason
    question_text: str
    options: list[BenchmarkClarificationOption]
    expected_response_shape: Literal["single_select"] = Field(
        default="single_select", description="The shape of the expected response."
    )


class BenchmarkResolved(BaseModel):
    status: Literal["resolved"] = Field(
        default="resolved", description="The status of the benchmark resolved."
    )
    benchmark: BenchmarkIntent = Field(
        ..., description="The benchmark intent that was resolved."
    )


class BenchmarkClarificationRequired(BaseModel):
    status: Literal["clarification_required"] = Field(
        default="clarification_required",
        description="The status of the benchmark clarification required.",
    )
    reason_code: BenchmarkClarificationReason = Field(
        ..., description="The reason code for the benchmark clarification required."
    )
    clarification_prompt: BenchmarkClarificationPrompt = Field(
        ...,
        description="The clarification prompt for the benchmark clarification required.",
    )


BenchmarkResolution = Annotated[
    Union[BenchmarkResolved, BenchmarkClarificationRequired],
    Field(discriminator="status"),
]

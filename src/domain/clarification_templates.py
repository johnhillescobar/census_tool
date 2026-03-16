from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field
from src.domain.temporal_contract import ClarificationPrompt, ClarificationOption


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
}

# Define the slots for the clarification template
ClarificationSlots = Annotated[
    Union[
        TemporalExplicitVsRollingSlots,
        TemporalAmbiguousGenericSlots,
    ],
    Field(discriminator="reason_code"),
]


def render_clarification(slots: ClarificationSlots) -> ClarificationPrompt:
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

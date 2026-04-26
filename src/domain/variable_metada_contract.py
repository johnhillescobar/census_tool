from pydantic import BaseModel, ConfigDict, Field


class VariableLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from Census variable code to human-readable label.",
    )

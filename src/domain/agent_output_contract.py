from pydantic import BaseModel, ConfigDict, Field

from src.domain.census_tool_contract import StrictCensusApiResponse
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.variable_metada_contract import VariableLabels


class AgentSolveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Canonical payload comes from strict_census_api_call observations (agent merge), not LLM JSON alone.
    census_data: StrictCensusApiResponse = Field(
        ...,
        description="Validated Census API response attached by the agent from tool output",
    )
    variable_labels: VariableLabels = Field(
        default_factory=VariableLabels, description="The variable labels of the data"
    )
    data_summary: str = Field(..., description="A brief summary of the data retrieved")
    reasoning_trace: str = Field(..., description="The reasoning trace of the agent")
    answer_text: str = Field(..., description="The answer text of the agent")
    charts_needed: list[FinalChartSpec] = Field(
        default_factory=list, description="The charts needed for the data"
    )
    tables_needed: list[FinalTableSpec] = Field(
        default_factory=list, description="The tables needed for the data"
    )
    footnotes: list[str] = Field(
        default_factory=list, description="The footnotes of the data"
    )

from pydantic import BaseModel, ConfigDict, Field

from src.domain.census_tool_contract import StrictCensusApiResponse
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.variable_metada_contract import VariableLabels


class AgentSolveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_data: StrictCensusApiResponse | None = (
        None  # TODO: make this required once we have a way to handle the legacy census_data
    )
    variable_labels: VariableLabels = Field(default_factory=VariableLabels)
    data_summary: str = ""
    reasoning_trace: str = ""
    answer_text: str = ""
    charts_needed: list[FinalChartSpec] = Field(default_factory=list)
    tables_needed: list[FinalTableSpec] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)

import pytest

pytest.importorskip("langchain_core.tools")

from src.domain.census_tool_contract import StrictCensusApiRawTable
from src.tools.chart_tool import ChartTool, ChartToolInput


def test_chart_render_requires_chart_tool_input(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tool = ChartTool()
    tbl = StrictCensusApiRawTable(headers=["NAME", "V"], rows=[["A", "1"]])
    typed = ChartToolInput(
        chart_type="bar",
        x_column="NAME",
        y_column="V",
        title="T",
        data=tbl,
    )
    bad = typed.model_dump()
    with pytest.raises(TypeError, match="ChartTool.render"):
        tool.render(bad)


def test_chart_render_succeeds_with_typed_instance(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tool = ChartTool()
    tbl = StrictCensusApiRawTable(headers=["NAME", "V"], rows=[["A", "1"], ["B", "2"]])
    out = tool.render(
        ChartToolInput(
            chart_type="bar",
            x_column="NAME",
            y_column="V",
            title="T",
            data=tbl,
        )
    )
    assert ".png" in out.path or out.mime_type == "text/html"


from unittest.mock import patch

from src.domain.temporal_contract import TemporalIntent, TemporalResolved
from src.services.agent_plan_context import build_agent_planning_context
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.agent_planning import agent_planning_node


def _temporal_plan() -> WorkflowPlan:
    return WorkflowPlan(
        temporal=TemporalResolved(
            time=TemporalIntent(
                mode="point_in_time",
                anchor_year=2023,
                requested_text="population in California",
            )
        ),
        requires_clarification=False,
    )


def test_build_agent_planning_context_returns_temporal_only():
    context = build_agent_planning_context(_temporal_plan())
    assert context is not None
    assert context.temporal is not None
    assert context.temporal.anchor_year == 2023
    assert context.geography is None
    assert context.has_comparison_plan is False


def test_build_agent_planning_context_returns_none_when_clarification_required():
    plan = _temporal_plan().model_copy(update={"requires_clarification": True})
    assert build_agent_planning_context(plan) is None


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_agent_planning_node_runs_retrieval_turn(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Planning tool steps: 2 (table_search, geography_discovery)",
        "data_summary": "Found population tables for 2023.",
        "answer_text": "Recommend B01003 for total population.",
        "intermediate_steps": [],
    }
    state = CensusState(
        messages=[{"role": "user", "content": "population of California in 2023"}],
        plan=_temporal_plan(),
    )

    result = agent_planning_node(state, config={})

    mock_agent_cls.assert_called_once_with(mode="planning")
    _, kwargs = mock_agent_cls.return_value.solve.call_args
    assert kwargs["plan_context"] is not None
    assert kwargs["plan_context"].temporal.anchor_year == 2023
    assert result["logs"] == ["agent_planning: completed retrieval planning turn"]
    assert result["artifacts"]["planning_trace"].startswith("Planning tool steps")


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_agent_planning_node_logs_skipped_when_offline(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = True
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Agent planning skipped because OPENAI_API_KEY is not configured",
        "data_summary": "Planning turn offline",
        "answer_text": "Planning turn skipped (no LLM credentials).",
    }
    state = CensusState(
        messages=[{"role": "user", "content": "population of California in 2023"}],
        plan=_temporal_plan(),
    )

    result = agent_planning_node(state, config={})

    assert result["logs"] == ["agent_planning: skipped (no LLM credentials)"]


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_agent_planning_node_skips_when_upstream_clarification_required(mock_agent_cls):
    state = CensusState(
        messages=[{"role": "user", "content": "compare 2019 vs 2023 over the last 5 years"}],
        plan=WorkflowPlan(requires_clarification=True),
    )

    result = agent_planning_node(state, config={})

    mock_agent_cls.assert_not_called()
    assert result["logs"] == ["agent_planning: skipped (clarification required)"]

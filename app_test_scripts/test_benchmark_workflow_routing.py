from src.domain.temporal_contract import TemporalIntent, TemporalResolved
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.benchmark import benchmark_node


def test_benchmark_node_routes_named_state_compare_to_agent_path():
    state = CensusState(
        messages=[
            {
                "role": "user",
                "content": "Compare California vs Texas population in 2020",
            }
        ],
        plan=WorkflowPlan(
            temporal=TemporalResolved(
                time=TemporalIntent(
                    mode="point_in_time",
                    anchor_year=2020,
                    missing_year_policy="skip_with_note",
                    requested_text="Compare California vs Texas population in 2020",
                )
            ),
            requires_clarification=False,
        ),
    )

    result = benchmark_node(state, {})
    plan = result["plan"]

    assert plan.requires_clarification is False
    assert plan.benchmark.status == "resolved"
    assert plan.benchmark.benchmark.benchmark_type == "custom_set"

from src.domain.comparison_artifacts import ComparisonMetricArtifactRow
from src.domain.strict_json import ConversationMessage, JsonMap, merge_json_maps
from src.state.types import FinalResponseState, WorkflowArtifactsState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch


def test_json_map_normalizes_nested_values_and_merges() -> None:
    existing = JsonMap.model_validate({"a": 1, "nested": {"x": True}})
    patch = JsonMap.model_validate({"nested": {"y": "yes"}, "items": [1, None]})

    merged = merge_json_maps(existing, patch)

    assert merged.root == {"a": 1, "nested": {"y": "yes"}, "items": [1, None]}


def test_conversation_message_accepts_legacy_dict_shape() -> None:
    msg = ConversationMessage.model_validate({"type": "human", "content": 123})

    assert msg.role == "human"
    assert msg.content == "123"


def test_graph_patch_projects_typed_final_and_artifacts_to_langgraph_update() -> None:
    metric = ComparisonMetricArtifactRow(
        year=2023,
        geo_id="06037",
        metric="population",
        derived_metric="difference",
        value=2.0,
        subject_value=10.0,
        benchmark_value=8.0,
    )

    update = CensusGraphPatch(
        plan=WorkflowPlan(requires_clarification=False),
        final=FinalResponseState(answer_text="Done"),
        artifacts=WorkflowArtifactsState(comparison_metrics=[metric]),
        logs=["ok"],
    ).as_langgraph_update()

    assert isinstance(update["plan"], WorkflowPlan)
    assert update["final"] == {
        "answer_text": "Done",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": [],
        "generated_files": [],
    }
    assert update["artifacts"]["comparison_metrics"][0]["value"] == 2.0
    assert update["logs"] == ["ok"]

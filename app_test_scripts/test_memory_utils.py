"""
Tests for typed memory helpers (Track 2E).
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


from src.domain.strict_json import ConversationMessage, JsonMap
from src.services.memory_utils import (
    build_history_record,
    update_profile,
    prune_history_by_age,
    prune_cache_by_age,
    enforce_retention_policies,
)
from src.state.types import FinalResponseState, WorkflowPlanState


def test_build_history_record():
    messages = [
        ConversationMessage(role="user", content="Population of NYC?"),
    ]
    final = FinalResponseState(answer_text="about 8.4m")
    intent = JsonMap.model_validate({"type": "population_query", "location": "NYC"})
    geo = JsonMap.model_validate({"level": "place", "name": "New York City"})
    plan = WorkflowPlanState(
        temporal=None,
        benchmark=None,
        comparison=None,
        requires_clarification=False,
    )

    rec = build_history_record(
        messages,
        final,
        intent,
        geo,
        plan,
        user_id="u1",
        workflow_error=None,
    )

    assert isinstance(rec, JsonMap)
    assert rec.root["question"] == "Population of NYC?"
    assert rec.root["user_id"] == "u1"
    assert rec.root["intent"] == intent.root
    assert rec.root["geo"] == geo.root
    assert rec.root["answer_type"] == "text"
    assert rec.root["success"] is True


def test_update_profile():
    profile = JsonMap.model_validate({})
    intent = JsonMap.model_validate(
        {
            "type": "population_query",
            "dataset": "population",
            "measures": ["population"],
        }
    )
    geo = JsonMap.model_validate(
        {"level": "place", "name": "New York City", "display_name": "NYC"}
    )
    final = FinalResponseState(answer_text="value B01003_001E")

    out = update_profile(
        profile, intent, geo, final, workflow_error=None
    )
    assert isinstance(out, JsonMap)
    assert out.root["last_geo"] == "NYC"
    assert out.root["preferred_dataset"] == "population"
    alias = out.root["var_aliases"]
    assert isinstance(alias, dict)


def test_prune_history_by_age():
    now = datetime.now()
    old_date = (now - timedelta(days=10)).isoformat()
    new_date = (now - timedelta(days=3)).isoformat()

    history = [
        {"timestamp": old_date, "question": "Old", "user_id": "a"},
        {"timestamp": new_date, "question": "New", "user_id": "b"},
        {"timestamp": now.isoformat(), "question": "Curr", "user_id": "c"},
    ]
    result = prune_history_by_age(history, 5)
    assert len(result) == 2
    assert result[0].root["question"] == "New"


def test_prune_cache_by_age_accepts_plain_dict():
    """LangGraph/SQLite can hand back bare dict envelopes; do not require .root."""
    now = datetime.now().isoformat()
    raw = {"sig_a": {"timestamp": now, "file_path": None}}
    out = prune_cache_by_age(raw, 9999)
    assert isinstance(out, JsonMap)
    assert "sig_a" in out.root


def test_update_profile_accepts_plain_dict_profile():
    out = update_profile(
        {},
        JsonMap.model_validate({"dataset": "population"}),
        JsonMap.model_validate(
            {"level": "place", "name": "NYC", "display_name": "NYC"}
        ),
        FinalResponseState(answer_text="ok"),
        workflow_error=None,
    )
    assert isinstance(out, JsonMap)
    assert out.root.get("preferred_dataset") == "population"


def test_enforce_retention_policies():
    test_profile = {
        "user_id": "test_user",
        "schema_version": 2,
        "default_geo": {},
        "preferred_dataset": "acs/acs5",
        "default_year_range": [2012, 2023],
        "preferred_level": "place",
        "var_aliases": {},
        "history": [
            {
                "timestamp": (datetime.now() - timedelta(days=10)).isoformat(),
                "question": "Old",
            },
            {
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                "question": "New",
            },
        ],
    }

    cache_meta_new = JsonMap.model_validate(
        {
            "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
            "file_path": "/tmp/new.csv",
        }
    )

    with (
        patch("src.services.memory_utils.load_json_file") as mock_load,
        patch("src.services.memory_utils.save_json_file") as mock_save,
        patch("src.services.memory_utils.prune_cache_by_age") as mock_prune_cache,
        patch(
            "src.services.memory_utils.prune_history_by_age",
            side_effect=lambda h, _: h[-1:],  # keep newest only
        ) as _mock_ph,
    ):
        mock_load.side_effect = [
            test_profile,
            {},  # raw cache migrated from empty envelope
        ]
        mock_prune_cache.return_value = JsonMap.model_validate(
            {"cache2": cache_meta_new.model_dump(mode="python")}
        )

        profile_file = Path("/tmp/test_profile.json")
        cache_file = Path("/tmp/test_cache.json")
        enforce_retention_policies(profile_file, cache_file, "test_user")

        assert mock_load.call_count == 2
        assert mock_save.call_count >= 1

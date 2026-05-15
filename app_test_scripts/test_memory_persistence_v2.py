from src.domain.memory_persistence_contract import (
    CacheIndexFileV2,
    UserMemoryFileV2,
    migrate_cache_index_file,
    migrate_user_memory_file,
)
from src.domain.strict_json import JsonMap


def test_migrate_legacy_profile_blob_to_v2():
    legacy = {
        "user_id": "u1",
        "default_geo": {"k": "v"},
        "history": [{"timestamp": "2024-01-01", "question": "q"}],
        "junk_extra_will_drop": True,
    }
    doc = migrate_user_memory_file(legacy, fallback_user_id="fallback")
    assert doc.schema_version == 2
    assert doc.user_id == "u1"
    dumped = doc.model_dump()
    assert dumped["schema_version"] == 2
    assert "junk_extra_will_drop" not in dumped


def test_roundtrip_v2_profile():
    d = {"schema_version": 2, "user_id": "u2", "history": [], "preferred_dataset": "acs/acs3"}
    doc = migrate_user_memory_file(d, fallback_user_id="fallback")
    assert isinstance(doc, UserMemoryFileV2)


def test_migrate_flat_cache_legacy_to_envelope_roundtrip():
    flat = {"sig_a": {"timestamp": "2030-01-01", "file_path": None}}
    expected_entries = JsonMap.model_validate(flat)
    doc = migrate_cache_index_file(flat)
    assert isinstance(doc, CacheIndexFileV2)
    assert doc.entries.root == expected_entries.root
    dumped = doc.model_dump()
    assert dumped["schema_version"] == 2
    round_doc = migrate_cache_index_file(dict(dumped))
    assert round_doc.entries.root == expected_entries.root


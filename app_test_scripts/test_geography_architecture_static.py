"""Static release guards for the grounded geography architecture."""

from __future__ import annotations

import ast
from pathlib import Path

from app_test_scripts.census_url_fixtures import load_golden_questions

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_RUNTIME_DIRS = (ROOT / "src" / "workflows", ROOT / "src" / "tools")


def _python_sources(paths: tuple[Path, ...]) -> list[Path]:
    return [source for path in paths for source in path.glob("*.py")]


def test_grounded_geography_has_no_feature_flag_or_legacy_node():
    source = (ROOT / "src" / "workflows" / "geography.py").read_text(encoding="utf-8")
    config_source = (ROOT / "config.py").read_text(encoding="utf-8")
    assert "CENSUS_CHROMA_GROUNDED_PLANNING" not in source
    assert "_legacy_geography_node" not in source
    assert "geography_policy" not in source
    assert "GEOGRAPHY_MAPPINGS" not in config_source
    assert "DEFAULT_GEO" not in config_source


def test_active_workflows_and_tools_do_not_use_legacy_mappings_or_implicit_us_default():
    for path in _python_sources(ACTIVE_RUNTIME_DIRS):
        source = path.read_text(encoding="utf-8")
        assert "GEOGRAPHY_MAPPINGS" not in source, path
        assert "missing_geo_default" not in source, path


def test_active_runtime_does_not_import_retired_geography_modules():
    retired_modules = {
        "src.domain.geo_utils",
        "src.llm.geography_resolver",
        "src.services.geography_policy",
    }
    active_sources = _python_sources((*ACTIVE_RUNTIME_DIRS, ROOT / "src" / "agents"))
    for path in active_sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        assert imports.isdisjoint(retired_modules), path


def test_graph_is_temporal_first_and_golden_acceptance_has_124_questions():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'return "temporal"' in source
    assert '{"geography": "geography", "output": "output"}' in source
    assert len(load_golden_questions()) == 124

from src.tools.table_search_tool import TableSearchTool


def test_table_search_tool_returns_client_error(monkeypatch):
    monkeypatch.setattr(
        "src.tools.table_search_tool.initialize_chroma_client",
        lambda: {"error": "Failed to connect to variable database: offline", "logs": []},
    )

    result = TableSearchTool()._run("median income")
    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to connect" in result["error"]


def test_table_search_tool_returns_collection_error(monkeypatch):
    class DummyClient:
        pass

    monkeypatch.setattr(
        "src.tools.table_search_tool.initialize_chroma_client",
        lambda: DummyClient(),
    )
    monkeypatch.setattr(
        "src.tools.table_search_tool.get_chroma_collection_tables",
        lambda client: {"error": "Failed to get Chroma collection: missing", "logs": []},
    )

    result = TableSearchTool()._run("population")
    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to get Chroma collection" in result["error"]

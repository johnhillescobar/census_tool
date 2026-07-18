"""FastAPI endpoint smoke tests."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.fastapi_app import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_query_endpoint_returns_thread_and_result():
    mock_graph = MagicMock()
    mock_graph.get_state.return_value = MagicMock(values={})
    mock_graph.invoke.return_value = {"final": {"answer_text": "stub answer"}}

    with patch("src.api.fastapi_app.get_graph", return_value=mock_graph):
        client = TestClient(app)
        response = client.post(
            "/query",
            json={"user_id": "demo", "question": "population of california", "new_thread": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"]
    assert body["result"]["final"]["answer_text"] == "stub answer"


def test_query_stream_emits_started_and_completed_events():
    mock_graph = MagicMock()
    mock_graph.get_state.return_value = MagicMock(values={})
    mock_graph.invoke.return_value = {"final": {"answer_text": "stream stub"}}

    with patch("src.api.fastapi_app.get_graph", return_value=mock_graph):
        client = TestClient(app)
        response = client.post(
            "/query/stream",
            json={"user_id": "demo", "question": "population trend", "new_thread": True},
        )

    assert response.status_code == 200
    text = response.text
    assert "event: started" in text
    assert "event: completed" in text
    assert "stream stub" in text


def test_new_thread_ignores_provided_thread_id():
    provided = "00000000-0000-0000-0000-000000000001"
    mock_graph = MagicMock()
    mock_graph.get_state.return_value = MagicMock(values={})
    mock_graph.invoke.return_value = {"final": {"answer_text": "stub answer"}}

    with patch("src.api.fastapi_app.get_graph", return_value=mock_graph):
        client = TestClient(app)
        response = client.post(
            "/query",
            json={
                "user_id": "demo",
                "thread_id": provided,
                "question": "population of california",
                "new_thread": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["thread_id"] != provided

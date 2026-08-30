import json

from fastapi.testclient import TestClient

from app.main import app


def signed_in_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    client = TestClient(app)
    assert client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    ).status_code == 200
    return client


def test_chat_persists_turn_and_sends_bounded_context(tmp_path, monkeypatch) -> None:
    client = signed_in_client(tmp_path, monkeypatch)
    captured: list[dict[str, object]] = []

    def complete(messages):
        captured.append({"messages": messages})
        return json.dumps({"reply": "I found the board.", "board": None})

    monkeypatch.setattr("app.main.openrouter_client.complete", complete)

    response = client.post("/api/chat", json={"message": "What is on the board?"})

    assert response.status_code == 200
    assert response.json()["message"]["content"] == "I found the board."
    assert len(captured[0]["messages"]) == 3
    assert client.get("/api/chat").json()[0]["role"] == "user"


def test_chat_applies_valid_board_update(tmp_path, monkeypatch) -> None:
    client = signed_in_client(tmp_path, monkeypatch)
    board = client.get("/api/board").json()
    board["columns"][0]["title"] = "Queue"
    monkeypatch.setattr(
        "app.main.openrouter_client.complete",
        lambda messages: json.dumps({"reply": "Renamed it.", "board": board}),
    )

    response = client.post("/api/chat", json={"message": "Rename backlog to queue"})

    assert response.status_code == 200
    assert client.get("/api/board").json()["columns"][0]["title"] == "Queue"
    assert response.json()["message"]["board_updated"] is True


def test_chat_rejects_invalid_provider_board_without_writing_messages(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    ).status_code == 200
    monkeypatch.setattr(
        "app.main.openrouter_client.complete",
        lambda messages: '{"reply":"Broken", "board":{"columns":[],"cards":{}}}',
    )

    response = client.post("/api/chat", json={"message": "Break the board"})

    assert response.status_code == 502
    assert client.get("/api/chat").json() == []


def test_chat_requires_authentication(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))

    assert TestClient(app).get("/api/chat").status_code == 401


def test_chat_rejects_stale_board_instead_of_clobbering_concurrent_edit(tmp_path, monkeypatch) -> None:
    client = signed_in_client(tmp_path, monkeypatch)
    stale_board = client.get("/api/board").json()
    stale_board["columns"][0]["title"] = "Renamed by assistant"

    def complete(messages):
        # Simulate another request mutating the board while this reply was "in flight".
        concurrent_edit = client.patch("/api/board/columns/col-discovery", json={"title": "Edited concurrently"})
        assert concurrent_edit.status_code == 200
        return json.dumps({"reply": "Renamed it.", "board": stale_board})

    monkeypatch.setattr("app.main.openrouter_client.complete", complete)

    response = client.post("/api/chat", json={"message": "Rename backlog"})

    assert response.status_code == 409
    board = client.get("/api/board").json()
    assert board["columns"][1]["title"] == "Edited concurrently"
    assert board["columns"][0]["title"] != "Renamed by assistant"
    assert client.get("/api/chat").json() == []
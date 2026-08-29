from fastapi.testclient import TestClient

from app.main import app


def signed_in_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 200
    return client


def test_board_is_seeded_and_persisted(tmp_path, monkeypatch) -> None:
    client = signed_in_client(tmp_path, monkeypatch)

    response = client.get("/api/board")

    assert response.status_code == 200
    assert len(response.json()["columns"]) == 5
    assert response.json()["cards"]["card-1"]["title"] == "Align roadmap themes"
    assert (tmp_path / "app.db").exists()


def test_board_mutations_persist(tmp_path, monkeypatch) -> None:
    client = signed_in_client(tmp_path, monkeypatch)
    client.get("/api/board")

    rename = client.patch("/api/board/columns/col-backlog", json={"title": "Queue"})
    assert rename.status_code == 200
    created = client.post(
        "/api/board/cards",
        json={"column_id": "col-backlog", "title": "New work", "details": "Details"},
    )
    assert created.status_code == 200
    card_id = next(card_id for card_id in created.json()["cards"] if card_id.startswith("card-") and card_id not in {f"card-{number}" for number in range(1, 9)})

    edited = client.patch(
        f"/api/board/cards/{card_id}",
        json={"title": "Updated work", "details": "Updated details"},
    )
    assert edited.status_code == 200
    moved = client.post(
        "/api/board/move",
        json={"active_card_id": card_id, "over_id": "col-done"},
    )
    assert moved.status_code == 200
    assert card_id in next(column for column in moved.json()["columns"] if column["id"] == "col-done")["cardIds"]

    deleted = client.delete(f"/api/board/cards/{card_id}")
    assert deleted.status_code == 200
    persisted = client.get("/api/board").json()
    assert persisted["columns"][0]["title"] == "Queue"
    assert card_id not in persisted["cards"]


def test_board_rejects_invalid_references(tmp_path, monkeypatch) -> None:
    client = signed_in_client(tmp_path, monkeypatch)

    response = client.put(
        "/api/board",
        json={"columns": [{"id": "one", "title": "One", "cardIds": ["missing"]}], "cards": {}},
    )

    assert response.status_code == 422


def test_board_requires_authentication(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))

    response = TestClient(app).get("/api/board")

    assert response.status_code == 401
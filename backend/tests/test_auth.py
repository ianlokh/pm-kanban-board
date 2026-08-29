from fastapi.testclient import TestClient

from app.main import app


def test_login_sets_http_only_session_cookie(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    client = TestClient(app)

    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )

    assert response.status_code == 200
    assert response.json() == {"username": "user"}
    assert "pm_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == {"username": "user"}


def test_invalid_login_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    client = TestClient(app)

    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_logout_revokes_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    client = TestClient(app)
    client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_session_is_required_for_me(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))

    response = TestClient(app).get("/api/auth/me")

    assert response.status_code == 401

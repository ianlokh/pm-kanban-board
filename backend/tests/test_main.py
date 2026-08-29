from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_example_html() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Hello, world!" in response.text
    assert response.headers["content-type"].startswith("text/html")

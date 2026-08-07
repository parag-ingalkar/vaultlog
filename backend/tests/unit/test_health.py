from starlette.testclient import TestClient

from vaultlog.main import create_app


def test_health_check_returns_ok() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

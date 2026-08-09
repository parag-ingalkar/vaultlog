from __future__ import annotations

import uuid

from starlette.testclient import TestClient

from vaultlog.domain.identity.rate_limits import LOGIN_IP_CAPACITY
from vaultlog.main import create_app


def test_login_rate_limit_fires(client: TestClient) -> None:
    email = f"limit-{uuid.uuid4().hex[:12]}@example.com"
    payload = {"email": email, "password": "wrong password 12"}
    for _ in range(LOGIN_IP_CAPACITY):
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code in {401, 403, 503}
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 429
    assert "retry-after" in {header.lower() for header in response.headers}
    body = response.json()["error"]
    assert body["code"] == "http_429"
    assert body["request_id"]


def test_500_response_leaks_nothing() -> None:
    """Verify the catch-all handler on the real app stack returns a safe 500 body.

    raise_server_exceptions=False is required so TestClient returns the HTTP
    response instead of re-raising the exception inside the test process.
    That mirrors production: clients receive a 500 body, not a traceback.
    """
    app = create_app()

    @app.get("/api/v1/__test_unhandled_error")
    async def crash() -> None:
        raise RuntimeError("intentional test failure")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/__test_unhandled_error")

    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "internal_error"
    assert body["message"] == "An internal error occurred"
    assert "intentional test failure" not in response.text
    assert "Traceback" not in response.text
    assert 'File "' not in response.text
    assert "RuntimeError" not in response.text
    assert response.headers.get("X-Request-ID")
    assert body["request_id"] == response.headers.get("X-Request-ID")


def test_validation_error_omits_submitted_secret(client: TestClient) -> None:
    canary = "CANARY-SECRET-VALUE-7f3d"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": canary,
            "organization_name": "Acme",
        },
    )
    assert response.status_code == 422
    assert canary not in response.text
    body = response.json()["error"]
    assert body["code"] == "validation_failed"
    assert "fields" in body
    assert body["request_id"]


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert response.headers.get("Content-Security-Policy") == (
        "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers.get("X-Request-ID")


def test_foreign_origin_on_refresh_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "csrf_origin_mismatch"


def test_origin_less_refresh_allowed_without_csrf_block(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    body = response.json()["error"]
    assert body["code"] == "authentication_failed"

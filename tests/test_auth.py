"""JWT authentication tests — Task 1.1 sub-step 2."""

from __future__ import annotations

import pytest
from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError, create_access_token, decode_access_token
from app.main import create_app
from app.schemas.auth import TokenRequest
from app.services.auth_service import AuthService
from fastapi.testclient import TestClient

TEST_SECRET = "test-jwt-secret-at-least-32-characters-long"
TEST_CLIENT_ID = "test-widget"
TEST_CLIENT_SECRET = "test-client-secret-value"


@pytest.fixture
def auth_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("API_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("API_CLIENT_SECRET", TEST_CLIENT_SECRET)
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    return get_settings()


@pytest.fixture
def client(auth_settings: Settings) -> TestClient:
    get_settings.cache_clear()
    app = create_app()
    return TestClient(app)


def test_create_and_decode_token(auth_settings: Settings) -> None:
    token = create_access_token("user-42", auth_settings)
    payload = decode_access_token(token, auth_settings)
    assert payload.sub == "user-42"
    assert payload.token_type == "access"


def test_decode_invalid_token_raises(auth_settings: Settings) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-valid-token", auth_settings)


def test_auth_service_issues_token(auth_settings: Settings) -> None:
    service = AuthService(auth_settings)
    response = service.issue_token(
        TokenRequest(
            client_id=TEST_CLIENT_ID,
            client_secret=TEST_CLIENT_SECRET,
            subject="staff-101",
        )
    )
    assert response.token_type == "bearer"
    assert response.expires_in == 30 * 60
    payload = decode_access_token(response.access_token, auth_settings)
    assert payload.sub == "staff-101"


def test_auth_service_rejects_bad_credentials(auth_settings: Settings) -> None:
    service = AuthService(auth_settings)
    with pytest.raises(PermissionError):
        service.issue_token(
            TokenRequest(
                client_id=TEST_CLIENT_ID,
                client_secret="wrong",
                subject="staff-101",
            )
        )


def test_token_endpoint_returns_jwt(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "client_id": TEST_CLIENT_ID,
            "client_secret": TEST_CLIENT_SECRET,
            "subject": "staff-99",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body


def test_token_endpoint_rejects_invalid_client(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "client_id": TEST_CLIENT_ID,
            "client_secret": "bad-secret",
            "subject": "staff-99",
        },
    )
    assert response.status_code == 401


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_subject_with_valid_token(client: TestClient) -> None:
    token_response = client.post(
        "/api/v1/auth/token",
        json={
            "client_id": TEST_CLIENT_ID,
            "client_secret": TEST_CLIENT_SECRET,
            "subject": "staff-77",
        },
    )
    token = token_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == {"subject": "staff-77"}

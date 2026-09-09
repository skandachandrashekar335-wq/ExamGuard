"""Firebase non-interactive verification tests.

Tests the /auth/firebase/exchange endpoint without real Google OAuth.
Verifies security boundary: missing, invalid, malformed, and garbage tokens
are all rejected with 401. Requires FIREBASE_PROJECT_ID to be configured.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FIREBASE_EXCHANGE_URL = "/api/v1/auth/firebase/exchange"


@pytest.fixture
def client():
    return TestClient(app=create_app())


class TestFirebaseExchangeSecurity:
    def test_missing_token_returns_401(self, client):
        """No Authorization header and no body → 401."""
        resp = client.post(FIREBASE_EXCHANGE_URL)
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_empty_bearer_returns_401(self, client):
        """Authorization: Bearer (empty) → 401."""
        resp = client.post(
            FIREBASE_EXCHANGE_URL,
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    def test_garbage_token_returns_401(self, client):
        """Random string as Firebase token → 401."""
        resp = client.post(
            FIREBASE_EXCHANGE_URL,
            headers={"Authorization": "Bearer not_a_real_firebase_token"},
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"] or "Missing" in resp.json()["detail"]

    def test_malformed_jwt_returns_401(self, client):
        """JWT-structured but invalid → 401."""
        # 3 base64 segments, but garbage content
        fake_jwt = "eyJhbGciOiJSUzI1NiJ9.eyJ1aWQiOiIxMjMifQ.invalid_signature"
        resp = client.post(
            FIREBASE_EXCHANGE_URL,
            headers={"Authorization": f"Bearer {fake_jwt}"},
        )
        assert resp.status_code == 401

    def test_body_firebase_token_field(self, client):
        """firebaseToken in body is also accepted."""
        resp = client.post(
            FIREBASE_EXCHANGE_URL,
            json={"firebaseToken": "garbage"},
        )
        assert resp.status_code == 401

    def test_non_bearer_header_ignored(self, client):
        """Authorization header without 'Bearer ' prefix is ignored."""
        resp = client.post(
            FIREBASE_EXCHANGE_URL,
            headers={"Authorization": "Basic abc123"},
        )
        assert resp.status_code == 401

    def test_empty_body_firebase_token_returns_401(self, client):
        """Empty firebaseToken in body → 401."""
        resp = client.post(
            FIREBASE_EXCHANGE_URL,
            json={"firebaseToken": ""},
        )
        assert resp.status_code == 401

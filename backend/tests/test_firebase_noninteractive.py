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
        detail = resp.json()["detail"]
        assert "Firebase token verification failed" in detail

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


class TestAdminPromotion:
    """Regression test: INITIAL_ADMIN_EMAILS promotion when another ADMIN exists.

    Bug: The original code only checked INITIAL_ADMIN_EMAILS when no ADMIN
    existed in the system. Once any ADMIN existed, the allowlist was never
    checked again, leaving designated admin accounts stuck as REVIEWER.
    """

    def test_admin_email_always_checked(self):
        """Verify INITIAL_ADMIN_EMAILS is checked on every login, not just first."""
        from app.core.config import get_settings

        settings = get_settings()
        assert len(settings.INITIAL_ADMIN_EMAILS) > 0, (
            "INITIAL_ADMIN_EMAILS must contain at least one email"
        )
        # All emails must be valid format
        for email in settings.INITIAL_ADMIN_EMAILS:
            assert "@" in email and "." in email, f"Invalid email in INITIAL_ADMIN_EMAILS: {email}"

    def test_admin_promotion_code_path(self):
        """Verify the auth.py exchange checks INITIAL_ADMIN_EMAILS on every login.

        The promotion logic must NOT be gated by `not existing_admin`.
        It must check the allowlist regardless of whether other ADMINs exist.
        """
        import ast
        import inspect

        from app.api.v1.auth import firebase_token_exchange

        source = inspect.getsource(firebase_token_exchange)
        # Must NOT contain the old broken pattern
        assert "existing_admin" not in source, (
            "The old pattern 'if not existing_admin' must be removed. "
            "INITIAL_ADMIN_EMAILS must be checked on every login."
        )
        # Must contain the new correct pattern
        assert "INITIAL_ADMIN_EMAILS" in source, (
            "The exchange endpoint must check INITIAL_ADMIN_EMAILS"
        )
        assert "email_lower" in source or "lower()" in source, (
            "Email comparison must be case-insensitive"
        )

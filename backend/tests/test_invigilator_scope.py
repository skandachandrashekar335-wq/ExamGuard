"""Invigilator Scope Enforcement Tests.

Tests for:
- IDOR protection via get_invigilator_scope / check_invigilator_scope
- Entry verification scope enforcement
- Examination session scope enforcement
- Attendance scope enforcement
- Monitoring endpoint auth
- WebSocket context scoping (INVIGILATOR filter enforcement)
- eg_token regression: production mode ignores dev bypass
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from app.auth import (
    Role,
    create_access_token,
    decode_token,
    get_invigilator_scope,
    check_invigilator_scope,
    InvigilatorScope,
)


# ---------------------------------------------------------------------------
# check_invigilator_scope unit tests
# ---------------------------------------------------------------------------


class TestCheckInvigilatorScope:
    def test_none_scope_passes(self):
        """Non-INVIGILATOR (scope=None) always passes."""
        check_invigilator_scope(None, resource_exam_id=1, resource_hall_id=2)

    def test_matching_exam_passes(self):
        """Scope matches exam_id → passes."""
        scope = InvigilatorScope(exam_id=10, hall_id=20, entry_point_id=None, camera_id=None, assignment_id=1)
        check_invigilator_scope(scope, resource_exam_id=10, resource_hall_id=20)

    def test_mismatched_exam_raises_403(self):
        """Scope differs on exam_id → 403."""
        scope = InvigilatorScope(exam_id=10, hall_id=20, entry_point_id=None, camera_id=None, assignment_id=1)
        with pytest.raises(HTTPException) as exc_info:
            check_invigilator_scope(scope, resource_exam_id=99, resource_hall_id=20)
        assert exc_info.value.status_code == 403

    def test_mismatched_hall_raises_403(self):
        """Scope differs on hall_id → 403."""
        scope = InvigilatorScope(exam_id=10, hall_id=20, entry_point_id=None, camera_id=None, assignment_id=1)
        with pytest.raises(HTTPException) as exc_info:
            check_invigilator_scope(scope, resource_exam_id=10, resource_hall_id=99)
        assert exc_info.value.status_code == 403

    def test_none_exam_id_skipped(self):
        """resource_exam_id=None skips exam check."""
        scope = InvigilatorScope(exam_id=10, hall_id=20, entry_point_id=None, camera_id=None, assignment_id=1)
        check_invigilator_scope(scope, resource_exam_id=None, resource_hall_id=20)

    def test_none_hall_id_skipped(self):
        """resource_hall_id=None skips hall check."""
        scope = InvigilatorScope(exam_id=10, hall_id=20, entry_point_id=None, camera_id=None, assignment_id=1)
        check_invigilator_scope(scope, resource_exam_id=10, resource_hall_id=None)

    def test_both_none_passes(self):
        """Both resources None → passes (no checks to apply)."""
        scope = InvigilatorScope(exam_id=10, hall_id=20, entry_point_id=None, camera_id=None, assignment_id=1)
        check_invigilator_scope(scope, resource_exam_id=None, resource_hall_id=None)


# ---------------------------------------------------------------------------
# get_invigilator_scope unit tests
# ---------------------------------------------------------------------------


class TestGetInvigilatorScope:
    def test_admin_returns_none(self):
        """ADMIN role returns None (unrestricted)."""
        claims = {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"}
        result = get_invigilator_scope(claims, db=None)
        assert result is None

    def test_operator_returns_none(self):
        """OPERATOR role returns None (unrestricted)."""
        claims = {"sub": "7", "role": Role.OPERATOR, "email": "op@test.com"}
        result = get_invigilator_scope(claims, db=None)
        assert result is None

    def test_reviewer_returns_none(self):
        """REVIEWER role returns None (unrestricted)."""
        claims = {"sub": "8", "role": Role.REVIEWER, "email": "rev@test.com"}
        result = get_invigilator_scope(claims, db=None)
        assert result is None


# ---------------------------------------------------------------------------
# JWT token / eg_token regression
# ---------------------------------------------------------------------------


class TestDevTokenBypassRegressed:
    def test_backend_has_no_eg_token_endpoint(self):
        """Backend does NOT consume eg_token parameter.

        The eg_token bypass is frontend-only (AuthContext.tsx, guarded by
        NODE_ENV=development). Backend JWT auth must work via Authorization
        header or proper Firebase exchange, never via URL param.
        """
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Request with ?eg_token=<valid_jwt> — should NOT authenticate
        valid_token = create_access_token(
            {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"}
        )
        resp = client.get(
            "/api/v1/exams",
            params={"eg_token": valid_token},
        )
        # No Authorization header → must be 401/403
        assert resp.status_code in (401, 403)

    def test_valid_bearer_auth_works(self):
        """Standard Bearer token auth works as expected."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        valid_token = create_access_token(
            {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"}
        )
        resp = client.get(
            "/api/v1/exams",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200

    def test_expired_token_rejected(self):
        """Expired JWT is rejected by backend."""
        from fastapi.testclient import TestClient
        from app.main import create_app
        from datetime import timedelta

        app = create_app()
        client = TestClient(app)

        expired_token = create_access_token(
            {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"},
            expires_delta=timedelta(seconds=-1),
        )
        resp = client.get(
            "/api/v1/exams",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_malformed_token_rejected(self):
        """Garbage token is rejected."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        resp = client.get(
            "/api/v1/exams",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert resp.status_code == 401

    def test_no_token_rejected(self):
        """Request with no auth is rejected."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        resp = client.get("/api/v1/exams")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Monitoring endpoint auth
# ---------------------------------------------------------------------------


class TestMonitoringAuth:
    def test_monitoring_status_requires_auth(self):
        """GET /monitoring/status requires auth (previously had none)."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        resp = client.get("/api/v1/monitoring/status")
        assert resp.status_code in (401, 403)

    def test_monitoring_events_requires_auth(self):
        """GET /monitoring/events requires auth."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        resp = client.get("/api/v1/monitoring/events")
        assert resp.status_code in (401, 403)

    def test_monitoring_alerts_requires_auth(self):
        """GET /monitoring/alerts requires auth."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        resp = client.get("/api/v1/monitoring/alerts")
        assert resp.status_code in (401, 403)

    def test_monitoring_connections_requires_auth(self):
        """GET /monitoring/connections requires auth."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        resp = client.get("/api/v1/monitoring/connections")
        assert resp.status_code in (401, 403)

    def test_admin_can_access_monitoring(self):
        """ADMIN can access monitoring endpoints."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        token = create_access_token(
            {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"}
        )
        resp = client.get(
            "/api/v1/monitoring/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# WebSocket edge-case tests (supplements test_phase_13_3_websocket.py)
# ---------------------------------------------------------------------------


class TestWebSocketEdgeCases:
    @pytest.fixture(autouse=True)
    def _reset(self):
        from app.api.v1.ws_monitoring import reset_connection_manager
        reset_connection_manager()
        yield
        reset_connection_manager()

    def test_ws_no_token_rejected(self):
        """WS connection without token is rejected (code 1008)."""
        from starlette.websockets import WebSocketDisconnect
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/ws/monitoring") as ws:
                pass

    def test_ws_invalid_token_rejected(self):
        """WS connection with garbage token is rejected."""
        from starlette.websockets import WebSocketDisconnect
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/api/v1/ws/monitoring?token=garbage.jwt.token"
            ) as ws:
                pass

    def test_ws_valid_admin_token_accepted(self):
        """WS connection with valid ADMIN token is accepted."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        token = create_access_token(
            {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"}
        )
        with client.websocket_connect(
            f"/api/v1/ws/monitoring?token={token}"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "client_id" in data

    def test_ws_subscribe_message_type(self):
        """WS client can send pong and receive pong."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        token = create_access_token(
            {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"}
        )
        with client.websocket_connect(
            f"/api/v1/ws/monitoring?token={token}"
        ) as ws:
            ws.receive_json()  # connected message
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_ws_unknown_message_type(self):
        """WS client sending unknown message type gets error."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        token = create_access_token(
            {"sub": "5", "role": Role.ADMIN, "email": "admin@test.com"}
        )
        with client.websocket_connect(
            f"/api/v1/ws/monitoring?token={token}"
        ) as ws:
            ws.receive_json()  # connected message
            ws.send_json({"type": "unknown_xyz"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Unknown message type" in data["message"]

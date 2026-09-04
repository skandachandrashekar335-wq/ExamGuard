"""Phase 9.5 — Device Communication API Tests

Tests for the device communication API endpoints using FastAPI TestClient.
Uses dependency override with StaticPool to ensure SQLite works across threads.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base
from app.models.camera import Camera, CameraStatus
from app.core.database import get_db


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def camera(db_session):
    c = Camera(
        name="API Test Camera",
        device_identifier="API-TEST-CAM-001",
        status=CameraStatus.UNKNOWN.value,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def credential(db_session, camera):
    from app.services.device_credential import create_device_credential

    cred, raw_secret = create_device_credential(
        db_session, camera.id, "API Test Credential"
    )
    return cred, raw_secret


# ---------------------------------------------------------------------------
# POST /api/v1/device/credentials
# ---------------------------------------------------------------------------


class TestProvisionCredentialAPI:
    def test_provision_credential_success(self, client, camera):
        response = client.post(
            "/api/v1/device/credentials",
            json={"camera_id": camera.id, "label": "Test Credential"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "secret" in data
        assert data["camera_id"] == camera.id
        assert data["label"] == "Test Credential"
        assert data["status"] == "ACTIVE"

    def test_provision_credential_camera_not_found(self, client):
        response = client.post(
            "/api/v1/device/credentials",
            json={"camera_id": 99999, "label": "Test"},
        )
        assert response.status_code == 404

    def test_provision_credential_inactive_camera(self, client, db_session):
        camera = Camera(
            name="Inactive",
            device_identifier="INACTIVE-API-CAM",
            status=CameraStatus.UNKNOWN.value,
            is_active=False,
        )
        db_session.add(camera)
        db_session.commit()
        db_session.refresh(camera)

        response = client.post(
            "/api/v1/device/credentials",
            json={"camera_id": camera.id, "label": "Test"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/v1/device/credentials
# ---------------------------------------------------------------------------


class TestListCredentialsAPI:
    def test_list_credentials(self, client, camera, credential):
        response = client.get(
            f"/api/v1/device/credentials?camera_id={camera.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_list_credentials_no_secret(self, client, camera, credential):
        response = client.get(
            f"/api/v1/device/credentials?camera_id={camera.id}"
        )
        assert response.status_code == 200
        for cred in response.json():
            assert "secret" not in cred
            assert "secret_hash" not in cred


# ---------------------------------------------------------------------------
# GET /api/v1/device/credentials/{id}
# ---------------------------------------------------------------------------


class TestGetCredentialAPI:
    def test_get_credential(self, client, credential):
        cred, _ = credential
        response = client.get(f"/api/v1/device/credentials/{cred.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cred.id
        assert "secret" not in data

    def test_get_credential_not_found(self, client):
        response = client.get("/api/v1/device/credentials/99999")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/device/credentials/{id}/revoke
# ---------------------------------------------------------------------------


class TestRevokeCredentialAPI:
    def test_revoke_credential(self, client, credential):
        cred, _ = credential
        response = client.post(f"/api/v1/device/credentials/{cred.id}/revoke")
        assert response.status_code == 200
        assert response.json()["status"] == "REVOKED"

    def test_revoke_credential_not_found(self, client):
        response = client.post("/api/v1/device/credentials/99999/revoke")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/device/health
# ---------------------------------------------------------------------------


class TestDeviceHealthAPI:
    def test_device_health_success(self, client, credential):
        _, raw_secret = credential
        response = client.post(
            "/api/v1/device/health",
            json={"status": "ONLINE", "reason": "DEVICE_RESPONDED"},
            headers={"X-Device-Credential": raw_secret},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "ONLINE"
        assert data["last_seen_at"] is not None
        assert data["health_reason"] == "DEVICE_RESPONDED"

    def test_device_health_offline(self, client, credential):
        _, raw_secret = credential
        response = client.post(
            "/api/v1/device/health",
            json={"status": "OFFLINE", "reason": "DEVICE_UNREACHABLE"},
            headers={"X-Device-Credential": raw_secret},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "OFFLINE"

    def test_device_health_invalid_credential(self, client):
        response = client.post(
            "/api/v1/device/health",
            json={"status": "ONLINE"},
            headers={"X-Device-Credential": "invalid-secret"},
        )
        assert response.status_code == 401

    def test_device_health_missing_credential(self, client):
        response = client.post(
            "/api/v1/device/health",
            json={"status": "ONLINE"},
        )
        assert response.status_code == 422

    def test_device_health_revoked_credential(self, client, credential):
        cred, raw_secret = credential
        response = client.post(f"/api/v1/device/credentials/{cred.id}/revoke")
        assert response.status_code == 200

        response = client.post(
            "/api/v1/device/health",
            json={"status": "ONLINE"},
            headers={"X-Device-Credential": raw_secret},
        )
        assert response.status_code == 401

    def test_device_health_invalid_status(self, client, credential):
        _, raw_secret = credential
        response = client.post(
            "/api/v1/device/health",
            json={"status": "PENDING"},
            headers={"X-Device-Credential": raw_secret},
        )
        assert response.status_code == 400

    def test_device_health_with_observed_at(self, client, credential):
        _, raw_secret = credential
        response = client.post(
            "/api/v1/device/health",
            json={
                "status": "ONLINE",
                "observed_at": "2026-01-15T10:30:00Z",
            },
            headers={"X-Device-Credential": raw_secret},
        )
        assert response.status_code == 201
        assert response.json()["last_seen_at"] is not None

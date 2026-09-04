"""Phase 9.4 — Camera Health API tests.

Uses real PostgreSQL via SessionLocal (same pattern as other API tests).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.camera import Camera
from app.models.camera_entry_point import CameraEntryPointMapping


@pytest.fixture(autouse=True)
def clean_test_data():
    """Remove test data before each test to avoid conflicts."""
    db = SessionLocal()
    try:
        db.execute(delete(CameraEntryPointMapping))
        db.execute(delete(Camera).where(Camera.device_identifier.like("TEST%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def camera(client):
    r = client.post(
        "/api/v1/cameras",
        json={
            "name": "Test Camera",
            "device_identifier": "TEST-CAM-001",
        },
    )
    assert r.status_code == 201
    return r.json()


@pytest.fixture()
def inactive_camera(client):
    r = client.post(
        "/api/v1/cameras",
        json={
            "name": "Inactive Camera",
            "device_identifier": "TEST-INACTIVE-CAM-001",
        },
    )
    assert r.status_code == 201
    cam_id = r.json()["id"]
    r2 = client.delete(f"/api/v1/cameras/{cam_id}")
    assert r2.status_code == 200
    return r2.json()


# ---------------------------------------------------------------------------
# GET /cameras/{id}/health
# ---------------------------------------------------------------------------


class TestGetHealth:
    def test_health_returns_200(self, client, camera):
        r = client.get(f"/api/v1/cameras/{camera['id']}/health")
        assert r.status_code == 200

    def test_health_returns_correct_schema(self, client, camera):
        r = client.get(f"/api/v1/cameras/{camera['id']}/health")
        data = r.json()
        assert "camera_id" in data
        assert "status" in data
        assert "last_seen_at" in data
        assert "last_health_check_at" in data
        assert "health_reason" in data
        assert "is_active" in data

    def test_health_initial_status_unknown(self, client, camera):
        r = client.get(f"/api/v1/cameras/{camera['id']}/health")
        data = r.json()
        assert data["status"] == "UNKNOWN"
        assert data["last_seen_at"] is None
        assert data["last_health_check_at"] is None
        assert data["health_reason"] is None

    def test_health_camera_not_found(self, client):
        r = client.get("/api/v1/cameras/99999/health")
        assert r.status_code == 404

    def test_health_inactive_camera(self, client, inactive_camera):
        r = client.get(f"/api/v1/cameras/{inactive_camera['id']}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["is_active"] is False
        assert data["status"] == "DISABLED"


# ---------------------------------------------------------------------------
# POST /cameras/{id}/health-observations
# ---------------------------------------------------------------------------


class TestRecordObservation:
    def test_online_observation_returns_201(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE"},
        )
        assert r.status_code == 201

    def test_online_observation_sets_status(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE"},
        )
        data = r.json()
        assert data["status"] == "ONLINE"

    def test_online_observation_sets_last_seen(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE"},
        )
        data = r.json()
        assert data["last_seen_at"] is not None
        assert data["last_health_check_at"] is not None

    def test_offline_observation(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "OFFLINE"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "OFFLINE"
        assert data["last_seen_at"] is None

    def test_observation_with_reason(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE", "reason": "DEVICE_RESPONDED"},
        )
        data = r.json()
        assert data["health_reason"] == "DEVICE_RESPONDED"

    def test_observation_with_observed_at(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={
                "status": "ONLINE",
                "observed_at": "2026-06-15T12:00:00Z",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["last_seen_at"] is not None
        assert "2026-06-15" in data["last_seen_at"]

    def test_camera_not_found(self, client):
        r = client.post(
            "/api/v1/cameras/99999/health-observations",
            json={"status": "ONLINE"},
        )
        assert r.status_code == 404

    def test_invalid_status(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "PENDING"},
        )
        assert r.status_code == 400

    def test_invalid_reason(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE", "reason": "BAD_REASON"},
        )
        assert r.status_code == 400

    def test_inactive_camera_rejected(self, client, inactive_camera):
        r = client.post(
            f"/api/v1/cameras/{inactive_camera['id']}/health-observations",
            json={"status": "ONLINE"},
        )
        assert r.status_code == 400

    def test_future_timestamp_rejected(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={
                "status": "ONLINE",
                "observed_at": "2099-01-01T00:00:00Z",
            },
        )
        assert r.status_code == 400

    def test_observation_persists_across_calls(self, client, camera):
        client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE", "reason": "DEVICE_RESPONDED"},
        )
        r = client.get(f"/api/v1/cameras/{camera['id']}/health")
        data = r.json()
        assert data["status"] == "ONLINE"
        assert data["health_reason"] == "DEVICE_RESPONDED"
        assert data["last_seen_at"] is not None

    def test_observation_updates_previous(self, client, camera):
        client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE"},
        )
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "OFFLINE", "reason": "DEVICE_UNREACHABLE"},
        )
        data = r.json()
        assert data["status"] == "OFFLINE"
        assert data["health_reason"] == "DEVICE_UNREACHABLE"

    def test_no_credential_leakage(self, client, camera):
        r = client.get(f"/api/v1/cameras/{camera['id']}/health")
        data = r.json()
        for key in data:
            val = str(data[key]).lower()
            assert "password" not in val
            assert "secret" not in val
            assert "api_key" not in val
            assert "credential" not in val

    def test_observation_response_schema(self, client, camera):
        r = client.post(
            f"/api/v1/cameras/{camera['id']}/health-observations",
            json={"status": "ONLINE"},
        )
        data = r.json()
        assert isinstance(data["camera_id"], int)
        assert isinstance(data["status"], str)
        assert isinstance(data["is_active"], bool)

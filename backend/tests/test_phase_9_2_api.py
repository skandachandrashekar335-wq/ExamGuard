"""Phase 9.2 — Camera, EntryPoint, and CameraEntryPointMapping API tests.

Uses real PostgreSQL via SessionLocal (same pattern as other API tests).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.camera import Camera
from app.models.camera_entry_point import CameraEntryPointMapping
from app.models.entry_point import EntryPoint
from app.models.exam_hall import ExamHall


@pytest.fixture(autouse=True)
def clean_test_data():
    """Remove test data before each test to avoid conflicts."""
    db = SessionLocal()
    try:
        db.execute(delete(CameraEntryPointMapping))
        db.execute(delete(Camera).where(Camera.device_identifier.like("TEST%")))
        db.execute(delete(EntryPoint).where(EntryPoint.code.like("TEST%")))
        db.execute(delete(ExamHall).where(ExamHall.building.like("CAM_TEST%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def hall():
    db = SessionLocal()
    try:
        h = ExamHall(building="CAM_TEST Block", room_number="101", capacity=50)
        db.add(h)
        db.commit()
        db.refresh(h)
        return h
    finally:
        db.close()


@pytest.fixture()
def camera(client, hall):
    r = client.post(
        "/api/v1/cameras",
        json={
            "name": "Test Camera",
            "device_identifier": "TEST-CAM-001",
            "exam_hall_id": hall.id,
        },
    )
    assert r.status_code == 201
    return r.json()


@pytest.fixture()
def entry_point(client, hall):
    r = client.post(
        "/api/v1/entry-points",
        json={
            "name": "Test Gate",
            "code": "TEST_GATE",
            "exam_hall_id": hall.id,
        },
    )
    assert r.status_code == 201
    return r.json()


# ===========================================================================
# Camera API Tests
# ===========================================================================

class TestCameraAPI:
    def test_create_camera(self, client):
        r = client.post(
            "/api/v1/cameras",
            json={"name": "Cam A", "device_identifier": "TEST-CAM-A"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Cam A"
        assert data["device_identifier"] == "TEST-CAM-A"
        assert data["status"] == "UNKNOWN"
        assert data["is_active"] is True

    def test_create_camera_with_all_fields(self, client, hall):
        r = client.post(
            "/api/v1/cameras",
            json={
                "name": "Full Cam",
                "device_identifier": "TEST-CAM-FULL",
                "camera_type": "IP",
                "manufacturer": "Hikvision",
                "model_name": "DS-2CD2143",
                "resolution_width": 1920,
                "resolution_height": 1080,
                "exam_hall_id": hall.id,
                "connection_info": "192.168.1.100",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["camera_type"] == "IP"
        assert data["manufacturer"] == "Hikvision"
        assert data["exam_hall_id"] == hall.id

    def test_list_cameras(self, client, camera):
        r = client.get("/api/v1/cameras")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert any(c["device_identifier"] == "TEST-CAM-001" for c in data["items"])

    def test_list_cameras_pagination(self, client):
        for i in range(3):
            client.post(
                "/api/v1/cameras",
                json={"name": f"Cam P{i}", "device_identifier": f"TEST-CAM-P{i}"},
            )
        r = client.get("/api/v1/cameras?page=1&page_size=2")
        assert r.status_code == 200
        assert r.json()["page_size"] == 2

    def test_list_cameras_search(self, client, camera):
        r = client.get("/api/v1/cameras?search=TEST-CAM-001")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_cameras_filter_by_hall(self, client, camera, hall):
        r = client.get(f"/api/v1/cameras?exam_hall_id={hall.id}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_cameras_filter_by_status(self, client, camera):
        r = client.get("/api/v1/cameras?status=UNKNOWN")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_camera(self, client, camera):
        r = client.get(f"/api/v1/cameras/{camera['id']}")
        assert r.status_code == 200
        assert r.json()["device_identifier"] == "TEST-CAM-001"

    def test_get_camera_not_found(self, client):
        r = client.get("/api/v1/cameras/99999")
        assert r.status_code == 404

    def test_update_camera(self, client, camera):
        r = client.patch(
            f"/api/v1/cameras/{camera['id']}",
            json={"name": "Updated Cam", "status": "ONLINE"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Cam"
        assert r.json()["status"] == "ONLINE"

    def test_update_camera_not_found(self, client):
        r = client.patch("/api/v1/cameras/99999", json={"name": "X"})
        assert r.status_code == 404

    def test_duplicate_device_identifier(self, client, camera):
        r = client.post(
            "/api/v1/cameras",
            json={"name": "Dup", "device_identifier": "TEST-CAM-001"},
        )
        assert r.status_code == 409

    def test_deactivate_camera(self, client, camera):
        r = client.delete(f"/api/v1/cameras/{camera['id']}")
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_deactivate_camera_not_found(self, client):
        r = client.delete("/api/v1/cameras/99999")
        assert r.status_code == 404

    def test_include_inactive(self, client, camera):
        client.delete(f"/api/v1/cameras/{camera['id']}")
        r = client.get("/api/v1/cameras?include_inactive=true")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_exclude_inactive_by_default(self, client, camera):
        client.delete(f"/api/v1/cameras/{camera['id']}")
        r = client.get("/api/v1/cameras")
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()["items"]]
        assert camera["id"] not in ids


# ===========================================================================
# EntryPoint API Tests
# ===========================================================================

class TestEntryPointAPI:
    def test_create_entry_point(self, client):
        r = client.post(
            "/api/v1/entry-points",
            json={"name": "Gate A", "code": "TEST_GA"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Gate A"
        assert data["code"] == "TEST_GA"
        assert data["is_active"] is True

    def test_code_is_uppercased(self, client):
        r = client.post(
            "/api/v1/entry-points",
            json={"name": "Gate", "code": "test_lower"},
        )
        assert r.status_code == 201
        assert r.json()["code"] == "TEST_LOWER"

    def test_create_with_all_fields(self, client, hall):
        r = client.post(
            "/api/v1/entry-points",
            json={
                "name": "Full Gate",
                "code": "TEST_FULL",
                "description": "Main entrance",
                "location_detail": "Ground floor",
                "exam_hall_id": hall.id,
            },
        )
        assert r.status_code == 201
        assert r.json()["description"] == "Main entrance"
        assert r.json()["exam_hall_id"] == hall.id

    def test_list_entry_points(self, client, entry_point):
        r = client.get("/api/v1/entry-points")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_entry_points_search(self, client, entry_point):
        r = client.get("/api/v1/entry-points?search=TEST_GATE")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_entry_points_filter_by_hall(self, client, entry_point, hall):
        r = client.get(f"/api/v1/entry-points?exam_hall_id={hall.id}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_entry_point(self, client, entry_point):
        r = client.get(f"/api/v1/entry-points/{entry_point['id']}")
        assert r.status_code == 200
        assert r.json()["code"] == "TEST_GATE"

    def test_get_entry_point_not_found(self, client):
        r = client.get("/api/v1/entry-points/99999")
        assert r.status_code == 404

    def test_update_entry_point(self, client, entry_point):
        r = client.patch(
            f"/api/v1/entry-points/{entry_point['id']}",
            json={"name": "Updated Gate"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Gate"

    def test_update_entry_point_not_found(self, client):
        r = client.patch("/api/v1/entry-points/99999", json={"name": "X"})
        assert r.status_code == 404

    def test_duplicate_code(self, client, entry_point):
        r = client.post(
            "/api/v1/entry-points",
            json={"name": "Dup", "code": "TEST_GATE"},
        )
        assert r.status_code == 409

    def test_deactivate_entry_point(self, client, entry_point):
        r = client.delete(f"/api/v1/entry-points/{entry_point['id']}")
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_deactivate_entry_point_not_found(self, client):
        r = client.delete("/api/v1/entry-points/99999")
        assert r.status_code == 404

    def test_include_inactive(self, client, entry_point):
        client.delete(f"/api/v1/entry-points/{entry_point['id']}")
        r = client.get("/api/v1/entry-points?include_inactive=true")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


# ===========================================================================
# CameraEntryPointMapping API Tests
# ===========================================================================

class TestCameraEntryPointMappingAPI:
    def test_create_mapping(self, client, camera, entry_point):
        r = client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["camera_id"] == camera["id"]
        assert data["entry_point_id"] == entry_point["id"]
        assert data["is_enabled"] is True

    def test_duplicate_mapping(self, client, camera, entry_point):
        client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        r = client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        assert r.status_code == 409

    def test_list_mappings(self, client, camera, entry_point):
        client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        r = client.get("/api/v1/camera-entry-points")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_mappings_filter_by_camera(self, client, camera, entry_point):
        client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        r = client.get(f"/api/v1/camera-entry-points?camera_id={camera['id']}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_mappings_filter_by_entry_point(self, client, camera, entry_point):
        client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        r = client.get(f"/api/v1/camera-entry-points?entry_point_id={entry_point['id']}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_mapping(self, client, camera, entry_point):
        create_r = client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        mapping_id = create_r.json()["id"]
        r = client.get(f"/api/v1/camera-entry-points/{mapping_id}")
        assert r.status_code == 200
        assert r.json()["id"] == mapping_id

    def test_get_mapping_not_found(self, client):
        r = client.get("/api/v1/camera-entry-points/99999")
        assert r.status_code == 404

    def test_update_mapping(self, client, camera, entry_point):
        create_r = client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        mapping_id = create_r.json()["id"]
        r = client.patch(
            f"/api/v1/camera-entry-points/{mapping_id}",
            json={"is_enabled": False},
        )
        assert r.status_code == 200
        assert r.json()["is_enabled"] is False

    def test_update_mapping_not_found(self, client):
        r = client.patch("/api/v1/camera-entry-points/99999", json={"is_enabled": False})
        assert r.status_code == 404

    def test_deactivate_mapping(self, client, camera, entry_point):
        create_r = client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        mapping_id = create_r.json()["id"]
        r = client.delete(f"/api/v1/camera-entry-points/{mapping_id}")
        assert r.status_code == 200
        assert r.json()["is_enabled"] is False

    def test_deactivate_mapping_not_found(self, client):
        r = client.delete("/api/v1/camera-entry-points/99999")
        assert r.status_code == 404

    def test_include_disabled(self, client, camera, entry_point):
        create_r = client.post(
            "/api/v1/camera-entry-points",
            json={"camera_id": camera["id"], "entry_point_id": entry_point["id"]},
        )
        mapping_id = create_r.json()["id"]
        client.delete(f"/api/v1/camera-entry-points/{mapping_id}")
        r = client.get("/api/v1/camera-entry-points?include_disabled=true")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

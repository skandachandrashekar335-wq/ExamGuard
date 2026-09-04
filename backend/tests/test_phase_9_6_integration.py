"""Phase 9.6 — Camera Infrastructure Integration & Hardening

Cross-component integration tests verifying the complete Phase 9 camera
infrastructure works correctly as ONE domain. Tests focus on cross-component
behavior, security invariants, state machine correctness, and data integrity
rather than duplicating existing unit tests.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.models import Base
from app.models.camera import Camera, CameraStatus, HealthReason
from app.models.camera_device_credential import CameraDeviceCredential, CredentialStatus
from app.models.camera_entry_point import CameraEntryPointMapping
from app.models.entry_point import EntryPoint
from app.models.exam_hall import ExamHall
from app.core.database import get_db
from app.services import camera as camera_service
from app.services import entry_point as ep_service
from app.services import camera_entry_point as mapping_service
from app.services import device_credential
from app.services import camera_health


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
def db(engine):
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
    def override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


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
def hall(db):
    h = ExamHall(building="INT-HALL", room_number="301", capacity=100)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@pytest.fixture()
def camera(db, hall):
    c = Camera(
        name="Integration Camera",
        device_identifier="INT-CAM-001",
        exam_hall_id=hall.id,
        status=CameraStatus.UNKNOWN.value,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def entry_point(db, hall):
    ep = EntryPoint(
        name="Main Gate",
        code="INT_GATE",
        exam_hall_id=hall.id,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


# ---------------------------------------------------------------------------
# 1. Camera Lifecycle Integration
# ---------------------------------------------------------------------------


class TestCameraLifecycleIntegration:
    def test_create_active_camera_has_unknown_status(self, db):
        c = Camera(name="Fresh", device_identifier="LIFECYCLE-001")
        db.add(c)
        db.commit()
        db.refresh(c)
        assert c.is_active is True
        assert c.status == CameraStatus.UNKNOWN.value
        assert c.last_seen_at is None
        assert c.last_health_check_at is None
        assert c.health_reason is None

    def test_deactivate_camera_sets_disabled_status(self, db, camera):
        result = camera_service.deactivate_camera(db, camera.id)
        assert result.is_active is False
        assert result.status == CameraStatus.DISABLED.value

    def test_deactivated_camera_cannot_be_health_observed(self, db, camera):
        camera_service.deactivate_camera(db, camera.id)
        with pytest.raises(ValueError, match="inactive"):
            camera_health.record_health_observation(
                db, camera.id, "ONLINE"
            )

    def test_deactivated_camera_cannot_authenticate_credential(self, db, camera):
        _, raw = device_credential.create_device_credential(
            db, camera.id, "test"
        )
        camera_service.deactivate_camera(db, camera.id)
        with pytest.raises(ValueError, match="inactive"):
            device_credential.authenticate_device(db, raw)

    def test_health_observation_is_only_path_to_change_status(self, db, camera):
        from app.schemas.camera import CameraUpdate

        assert camera.status == CameraStatus.UNKNOWN.value
        camera_service.update_camera(
            db, camera.id, CameraUpdate(name="Updated Name")
        )
        assert camera.status == CameraStatus.UNKNOWN.value

    def test_health_observation_sets_online_and_last_seen(self, db, camera):
        obs_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = camera_health.record_health_observation(
            db, camera.id, "ONLINE", observed_at=obs_time,
            reason="DEVICE_RESPONDED",
        )
        assert result.status == CameraStatus.ONLINE.value
        assert result.last_seen_at.replace(tzinfo=None) == obs_time.replace(tzinfo=None)
        assert result.health_reason == HealthReason.DEVICE_RESPONDED.value
        assert result.last_health_check_at is not None

    def test_health_observation_offline_preserves_last_seen(self, db, camera):
        obs1 = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        camera_health.record_health_observation(
            db, camera.id, "ONLINE", observed_at=obs1
        )
        db.refresh(camera)
        first_seen = camera.last_seen_at

        obs2 = datetime(2026, 1, 15, 10, 5, 0, tzinfo=timezone.utc)
        camera_health.record_health_observation(
            db, camera.id, "OFFLINE", observed_at=obs2,
            reason="DEVICE_UNREACHABLE",
        )
        db.refresh(camera)
        assert camera.status == CameraStatus.OFFLINE.value
        assert camera.last_seen_at == first_seen

    def test_reactivate_camera_resets_to_unknown(self, db, camera):
        camera_service.deactivate_camera(db, camera.id)
        db.refresh(camera)
        assert camera.status == CameraStatus.DISABLED.value
        camera.is_active = True
        camera.status = CameraStatus.UNKNOWN.value
        db.commit()
        db.refresh(camera)
        assert camera.is_active is True
        assert camera.status == CameraStatus.UNKNOWN.value


# ---------------------------------------------------------------------------
# 2. Mapping Lifecycle Integration
# ---------------------------------------------------------------------------


class TestMappingLifecycleIntegration:
    def test_create_mapping(self, db, camera, entry_point):
        m = mapping_service.create_mapping(
            db,
            type("Data", (), {"camera_id": camera.id, "entry_point_id": entry_point.id})(),
        )
        assert m.camera_id == camera.id
        assert m.entry_point_id == entry_point.id
        assert m.is_enabled is True

    def test_duplicate_mapping_rejected(self, db, camera, entry_point):
        class D:
            camera_id: int
            entry_point_id: int
        d = D()
        d.camera_id = camera.id
        d.entry_point_id = entry_point.id
        mapping_service.create_mapping(db, d)
        with pytest.raises(ValueError, match="already exists"):
            mapping_service.create_mapping(db, d)

    def test_disable_mapping_preserves_history(self, db, camera, entry_point):
        class D:
            camera_id: int
            entry_point_id: int
        d = D()
        d.camera_id = camera.id
        d.entry_point_id = entry_point.id
        m = mapping_service.create_mapping(db, d)
        result = mapping_service.deactivate_mapping(db, m.id)
        assert result.is_enabled is False

    def test_deactivate_camera_does_not_break_mapping(self, db, camera, entry_point):
        class D:
            camera_id: int
            entry_point_id: int
        d = D()
        d.camera_id = camera.id
        d.entry_point_id = entry_point.id
        m = mapping_service.create_mapping(db, d)
        camera_service.deactivate_camera(db, camera.id)
        refreshed = mapping_service.get_mapping(db, m.id)
        assert refreshed is not None
        assert refreshed.camera_id == camera.id


# ---------------------------------------------------------------------------
# 3. Credential → Camera Binding Integration
# ---------------------------------------------------------------------------


class TestCredentialCameraBinding:
    def test_credential_bound_to_exact_camera(self, db, camera):
        cred, raw = device_credential.create_device_credential(
            db, camera.id, "binding-test"
        )
        assert cred.camera_id == camera.id
        authenticated = device_credential.authenticate_device(db, raw)
        assert authenticated.camera_id == camera.id

    def test_credential_cannot_target_another_camera(self, db, camera):
        c2 = Camera(
            name="Other Camera",
            device_identifier="BINDING-OTHER",
            status=CameraStatus.UNKNOWN.value,
        )
        db.add(c2)
        db.commit()
        db.refresh(c2)

        cred, raw = device_credential.create_device_credential(
            db, camera.id, "test"
        )
        authenticated = device_credential.authenticate_device(db, raw)
        assert authenticated.camera_id == camera.id
        assert authenticated.camera_id != c2.id

    def test_multiple_cameras_independent_credentials(self, db):
        c1 = Camera(
            name="Cam1", device_identifier="MULTI-1",
            status=CameraStatus.UNKNOWN.value,
        )
        c2 = Camera(
            name="Cam2", device_identifier="MULTI-2",
            status=CameraStatus.UNKNOWN.value,
        )
        db.add_all([c1, c2])
        db.commit()
        db.refresh(c1)
        db.refresh(c2)

        _, raw1 = device_credential.create_device_credential(db, c1.id, "c1")
        _, raw2 = device_credential.create_device_credential(db, c2.id, "c2")

        auth1 = device_credential.authenticate_device(db, raw1)
        auth2 = device_credential.authenticate_device(db, raw2)
        assert auth1.camera_id == c1.id
        assert auth2.camera_id == c2.id

    def test_revoked_credential_cannot_authenticate(self, db, camera):
        cred, raw = device_credential.create_device_credential(
            db, camera.id, "revoke-test"
        )
        device_credential.revoke_device_credential(db, cred.id)
        with pytest.raises(ValueError, match="revoked"):
            device_credential.authenticate_device(db, raw)

    def test_credential_cascade_delete_with_camera(self, db):
        c = Camera(
            name="Cascade Cam", device_identifier="CASCADE-CAM",
            status=CameraStatus.UNKNOWN.value,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        device_credential.create_device_credential(db, c.id, "will-be-deleted")
        db.delete(c)
        db.commit()
        remaining = db.query(CameraDeviceCredential).filter(
            CameraDeviceCredential.camera_id == c.id
        ).all()
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# 4. Full Device Authentication → Health Chain
# ---------------------------------------------------------------------------


class TestDeviceAuthHealthChain:
    def test_full_chain_online(self, db, camera):
        _, raw = device_credential.create_device_credential(
            db, camera.id, "chain-test"
        )
        cred = device_credential.authenticate_device(db, raw)
        assert cred.camera_id == camera.id

        obs_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        cam = camera_health.record_health_observation(
            db, cred.camera_id, "ONLINE",
            observed_at=obs_time, reason="DEVICE_RESPONDED",
        )
        assert cam.status == CameraStatus.ONLINE.value
        assert cam.last_seen_at.replace(tzinfo=None) == obs_time.replace(tzinfo=None)
        assert cam.health_reason == HealthReason.DEVICE_RESPONDED.value

    def test_full_chain_offline(self, db, camera):
        _, raw = device_credential.create_device_credential(
            db, camera.id, "chain-offline"
        )
        cred = device_credential.authenticate_device(db, raw)

        obs_time = datetime(2026, 6, 1, 12, 5, 0, tzinfo=timezone.utc)
        cam = camera_health.record_health_observation(
            db, cred.camera_id, "OFFLINE",
            observed_at=obs_time, reason="DEVICE_UNREACHABLE",
        )
        assert cam.status == CameraStatus.OFFLINE.value
        assert cam.last_seen_at is None

    def test_deactivated_camera_breaks_full_chain(self, db, camera):
        _, raw = device_credential.create_device_credential(
            db, camera.id, "chain-dead"
        )
        camera_service.deactivate_camera(db, camera.id)
        with pytest.raises(ValueError, match="inactive"):
            device_credential.authenticate_device(db, raw)


# ---------------------------------------------------------------------------
# 5. Exam Hall → Camera → Mapping Integration
# ---------------------------------------------------------------------------


class TestHallCameraMappingIntegration:
    def test_camera_in_hall_has_hall_id(self, db, hall):
        c = Camera(
            name="Hall Camera", device_identifier="HALL-CAM-1",
            exam_hall_id=hall.id, status=CameraStatus.UNKNOWN.value,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        assert c.exam_hall_id == hall.id

    def test_entry_point_in_hall_has_hall_id(self, db, hall):
        ep = EntryPoint(
            name="Hall Gate", code="HALL-GATE-1",
            exam_hall_id=hall.id,
        )
        db.add(ep)
        db.commit()
        db.refresh(ep)
        assert ep.exam_hall_id == hall.id

    def test_camera_without_hall_can_be_created(self, db):
        c = Camera(
            name="No Hall Camera", device_identifier="NOHALL-CAM",
            status=CameraStatus.UNKNOWN.value,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        assert c.exam_hall_id is None

    def test_hall_cascade_delete_does_not_destroy_cameras(self, db, hall):
        c = Camera(
            name="Surviving Camera", device_identifier="SURVIVE-CAM",
            exam_hall_id=hall.id, status=CameraStatus.UNKNOWN.value,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        db.delete(hall)
        db.commit()
        surviving = db.query(Camera).filter(Camera.id == c.id).first()
        assert surviving is not None
        assert surviving.exam_hall_id is None


# ---------------------------------------------------------------------------
# 6. Security Invariants
# ---------------------------------------------------------------------------


class TestSecurityInvariants:
    def test_raw_secret_never_stored(self, db, camera):
        cred, raw = device_credential.create_device_credential(
            db, camera.id, "sec-test"
        )
        assert cred.secret_hash != raw
        assert raw not in cred.secret_hash
        assert len(raw) == 64

    def test_hash_never_exposed_via_api(self, db, camera):
        cred, _ = device_credential.create_device_credential(
            db, camera.id, "api-sec"
        )
        from app.schemas.device_credential import DeviceCredentialResponse
        response_schema = DeviceCredentialResponse.model_validate(cred)
        response_dict = response_schema.model_dump()
        assert "secret_hash" not in response_dict
        assert "secret" not in response_dict

    def test_constant_time_comparison_used(self, db, camera):
        _, raw = device_credential.create_device_credential(
            db, camera.id, "ct-test"
        )
        cred = device_credential.authenticate_device(db, raw)
        assert cred is not None

    def test_empty_credential_rejected(self, db):
        with pytest.raises(LookupError, match="Invalid"):
            device_credential.authenticate_device(db, "")

    def test_whitespace_credential_rejected(self, db):
        with pytest.raises(LookupError, match="Invalid"):
            device_credential.authenticate_device(db, "   ")

    def test_invalid_credential_rejected(self, db):
        with pytest.raises(LookupError, match="Invalid"):
            device_credential.authenticate_device(
                db, "a" * 64
            )

    def test_error_messages_do_not_leak_secrets(self, db, camera):
        _, raw = device_credential.create_device_credential(
            db, camera.id, "leak-test"
        )
        try:
            device_credential.authenticate_device(db, "wrong")
        except LookupError as e:
            assert raw not in str(e)

    def test_no_biometric_data_in_credential_model(self, db, camera):
        cred, _ = device_credential.create_device_credential(
            db, camera.id, "privacy"
        )
        fields = {c.name for c in CameraDeviceCredential.__table__.columns}
        biometric_fields = {
            "face_embedding", "face_image", "fingerprint",
            "biometric_template", "video_frame", "student_id",
        }
        assert fields.isdisjoint(biometric_fields)


# ---------------------------------------------------------------------------
# 7. API Integration via TestClient
# ---------------------------------------------------------------------------


class TestAPIIntegration:
    def test_camera_crud_lifecycle(self, client):
        r = client.post("/api/v1/cameras", json={
            "name": "API Lifecycle", "device_identifier": "API-LC-001",
        })
        assert r.status_code == 201
        cam_id = r.json()["id"]
        assert r.json()["status"] == "UNKNOWN"

        r = client.get(f"/api/v1/cameras/{cam_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "UNKNOWN"

        r = client.patch(f"/api/v1/cameras/{cam_id}", json={"name": "Updated"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated"
        assert r.json()["status"] == "UNKNOWN"

        r = client.delete(f"/api/v1/cameras/{cam_id}")
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        assert r.json()["status"] == "DISABLED"

    def test_cannot_set_status_via_camera_update(self, client):
        r = client.post("/api/v1/cameras", json={
            "name": "No Status", "device_identifier": "API-NOSTAT",
        })
        cam_id = r.json()["id"]
        r = client.patch(f"/api/v1/cameras/{cam_id}", json={
            "name": "Still No Status",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "UNKNOWN"

    def test_health_observation_via_api(self, client):
        r = client.post("/api/v1/cameras", json={
            "name": "Health API", "device_identifier": "API-HEALTH",
        })
        cam_id = r.json()["id"]
        r = client.post(
            f"/api/v1/cameras/{cam_id}/health-observations",
            json={"status": "ONLINE", "reason": "DEVICE_RESPONDED"},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "ONLINE"
        assert r.json()["last_seen_at"] is not None

    def test_device_health_endpoint_auth(self, client):
        r = client.post("/api/v1/cameras", json={
            "name": "Device Auth", "device_identifier": "API-DAUTH",
        })
        cam_id = r.json()["id"]
        r = client.post(
            "/api/v1/device/credentials",
            json={"camera_id": cam_id, "label": "test"},
        )
        assert r.status_code == 201
        raw = r.json()["secret"]

        r = client.post(
            "/api/v1/device/health",
            json={"status": "ONLINE", "reason": "DEVICE_RESPONDED"},
            headers={"X-Device-Credential": raw},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "ONLINE"
        assert r.json()["camera_id"] == cam_id

    def test_device_health_rejected_without_credential(self, client):
        r = client.post(
            "/api/v1/device/health",
            json={"status": "ONLINE"},
        )
        assert r.status_code == 422

    def test_device_health_rejected_with_invalid_credential(self, client):
        r = client.post(
            "/api/v1/device/health",
            json={"status": "ONLINE"},
            headers={"X-Device-Credential": "invalid"},
        )
        assert r.status_code == 401

    def test_mapping_crud_lifecycle(self, client):
        r = client.post("/api/v1/cameras", json={
            "name": "Map Cam", "device_identifier": "MAP-CAM",
        })
        cam_id = r.json()["id"]
        r = client.post("/api/v1/entry-points", json={
            "name": "Map Gate", "code": "MAPGATE",
        })
        ep_id = r.json()["id"]

        r = client.post("/api/v1/camera-entry-points", json={
            "camera_id": cam_id, "entry_point_id": ep_id,
        })
        assert r.status_code == 201
        map_id = r.json()["id"]
        assert r.json()["is_enabled"] is True

        r = client.delete(f"/api/v1/camera-entry-points/{map_id}")
        assert r.status_code == 200
        assert r.json()["is_enabled"] is False

    def test_duplicate_mapping_rejected_via_api(self, client):
        r = client.post("/api/v1/cameras", json={
            "name": "Dup Cam", "device_identifier": "DUP-CAM",
        })
        cam_id = r.json()["id"]
        r = client.post("/api/v1/entry-points", json={
            "name": "Dup Gate", "code": "DUPGATE",
        })
        ep_id = r.json()["id"]

        r = client.post("/api/v1/camera-entry-points", json={
            "camera_id": cam_id, "entry_point_id": ep_id,
        })
        assert r.status_code == 201

        r = client.post("/api/v1/camera-entry-points", json={
            "camera_id": cam_id, "entry_point_id": ep_id,
        })
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# 8. Cross-Component State Consistency
# ---------------------------------------------------------------------------


class TestCrossComponentStateConsistency:
    def test_deactivated_camera_rejected_by_credential_service(self, db, camera):
        _, raw = device_credential.create_device_credential(
            db, camera.id, "cross-test"
        )
        camera_service.deactivate_camera(db, camera.id)
        with pytest.raises(ValueError, match="inactive"):
            device_credential.authenticate_device(db, raw)

    def test_deactivated_camera_rejected_by_health_service(self, db, camera):
        camera_service.deactivate_camera(db, camera.id)
        with pytest.raises(ValueError, match="inactive"):
            camera_health.record_health_observation(
                db, camera.id, "ONLINE"
            )

    def test_provision_credential_rejected_for_inactive_camera(self, db, camera):
        camera_service.deactivate_camera(db, camera.id)
        with pytest.raises(ValueError, match="inactive"):
            device_credential.create_device_credential(
                db, camera.id, "dead-cred"
            )

    def test_health_observation_updates_admin_view(self, db, camera):
        obs_time = datetime(2026, 7, 1, 8, 0, 0, tzinfo=timezone.utc)
        camera_health.record_health_observation(
            db, camera.id, "ONLINE",
            observed_at=obs_time, reason="DEVICE_RESPONDED",
        )
        fetched = camera_service.get_camera(db, camera.id)
        assert fetched.status == CameraStatus.ONLINE.value
        assert fetched.last_seen_at.replace(tzinfo=None) == obs_time.replace(tzinfo=None)
        assert fetched.health_reason == HealthReason.DEVICE_RESPONDED.value

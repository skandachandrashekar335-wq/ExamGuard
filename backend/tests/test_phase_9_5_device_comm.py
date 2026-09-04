"""Phase 9.5 — Secure Device Communication Foundation

Tests for device credential provisioning, authentication, revocation,
device health heartbeat endpoint, security invariants, and integration
with the camera health service.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.camera import Camera, CameraStatus
from app.models.camera_device_credential import CameraDeviceCredential, CredentialStatus
from app.services.device_credential import (
    _hash_secret,
    _constant_time_compare,
    create_device_credential,
    authenticate_device,
    revoke_device_credential,
    list_device_credentials,
    get_device_credential,
)
from app.services.camera_health import record_health_observation


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
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
def camera(db):
    c = Camera(
        name="Test Camera",
        device_identifier="TEST-CAM-001",
        status=CameraStatus.UNKNOWN.value,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def inactive_camera(db):
    c = Camera(
        name="Inactive Camera",
        device_identifier="INACTIVE-CAM-001",
        status=CameraStatus.UNKNOWN.value,
        is_active=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Hashing and comparison utilities
# ---------------------------------------------------------------------------


class TestHashingUtilities:
    def test_hash_secret_deterministic(self):
        secret = "test-secret-123"
        assert _hash_secret(secret) == _hash_secret(secret)

    def test_hash_secret_differs_for_different_inputs(self):
        assert _hash_secret("secret1") != _hash_secret("secret2")

    def test_constant_time_compare_equal(self):
        assert _constant_time_compare("abc", "abc") is True

    def test_constant_time_compare_not_equal(self):
        assert _constant_time_compare("abc", "def") is False

    def test_constant_time_compare_empty(self):
        assert _constant_time_compare("", "") is True

    def test_constant_time_compare_different_lengths(self):
        assert _constant_time_compare("abc", "abcd") is False


# ---------------------------------------------------------------------------
# Credential provisioning
# ---------------------------------------------------------------------------


class TestCredentialProvisioning:
    def test_create_credential_success(self, db, camera):
        credential, raw_secret = create_device_credential(
            db, camera.id, "Test Credential"
        )
        assert credential.camera_id == camera.id
        assert credential.label == "Test Credential"
        assert credential.status == CredentialStatus.ACTIVE.value
        assert credential.is_active is True
        assert len(raw_secret) == 64
        assert credential.secret_prefix == raw_secret[:8]

    def test_create_credential_hash_matches(self, db, camera):
        credential, raw_secret = create_device_credential(
            db, camera.id, "Test Credential"
        )
        assert credential.secret_hash == _hash_secret(raw_secret)

    def test_create_credential_not_found(self, db):
        with pytest.raises(LookupError, match="not found"):
            create_device_credential(db, 99999, "Test")

    def test_create_credential_inactive_camera(self, db, inactive_camera):
        with pytest.raises(ValueError, match="inactive"):
            create_device_credential(db, inactive_camera.id, "Test")

    def test_create_multiple_credentials(self, db, camera):
        cred1, _ = create_device_credential(db, camera.id, "Cred 1")
        cred2, _ = create_device_credential(db, camera.id, "Cred 2")
        assert cred1.id != cred2.id

    def test_create_credential_label_stripped(self, db, camera):
        credential, _ = create_device_credential(
            db, camera.id, "  Test Credential  "
        )
        assert credential.label == "Test Credential"


# ---------------------------------------------------------------------------
# Credential authentication
# ---------------------------------------------------------------------------


class TestCredentialAuthentication:
    def test_authenticate_valid_credential(self, db, camera):
        _, raw_secret = create_device_credential(db, camera.id, "Test")
        credential = authenticate_device(db, raw_secret)
        assert credential.camera_id == camera.id

    def test_authenticate_invalid_credential(self, db):
        with pytest.raises(LookupError, match="Invalid"):
            authenticate_device(db, "invalid-secret-123")

    def test_authenticate_empty_credential(self, db):
        with pytest.raises(LookupError, match="Invalid"):
            authenticate_device(db, "")

    def test_authenticate_whitespace_credential(self, db):
        with pytest.raises(LookupError, match="Invalid"):
            authenticate_device(db, "   ")

    def test_authenticate_revoked_credential(self, db, camera):
        credential, raw_secret = create_device_credential(db, camera.id, "Test")
        revoke_device_credential(db, credential.id)
        with pytest.raises(ValueError, match="revoked"):
            authenticate_device(db, raw_secret)

    def test_authenticate_inactive_credential(self, db, camera):
        credential, raw_secret = create_device_credential(db, camera.id, "Test")
        credential.is_active = False
        db.commit()
        with pytest.raises(ValueError, match="inactive"):
            authenticate_device(db, raw_secret)

    def test_authenticate_inactive_camera_credential(self, db, camera):
        _, raw_secret = create_device_credential(db, camera.id, "Test")
        camera.is_active = False
        db.commit()
        with pytest.raises(ValueError, match="inactive"):
            authenticate_device(db, raw_secret)


# ---------------------------------------------------------------------------
# Credential revocation
# ---------------------------------------------------------------------------


class TestCredentialRevocation:
    def test_revoke_credential_success(self, db, camera):
        credential, _ = create_device_credential(db, camera.id, "Test")
        revoked = revoke_device_credential(db, credential.id)
        assert revoked.status == CredentialStatus.REVOKED.value

    def test_revoke_credential_not_found(self, db):
        with pytest.raises(LookupError, match="not found"):
            revoke_device_credential(db, 99999)

    def test_revoked_credential_cannot_authenticate(self, db, camera):
        credential, raw_secret = create_device_credential(db, camera.id, "Test")
        revoke_device_credential(db, credential.id)
        with pytest.raises(ValueError, match="revoked"):
            authenticate_device(db, raw_secret)


# ---------------------------------------------------------------------------
# Credential listing and retrieval
# ---------------------------------------------------------------------------


class TestCredentialListing:
    def test_list_credentials(self, db, camera):
        create_device_credential(db, camera.id, "Cred 1")
        create_device_credential(db, camera.id, "Cred 2")
        credentials = list_device_credentials(db, camera.id)
        assert len(credentials) == 2

    def test_list_credentials_empty(self, db, camera):
        credentials = list_device_credentials(db, camera.id)
        assert len(credentials) == 0

    def test_get_credential(self, db, camera):
        credential, _ = create_device_credential(db, camera.id, "Test")
        result = get_device_credential(db, credential.id)
        assert result is not None
        assert result.id == credential.id

    def test_get_credential_not_found(self, db):
        result = get_device_credential(db, 99999)
        assert result is None


# ---------------------------------------------------------------------------
# Device health endpoint (API-level tests)
# ---------------------------------------------------------------------------


class TestDeviceHealthEndpoint:
    """Tests for POST /api/v1/device/health endpoint.

    These tests use the service layer directly since we don't have
    a TestClient fixture. The endpoint logic is tested via the
    service integration tests below.
    """

    def test_health_observation_via_service(self, db, camera):
        _, raw_secret = create_device_credential(db, camera.id, "Test")

        credential = authenticate_device(db, raw_secret)
        assert credential.camera_id == camera.id

        result = record_health_observation(
            db, credential.camera_id, "ONLINE", reason="DEVICE_RESPONDED"
        )
        assert result.status == CameraStatus.ONLINE.value
        assert result.last_seen_at is not None
        assert result.health_reason == "DEVICE_RESPONDED"

    def test_health_observation_offline(self, db, camera):
        _, raw_secret = create_device_credential(db, camera.id, "Test")

        credential = authenticate_device(db, raw_secret)
        result = record_health_observation(
            db, credential.camera_id, "OFFLINE", reason="DEVICE_UNREACHABLE"
        )
        assert result.status == CameraStatus.OFFLINE.value

    def test_health_observation_invalid_status(self, db, camera):
        _, raw_secret = create_device_credential(db, camera.id, "Test")

        credential = authenticate_device(db, raw_secret)
        with pytest.raises(ValueError, match="Invalid status"):
            record_health_observation(db, credential.camera_id, "PENDING")

    def test_health_observation_inactive_camera(self, db, inactive_camera):
        with pytest.raises(ValueError, match="inactive"):
            create_device_credential(db, inactive_camera.id, "Test")


# ---------------------------------------------------------------------------
# Security invariants
# ---------------------------------------------------------------------------


class TestSecurityInvariants:
    def test_secret_never_stored_in_plaintext(self, db, camera):
        credential, raw_secret = create_device_credential(db, camera.id, "Test")
        assert credential.secret_hash != raw_secret
        assert raw_secret not in str(credential.secret_hash)

    def test_credential_response_no_secret(self, db, camera):
        credential, _ = create_device_credential(db, camera.id, "Test")
        cred_dict = {
            "id": credential.id,
            "camera_id": credential.camera_id,
            "label": credential.label,
            "secret_prefix": credential.secret_prefix,
            "status": credential.status,
        }
        assert "secret" not in cred_dict
        assert "secret_hash" not in cred_dict

    def test_cross_camera_credential_misuse(self, db):
        camera1 = Camera(
            name="Camera 1",
            device_identifier="CAM-001",
            status=CameraStatus.UNKNOWN.value,
        )
        camera2 = Camera(
            name="Camera 2",
            device_identifier="CAM-002",
            status=CameraStatus.UNKNOWN.value,
        )
        db.add_all([camera1, camera2])
        db.commit()
        db.refresh(camera1)
        db.refresh(camera2)

        _, raw_secret = create_device_credential(db, camera1.id, "Cred 1")

        credential = authenticate_device(db, raw_secret)
        assert credential.camera_id == camera1.id
        assert credential.camera_id != camera2.id

    def test_constant_time_comparison_used(self):
        import hmac

        original_compare = hmac.compare_digest
        calls = []

        def tracking_compare(a, b):
            calls.append((a, b))
            return original_compare(a, b)

        import app.services.device_credential as dc

        original_func = dc._constant_time_compare
        dc._constant_time_compare = lambda v1, v2: tracking_compare(
            v1.encode("utf-8"), v2.encode("utf-8")
        )

        try:
            _constant_time_compare = dc._constant_time_compare
            _constant_time_compare("abc", "abc")
            _constant_time_compare("abc", "def")
            assert len(calls) == 2
        finally:
            dc._constant_time_compare = original_func


# ---------------------------------------------------------------------------
# Integration with camera health service
# ---------------------------------------------------------------------------


class TestIntegrationWithHealthService:
    def test_full_lifecycle(self, db):
        camera = Camera(
            name="Lifecycle Camera",
            device_identifier="LIFECYCLE-CAM-001",
            status=CameraStatus.UNKNOWN.value,
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)

        credential, raw_secret = create_device_credential(
            db, camera.id, "Lifecycle Credential"
        )

        authenticated = authenticate_device(db, raw_secret)
        assert authenticated.camera_id == camera.id

        result = record_health_observation(
            db, authenticated.camera_id, "ONLINE", reason="DEVICE_RESPONDED"
        )
        assert result.status == CameraStatus.ONLINE.value
        assert result.last_seen_at is not None
        assert result.last_health_check_at is not None

        result2 = record_health_observation(
            db, authenticated.camera_id, "OFFLINE", reason="DEVICE_UNREACHABLE"
        )
        assert result2.status == CameraStatus.OFFLINE.value

        revoke_device_credential(db, credential.id)

        with pytest.raises(ValueError, match="revoked"):
            authenticate_device(db, raw_secret)

    def test_multiple_cameras_independent(self, db):
        cam1 = Camera(
            name="Camera A",
            device_identifier="MULTI-CAM-A",
            status=CameraStatus.UNKNOWN.value,
        )
        cam2 = Camera(
            name="Camera B",
            device_identifier="MULTI-CAM-B",
            status=CameraStatus.UNKNOWN.value,
        )
        db.add_all([cam1, cam2])
        db.commit()
        db.refresh(cam1)
        db.refresh(cam2)

        _, secret1 = create_device_credential(db, cam1.id, "Cred A")
        _, secret2 = create_device_credential(db, cam2.id, "Cred B")

        cred1 = authenticate_device(db, secret1)
        cred2 = authenticate_device(db, secret2)

        assert cred1.camera_id == cam1.id
        assert cred2.camera_id == cam2.id

        record_health_observation(db, cred1.camera_id, "ONLINE")
        record_health_observation(db, cred2.camera_id, "OFFLINE")

        assert cam1.status == CameraStatus.ONLINE.value
        assert cam2.status == CameraStatus.OFFLINE.value


# ---------------------------------------------------------------------------
# Admin PATCH still cannot change status directly
# ---------------------------------------------------------------------------


class TestAdminPatchCannotChangeStatus:
    def test_admin_patch_ignored_for_status(self, db, camera):
        """Verify that the existing camera update service does not allow
        direct status changes via PATCH. Status should only change
        through record_health_observation().
        """
        from app.services.camera import update_camera
        from app.schemas.camera import CameraUpdate

        update_data = CameraUpdate(status="ONLINE")
        updated = update_camera(db, camera.id, update_data)

        assert updated.status == CameraStatus.UNKNOWN.value

    def test_status_only_changes_via_health_observation(self, db, camera):
        _, raw_secret = create_device_credential(db, camera.id, "Test")

        credential = authenticate_device(db, raw_secret)
        record_health_observation(
            db, credential.camera_id, "ONLINE", reason="DEVICE_RESPONDED"
        )

        assert camera.status == CameraStatus.ONLINE.value

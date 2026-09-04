"""Phase 9.4 — Camera Device Health & Status.

Tests for health observation recording, status transitions, timestamp handling,
reason categories, inactive camera rejection, and health state retrieval.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.camera import Camera, CameraStatus, HealthReason
from app.services.camera_health import (
    record_health_observation,
    get_camera_health,
    VALID_OBSERVATION_STATUSES,
)


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
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_new_camera_is_unknown(self, camera):
        assert camera.status == CameraStatus.UNKNOWN.value

    def test_new_camera_has_no_health_fields(self, camera):
        assert camera.last_seen_at is None
        assert camera.last_health_check_at is None
        assert camera.health_reason is None


# ---------------------------------------------------------------------------
# Valid ONLINE observation
# ---------------------------------------------------------------------------


class TestOnlineObservation:
    def test_online_sets_status(self, db, camera):
        result = record_health_observation(db, camera.id, "ONLINE")
        assert result.status == CameraStatus.ONLINE.value

    def test_online_sets_last_seen(self, db, camera):
        result = record_health_observation(db, camera.id, "ONLINE")
        assert result.last_seen_at is not None

    def test_online_sets_last_health_check(self, db, camera):
        result = record_health_observation(db, camera.id, "ONLINE")
        assert result.last_health_check_at is not None

    def test_online_with_observed_at(self, db, camera):
        ts = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = record_health_observation(db, camera.id, "ONLINE", observed_at=ts)
        assert result.last_seen_at is not None
        assert result.last_seen_at.replace(tzinfo=None) == ts.replace(tzinfo=None)

    def test_online_with_reason(self, db, camera):
        result = record_health_observation(
            db, camera.id, "ONLINE", reason="DEVICE_RESPONDED"
        )
        assert result.health_reason == HealthReason.DEVICE_RESPONDED.value

    def test_online_lowercase_input(self, db, camera):
        result = record_health_observation(db, camera.id, "online")
        assert result.status == CameraStatus.ONLINE.value

    def test_online_with_whitespace(self, db, camera):
        result = record_health_observation(db, camera.id, "  ONLINE  ")
        assert result.status == CameraStatus.ONLINE.value


# ---------------------------------------------------------------------------
# Valid OFFLINE observation
# ---------------------------------------------------------------------------


class TestOfflineObservation:
    def test_offline_sets_status(self, db, camera):
        result = record_health_observation(db, camera.id, "OFFLINE")
        assert result.status == CameraStatus.OFFLINE.value

    def test_offline_does_not_update_last_seen(self, db, camera):
        result = record_health_observation(db, camera.id, "OFFLINE")
        assert result.last_seen_at is None

    def test_offline_with_reason(self, db, camera):
        result = record_health_observation(
            db, camera.id, "OFFLINE", reason="DEVICE_UNREACHABLE"
        )
        assert result.health_reason == HealthReason.DEVICE_UNREACHABLE.value

    def test_offline_preserves_previous_last_seen(self, db, camera):
        ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        record_health_observation(db, camera.id, "ONLINE", observed_at=ts)
        result = record_health_observation(db, camera.id, "OFFLINE")
        assert result.last_seen_at is not None
        assert result.last_seen_at.replace(tzinfo=None) == ts.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Repeated observations
# ---------------------------------------------------------------------------


class TestRepeatedObservations:
    def test_online_then_offline(self, db, camera):
        record_health_observation(db, camera.id, "ONLINE")
        result = record_health_observation(db, camera.id, "OFFLINE")
        assert result.status == CameraStatus.OFFLINE.value

    def test_offline_then_online(self, db, camera):
        record_health_observation(db, camera.id, "OFFLINE")
        result = record_health_observation(db, camera.id, "ONLINE")
        assert result.status == CameraStatus.ONLINE.value

    def test_online_then_online_updates_last_seen(self, db, camera):
        ts1 = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        record_health_observation(db, camera.id, "ONLINE", observed_at=ts1)
        result = record_health_observation(db, camera.id, "ONLINE", observed_at=ts2)
        assert result.last_seen_at is not None
        assert result.last_seen_at.replace(tzinfo=None) == ts2.replace(tzinfo=None)

    def test_reason_updates_on_each_observation(self, db, camera):
        record_health_observation(
            db, camera.id, "ONLINE", reason="DEVICE_RESPONDED"
        )
        result = record_health_observation(
            db, camera.id, "OFFLINE", reason="DEVICE_UNREACHABLE"
        )
        assert result.health_reason == HealthReason.DEVICE_UNREACHABLE.value


# ---------------------------------------------------------------------------
# Invalid camera
# ---------------------------------------------------------------------------


class TestInvalidCamera:
    def test_camera_not_found(self, db):
        with pytest.raises(LookupError, match="not found"):
            record_health_observation(db, 99999, "ONLINE")

    def test_camera_not_found_health(self, db):
        result = get_camera_health(db, 99999)
        assert result is None


# ---------------------------------------------------------------------------
# Invalid status
# ---------------------------------------------------------------------------


class TestInvalidStatus:
    def test_invalid_status_value(self, db, camera):
        with pytest.raises(ValueError, match="Invalid status"):
            record_health_observation(db, camera.id, "PENDING")

    def test_empty_status(self, db, camera):
        with pytest.raises(ValueError, match="Invalid status"):
            record_health_observation(db, camera.id, "")

    def test_unknown_not_allowed(self, db, camera):
        with pytest.raises(ValueError, match="Invalid status"):
            record_health_observation(db, camera.id, "UNKNOWN")

    def test_disabled_not_allowed(self, db, camera):
        with pytest.raises(ValueError, match="Invalid status"):
            record_health_observation(db, camera.id, "DISABLED")


# ---------------------------------------------------------------------------
# Invalid reason
# ---------------------------------------------------------------------------


class TestInvalidReason:
    def test_invalid_reason_value(self, db, camera):
        with pytest.raises(ValueError, match="Invalid reason"):
            record_health_observation(
                db, camera.id, "ONLINE", reason="SOME_RANDOM_REASON"
            )

    def test_empty_string_reason_rejected(self, db, camera):
        with pytest.raises(ValueError, match="Invalid reason"):
            record_health_observation(db, camera.id, "ONLINE", reason="")


# ---------------------------------------------------------------------------
# Timestamp validation
# ---------------------------------------------------------------------------


class TestTimestampValidation:
    def test_future_timestamp_rejected(self, db, camera):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        with pytest.raises(ValueError, match="future"):
            record_health_observation(db, camera.id, "ONLINE", observed_at=future)

    def test_naive_timestamp_gets_utc(self, db, camera):
        naive = datetime(2026, 6, 15, 12, 0, 0)
        result = record_health_observation(db, camera.id, "ONLINE", observed_at=naive)
        assert result.last_seen_at is not None
        assert result.last_seen_at.replace(tzinfo=None) == naive


# ---------------------------------------------------------------------------
# Inactive camera
# ---------------------------------------------------------------------------


class TestInactiveCamera:
    def test_inactive_camera_rejected(self, db, inactive_camera):
        with pytest.raises(ValueError, match="inactive"):
            record_health_observation(db, inactive_camera.id, "ONLINE")

    def test_inactive_camera_health_retrievable(self, db, inactive_camera):
        result = get_camera_health(db, inactive_camera.id)
        assert result is not None
        assert result.is_active is False


# ---------------------------------------------------------------------------
# Health retrieval
# ---------------------------------------------------------------------------


class TestHealthRetrieval:
    def test_get_health_returns_camera(self, db, camera):
        result = get_camera_health(db, camera.id)
        assert result is not None
        assert result.id == camera.id

    def test_health_reflects_observation(self, db, camera):
        record_health_observation(db, camera.id, "ONLINE", reason="DEVICE_RESPONDED")
        result = get_camera_health(db, camera.id)
        assert result.status == CameraStatus.ONLINE.value
        assert result.health_reason == HealthReason.DEVICE_RESPONDED.value
        assert result.last_seen_at is not None
        assert result.last_health_check_at is not None


# ---------------------------------------------------------------------------
# Valid status/reason sets
# ---------------------------------------------------------------------------


class TestValidSets:
    def test_valid_observation_statuses(self):
        assert VALID_OBSERVATION_STATUSES == {"ONLINE", "OFFLINE"}

    def test_all_health_reasons_are_valid(self):
        for r in HealthReason:
            assert r.value in {reason.value for reason in HealthReason}

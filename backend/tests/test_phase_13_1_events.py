"""Phase 13.1 — Real-Time Event Domain Tests.

Tests for the monitoring event domain: MonitoringEvent, enums,
severity mapping, serialization, payload safety, filters.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.schemas.monitoring import (
    MonitoringAlertListResponse,
    MonitoringAlertSchema,
    MonitoringEventListResponse,
    MonitoringEventSchema,
    MonitoringFilterParams,
    MonitoringStatusResponse,
)
from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
    MonitoringEvent,
    MonitoringFilter,
    _SENSITIVE_KEYS,
    default_severity,
    event_category,
    severity_order,
)


# ---------------------------------------------------------------------------
# Event Creation & Core Properties
# ---------------------------------------------------------------------------


class TestMonitoringEvent:
    def test_event_creation(self):
        """Basic event creation with required fields."""
        now = datetime.now(timezone.utc)
        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=42,
            timestamp=now,
        )
        assert event.event_type == EventType.ENTRY_GRANTED
        assert event.entity_type == "EntryVerification"
        assert event.entity_id == 42
        assert event.timestamp == now
        assert isinstance(event.event_id, uuid.UUID)

    def test_uuid_uniqueness(self):
        """Each event gets a unique UUID."""
        now = datetime.now(timezone.utc)
        events = [
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=now,
            )
            for _ in range(100)
        ]
        ids = {e.event_id for e in events}
        assert len(ids) == 100

    def test_immutability(self):
        """MonitoringEvent is frozen — field assignment raises."""
        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            event.entity_id = 999  # type: ignore[misc]

    def test_optional_fields_default_none(self):
        """Optional fields default to None."""
        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.exam_id is None
        assert event.hall_id is None
        assert event.student_id is None
        assert event.entry_point_id is None
        assert event.payload == {}

    def test_optional_fields_set(self):
        """Optional fields can be set."""
        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
            exam_id=3,
            hall_id=5,
            student_id=7,
            entry_point_id=9,
        )
        assert event.exam_id == 3
        assert event.hall_id == 5
        assert event.student_id == 7
        assert event.entry_point_id == 9


# ---------------------------------------------------------------------------
# Enum Validation
# ---------------------------------------------------------------------------


class TestEnums:
    def test_event_type_values(self):
        """All expected event types exist."""
        expected = {
            "ENTRY_CREATED", "ENTRY_BEGAN", "ENTRY_GRANTED", "ENTRY_DENIED",
            "ENTRY_ESCALATED", "ENTRY_RESOLVED",
            "SIGNAL_DETECTED", "RISK_ASSESSED", "RISK_ELEVATED", "RISK_HIGH",
            "RISK_CRITICAL",
            "ATTENDANCE_RECORDED", "ATTENDANCE_CORRECTED",
            "CAMERA_OFFLINE", "CAMERA_ONLINE",
            "HEARTBEAT",
        }
        actual = {e.value for e in EventType}
        assert actual == expected

    def test_event_category_values(self):
        """All expected categories exist."""
        expected = {"ENTRY", "RISK", "ATTENDANCE", "CAMERA", "SYSTEM"}
        actual = {c.value for c in EventCategory}
        assert actual == expected

    def test_severity_values(self):
        """All expected severity levels exist."""
        expected = {"INFO", "WARNING", "CRITICAL"}
        actual = {s.value for s in EventSeverity}
        assert actual == expected

    def test_event_category_mapping(self):
        """Each event type maps to the correct category."""
        assert event_category(EventType.ENTRY_GRANTED) == EventCategory.ENTRY
        assert event_category(EventType.RISK_CRITICAL) == EventCategory.RISK
        assert event_category(EventType.ATTENDANCE_RECORDED) == EventCategory.ATTENDANCE
        assert event_category(EventType.CAMERA_OFFLINE) == EventCategory.CAMERA
        assert event_category(EventType.HEARTBEAT) == EventCategory.SYSTEM


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


class TestSeverity:
    def test_severity_ordering(self):
        """INFO < WARNING < CRITICAL."""
        assert severity_order(EventSeverity.INFO) < severity_order(EventSeverity.WARNING)
        assert severity_order(EventSeverity.WARNING) < severity_order(EventSeverity.CRITICAL)

    def test_default_severity_entry_escalated(self):
        """ENTRY_ESCALATED is WARNING."""
        assert default_severity(EventType.ENTRY_ESCALATED) == EventSeverity.WARNING

    def test_default_severity_risk_levels(self):
        """Risk events map to correct severity."""
        assert default_severity(EventType.RISK_ELEVATED) == EventSeverity.WARNING
        assert default_severity(EventType.RISK_HIGH) == EventSeverity.WARNING
        assert default_severity(EventType.RISK_CRITICAL) == EventSeverity.CRITICAL

    def test_default_severity_camera_offline(self):
        """CAMERA_OFFLINE is WARNING."""
        assert default_severity(EventType.CAMERA_OFFLINE) == EventSeverity.WARNING

    def test_default_severity_info_events(self):
        """Normal events are INFO."""
        for et in [
            EventType.ENTRY_CREATED, EventType.ENTRY_BEGAN,
            EventType.ENTRY_GRANTED, EventType.ENTRY_DENIED,
            EventType.ENTRY_RESOLVED,
            EventType.SIGNAL_DETECTED, EventType.RISK_ASSESSED,
            EventType.ATTENDANCE_RECORDED, EventType.ATTENDANCE_CORRECTED,
            EventType.CAMERA_ONLINE, EventType.HEARTBEAT,
        ]:
            assert default_severity(et) == EventSeverity.INFO, f"{et} should be INFO"

    def test_auto_derived_category_and_severity(self):
        """Category and severity are derived from event_type, not set manually."""
        event = MonitoringEvent(
            event_type=EventType.ENTRY_ESCALATED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.category == EventCategory.ENTRY
        assert event.severity == EventSeverity.WARNING


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_minimal(self):
        """Serialization with only required fields."""
        ts = datetime(2026, 9, 5, 10, 30, 0, tzinfo=timezone.utc)
        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=42,
            timestamp=ts,
        )
        d = event.to_dict()
        assert d["event_type"] == "ENTRY_GRANTED"
        assert d["category"] == "ENTRY"
        assert d["entity_type"] == "EntryVerification"
        assert d["entity_id"] == 42
        assert d["timestamp"] == "2026-09-05T10:30:00+00:00"
        assert d["severity"] == "INFO"
        assert "exam_id" not in d
        assert "hall_id" not in d
        assert "student_id" not in d
        assert "entry_point_id" not in d
        assert "payload" not in d

    def test_to_dict_full(self):
        """Serialization with all optional fields."""
        ts = datetime(2026, 9, 5, 10, 30, 0, tzinfo=timezone.utc)
        event = MonitoringEvent(
            event_type=EventType.ENTRY_ESCALATED,
            entity_type="EntryVerification",
            entity_id=42,
            timestamp=ts,
            exam_id=3,
            hall_id=5,
            student_id=7,
            entry_point_id=9,
            payload={"reason": "suspicious behavior"},
        )
        d = event.to_dict()
        assert d["exam_id"] == 3
        assert d["hall_id"] == 5
        assert d["student_id"] == 7
        assert d["entry_point_id"] == 9
        assert d["payload"] == {"reason": "suspicious behavior"}

    def test_to_dict_uuid_serialized(self):
        """UUID is serialized as string."""
        event = MonitoringEvent(
            event_type=EventType.HEARTBEAT,
            entity_type="System",
            entity_id=0,
            timestamp=datetime.now(timezone.utc),
        )
        d = event.to_dict()
        parsed = uuid.UUID(d["event_id"])
        assert parsed == event.event_id

    def test_to_dict_datetime_serialized(self):
        """Datetime is serialized as ISO format."""
        ts = datetime(2026, 9, 5, 10, 30, 0, tzinfo=timezone.utc)
        event = MonitoringEvent(
            event_type=EventType.HEARTBEAT,
            entity_type="System",
            entity_id=0,
            timestamp=ts,
        )
        d = event.to_dict()
        assert "2026-09-05T10:30:00" in d["timestamp"]


# ---------------------------------------------------------------------------
# Payload Safety
# ---------------------------------------------------------------------------


class TestPayloadSafety:
    def test_rejects_face_image(self):
        """Payload with face_image is rejected."""
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
                payload={"face_image": "base64data"},
            )

    def test_rejects_face_embedding(self):
        """Payload with face_embedding is rejected."""
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
                payload={"face_embedding": [0.1, 0.2]},
            )

    def test_rejects_api_key(self):
        """Payload with api_key is rejected."""
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.HEARTBEAT,
                entity_type="System",
                entity_id=0,
                timestamp=datetime.now(timezone.utc),
                payload={"api_key": "secret123"},
            )

    def test_rejects_database_url(self):
        """Payload with database_url is rejected."""
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.HEARTBEAT,
                entity_type="System",
                entity_id=0,
                timestamp=datetime.now(timezone.utc),
                payload={"database_url": "postgresql://..."},
            )

    def test_rejects_stack_trace(self):
        """Payload with stack_trace is rejected."""
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.HEARTBEAT,
                entity_type="System",
                entity_id=0,
                timestamp=datetime.now(timezone.utc),
                payload={"stack_trace": "..."},
            )

    def test_rejects_raw_ocr(self):
        """Payload with raw_ocr is rejected."""
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
                payload={"raw_ocr": "extracted text"},
            )

    def test_rejects_secrets(self):
        """Payload with secrets is rejected."""
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.HEARTBEAT,
                entity_type="System",
                entity_id=0,
                timestamp=datetime.now(timezone.utc),
                payload={"secrets": {"key": "val"}},
            )

    def test_safe_payload_accepted(self):
        """Operational payloads are accepted."""
        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
            payload={"hall_id": 5, "seat_number": "A01", "method": "VERIFIED_ENTRY"},
        )
        assert event.payload["hall_id"] == 5


# ---------------------------------------------------------------------------
# Filter Matching
# ---------------------------------------------------------------------------


class TestMonitoringFilter:
    def _make_event(self, **kwargs) -> MonitoringEvent:
        defaults = {
            "event_type": EventType.ENTRY_GRANTED,
            "entity_type": "EntryVerification",
            "entity_id": 1,
            "timestamp": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        return MonitoringEvent(**defaults)

    def test_empty_filter_matches_all(self):
        """Empty filter matches any event."""
        f = MonitoringFilter()
        event = self._make_event()
        assert f.matches(event) is True

    def test_exam_id_filter(self):
        """Filter by exam_id."""
        f = MonitoringFilter(exam_id=3)
        assert f.matches(self._make_event(exam_id=3)) is True
        assert f.matches(self._make_event(exam_id=4)) is False
        assert f.matches(self._make_event()) is False

    def test_hall_id_filter(self):
        """Filter by hall_id."""
        f = MonitoringFilter(hall_id=5)
        assert f.matches(self._make_event(hall_id=5)) is True
        assert f.matches(self._make_event(hall_id=6)) is False

    def test_category_filter(self):
        """Filter by category."""
        f = MonitoringFilter(category=EventCategory.ENTRY)
        assert f.matches(self._make_event(event_type=EventType.ENTRY_GRANTED)) is True
        assert f.matches(self._make_event(event_type=EventType.RISK_CRITICAL)) is False

    def test_event_type_filter(self):
        """Filter by specific event type."""
        f = MonitoringFilter(event_type=EventType.ENTRY_ESCALATED)
        assert f.matches(self._make_event(event_type=EventType.ENTRY_ESCALATED)) is True
        assert f.matches(self._make_event(event_type=EventType.ENTRY_GRANTED)) is False

    def test_min_severity_filter(self):
        """Filter by minimum severity."""
        f = MonitoringFilter(min_severity=EventSeverity.WARNING)
        assert f.matches(self._make_event(event_type=EventType.ENTRY_GRANTED)) is False
        assert f.matches(self._make_event(event_type=EventType.ENTRY_ESCALATED)) is True
        assert f.matches(self._make_event(event_type=EventType.RISK_CRITICAL)) is True

    def test_combined_filters(self):
        """Multiple filters must all pass."""
        f = MonitoringFilter(
            exam_id=3,
            category=EventCategory.ENTRY,
            min_severity=EventSeverity.WARNING,
        )
        # Matches: exam=3, category=ENTRY, severity>=WARNING
        assert f.matches(self._make_event(
            event_type=EventType.ENTRY_ESCALATED, exam_id=3,
        )) is True
        # Fails: wrong exam
        assert f.matches(self._make_event(
            event_type=EventType.ENTRY_ESCALATED, exam_id=4,
        )) is False
        # Fails: wrong category
        assert f.matches(self._make_event(
            event_type=EventType.RISK_CRITICAL, exam_id=3,
        )) is False
        # Fails: severity too low
        assert f.matches(self._make_event(
            event_type=EventType.ENTRY_GRANTED, exam_id=3,
        )) is False

    def test_severity_filter_boundary(self):
        """INFO < WARNING < CRITICAL boundary tests."""
        f_min_warning = MonitoringFilter(min_severity=EventSeverity.WARNING)
        f_min_critical = MonitoringFilter(min_severity=EventSeverity.CRITICAL)

        # INFO event
        info_event = self._make_event(event_type=EventType.ENTRY_GRANTED)
        assert f_min_warning.matches(info_event) is False
        assert f_min_critical.matches(info_event) is False

        # WARNING event
        warn_event = self._make_event(event_type=EventType.ENTRY_ESCALATED)
        assert f_min_warning.matches(warn_event) is True
        assert f_min_critical.matches(warn_event) is False

        # CRITICAL event
        crit_event = self._make_event(event_type=EventType.RISK_CRITICAL)
        assert f_min_warning.matches(crit_event) is True
        assert f_min_critical.matches(crit_event) is True


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class TestMonitoringSchemas:
    def test_event_schema_validation(self):
        """MonitoringEventSchema validates correctly."""
        schema = MonitoringEventSchema(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ENTRY_GRANTED,
            category=EventCategory.ENTRY,
            entity_type="EntryVerification",
            entity_id=42,
            timestamp=datetime.now(timezone.utc),
            severity=EventSeverity.INFO,
        )
        assert schema.event_type == EventType.ENTRY_GRANTED
        assert schema.entity_id == 42

    def test_event_schema_optional_fields(self):
        """MonitoringEventSchema optional fields default to None."""
        schema = MonitoringEventSchema(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ENTRY_GRANTED,
            category=EventCategory.ENTRY,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
            severity=EventSeverity.INFO,
        )
        assert schema.exam_id is None
        assert schema.hall_id is None
        assert schema.student_id is None
        assert schema.payload == {}

    def test_filter_params_schema(self):
        """MonitoringFilterParams validates correctly."""
        params = MonitoringFilterParams(
            exam_id=3,
            min_severity=EventSeverity.WARNING,
        )
        assert params.exam_id == 3
        assert params.min_severity == EventSeverity.WARNING
        assert params.hall_id is None
        assert params.category is None

    def test_status_response_schema(self):
        """MonitoringStatusResponse validates correctly."""
        status = MonitoringStatusResponse(
            active_connections=5,
            buffered_events=100,
            buffered_alerts=10,
            total_published=142,
            event_buffer_capacity=1000,
            alert_buffer_capacity=200,
            max_connections=50,
        )
        assert status.active_connections == 5
        assert status.total_published == 142
        assert status.event_buffer_capacity == 1000

    def test_alert_schema(self):
        """MonitoringAlertSchema validates correctly."""
        alert = MonitoringAlertSchema(
            alert_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
            event_type=EventType.RISK_CRITICAL,
            severity=EventSeverity.CRITICAL,
            entity_type="ProxyRiskAssessment",
            entity_id=10,
            message="Critical risk detected",
            created_at=datetime.now(timezone.utc),
        )
        assert alert.severity == EventSeverity.CRITICAL
        assert alert.message == "Critical risk detected"

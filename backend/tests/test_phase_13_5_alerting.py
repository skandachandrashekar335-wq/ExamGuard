"""Phase 13.5 — Alerting Tests.

Tests for alert classification, message generation, AlertBuffer filtering,
and integration with EventPublisher. Covers classification rules,
deterministic messages, deduplication, buffer behavior, and security.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.services.monitoring.alert_buffer import Alert, AlertBuffer, AlertFilter
from app.services.monitoring.alerting import (
    alert_message,
    alert_payload,
    alert_worthy_event_types,
    should_alert,
)
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.events import (
    EventSeverity,
    EventType,
    MonitoringEvent,
)


def _make_event(**kwargs) -> MonitoringEvent:
    defaults = {
        "event_type": EventType.ENTRY_GRANTED,
        "entity_type": "EntryVerification",
        "entity_id": 1,
        "timestamp": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return MonitoringEvent(**defaults)


def _make_alert(**kwargs) -> Alert:
    defaults = {
        "event_id": uuid.uuid4(),
        "event_type": EventType.ENTRY_ESCALATED,
        "severity": EventSeverity.WARNING,
        "message": "Test alert",
        "entity_type": "EntryVerification",
        "entity_id": 1,
    }
    defaults.update(kwargs)
    return Alert(**defaults)


# ---------------------------------------------------------------------------
# Alert Classification
# ---------------------------------------------------------------------------


class TestShouldAlert:
    def test_info_no_alert(self):
        """INFO events never generate alerts."""
        event = _make_event(event_type=EventType.ENTRY_GRANTED)
        assert should_alert(event) is False

    def test_warning_generates_alert(self):
        """WARNING events generate alerts."""
        event = _make_event(event_type=EventType.ENTRY_ESCALATED)
        assert should_alert(event) is True

    def test_critical_generates_alert(self):
        """CRITICAL events generate alerts."""
        event = _make_event(event_type=EventType.RISK_CRITICAL)
        assert should_alert(event) is True

    def test_entry_escalated(self):
        """ENTRY_ESCALATED is alert-worthy."""
        event = _make_event(event_type=EventType.ENTRY_ESCALATED)
        assert should_alert(event) is True

    def test_risk_elevated(self):
        """RISK_ELEVATED is alert-worthy."""
        event = _make_event(event_type=EventType.RISK_ELEVATED)
        assert should_alert(event) is True

    def test_risk_high(self):
        """RISK_HIGH is alert-worthy."""
        event = _make_event(event_type=EventType.RISK_HIGH)
        assert should_alert(event) is True

    def test_risk_critical(self):
        """RISK_CRITICAL is alert-worthy."""
        event = _make_event(event_type=EventType.RISK_CRITICAL)
        assert should_alert(event) is True

    def test_camera_offline(self):
        """CAMERA_OFFLINE is alert-worthy."""
        event = _make_event(event_type=EventType.CAMERA_OFFLINE)
        assert should_alert(event) is True

    def test_entry_created_no_alert(self):
        """ENTRY_CREATED (INFO) does not alert."""
        event = _make_event(event_type=EventType.ENTRY_CREATED)
        assert should_alert(event) is False

    def test_entry_began_no_alert(self):
        """ENTRY_BEGAN (INFO) does not alert."""
        event = _make_event(event_type=EventType.ENTRY_BEGAN)
        assert should_alert(event) is False

    def test_entry_denied_no_alert(self):
        """ENTRY_DENIED (INFO) does not alert."""
        event = _make_event(event_type=EventType.ENTRY_DENIED)
        assert should_alert(event) is False

    def test_entry_resolved_no_alert(self):
        """ENTRY_RESOLVED (INFO) does not alert."""
        event = _make_event(event_type=EventType.ENTRY_RESOLVED)
        assert should_alert(event) is False

    def test_signal_detected_no_alert(self):
        """SIGNAL_DETECTED (INFO) does not alert."""
        event = _make_event(event_type=EventType.SIGNAL_DETECTED)
        assert should_alert(event) is False

    def test_risk_assessed_no_alert(self):
        """RISK_ASSESSED (INFO) does not alert."""
        event = _make_event(event_type=EventType.RISK_ASSESSED)
        assert should_alert(event) is False

    def test_attendance_recorded_no_alert(self):
        """ATTENDANCE_RECORDED (INFO) does not alert."""
        event = _make_event(event_type=EventType.ATTENDANCE_RECORDED)
        assert should_alert(event) is False

    def test_attendance_corrected_no_alert(self):
        """ATTENDANCE_CORRECTED (INFO) does not alert."""
        event = _make_event(event_type=EventType.ATTENDANCE_CORRECTED)
        assert should_alert(event) is False

    def test_camera_online_no_alert(self):
        """CAMERA_ONLINE (INFO) does not alert."""
        event = _make_event(event_type=EventType.CAMERA_ONLINE)
        assert should_alert(event) is False

    def test_heartbeat_no_alert(self):
        """HEARTBEAT (INFO) does not alert."""
        event = _make_event(event_type=EventType.HEARTBEAT)
        assert should_alert(event) is False

    def test_alert_worthy_set(self):
        """Alert-worthy event types are the expected set."""
        types = alert_worthy_event_types()
        assert EventType.ENTRY_ESCALATED in types
        assert EventType.RISK_ELEVATED in types
        assert EventType.RISK_HIGH in types
        assert EventType.RISK_CRITICAL in types
        assert EventType.CAMERA_OFFLINE in types
        assert len(types) == 5


# ---------------------------------------------------------------------------
# Alert Messages
# ---------------------------------------------------------------------------


class TestAlertMessages:
    def test_entry_escalated_message(self):
        """ENTRY_ESCALATED has a safe, deterministic message."""
        event = _make_event(event_type=EventType.ENTRY_ESCALATED)
        msg = alert_message(event)
        assert msg == "Entry verification requires review."

    def test_risk_elevated_message(self):
        """RISK_ELEVATED has a safe message."""
        event = _make_event(event_type=EventType.RISK_ELEVATED)
        msg = alert_message(event)
        assert msg == "Elevated proxy-risk assessment detected."

    def test_risk_high_message(self):
        """RISK_HIGH has a safe message."""
        event = _make_event(event_type=EventType.RISK_HIGH)
        msg = alert_message(event)
        assert msg == "High proxy-risk assessment detected."

    def test_risk_critical_message(self):
        """RISK_CRITICAL has a safe message."""
        event = _make_event(event_type=EventType.RISK_CRITICAL)
        msg = alert_message(event)
        assert msg == "Critical proxy-risk assessment detected."

    def test_camera_offline_message(self):
        """CAMERA_OFFLINE has a safe message."""
        event = _make_event(event_type=EventType.CAMERA_OFFLINE)
        msg = alert_message(event)
        assert msg == "Camera reported offline."

    def test_message_no_sensitive_data(self):
        """Messages contain no sensitive data."""
        event = _make_event(event_type=EventType.RISK_CRITICAL)
        msg = alert_message(event)
        assert "face_image" not in msg
        assert "should not appear" not in msg

    def test_alert_payload_safe(self):
        """Alert payload contains only safe operational data."""
        event = _make_event(
            event_type=EventType.RISK_CRITICAL,
            exam_id=1,
            hall_id=2,
            student_id=3,
        )
        payload = alert_payload(event)
        assert "exam_id" in payload
        assert "hall_id" in payload
        assert "student_id" in payload
        assert "secret" not in payload


# ---------------------------------------------------------------------------
# Alert Identity
# ---------------------------------------------------------------------------


class TestAlertIdentity:
    def test_unique_alert_id(self):
        """Each alert gets a unique alert_id."""
        a1 = _make_alert()
        a2 = _make_alert()
        assert a1.alert_id != a2.alert_id

    def test_event_id_linkage(self):
        """Alert references originating event by event_id."""
        eid = uuid.uuid4()
        alert = _make_alert(event_id=eid)
        assert alert.event_id == eid

    def test_alert_to_dict(self):
        """Alert serialization includes all fields."""
        alert = _make_alert(exam_id=3, hall_id=5, student_id=7)
        d = alert.to_dict()
        assert "alert_id" in d
        assert "event_id" in d
        assert d["exam_id"] == 3
        assert d["hall_id"] == 5
        assert d["student_id"] == 7


# ---------------------------------------------------------------------------
# AlertBuffer Filtering
# ---------------------------------------------------------------------------


class TestAlertBufferFiltering:
    def test_by_severity(self):
        """Filter alerts by severity."""
        buf = AlertBuffer(capacity=10)
        buf.append(_make_alert(severity=EventSeverity.WARNING))
        buf.append(_make_alert(severity=EventSeverity.CRITICAL))
        buf.append(_make_alert(severity=EventSeverity.WARNING))

        warnings = buf.by_severity(EventSeverity.WARNING)
        assert len(warnings) == 2
        criticals = buf.by_severity(EventSeverity.CRITICAL)
        assert len(criticals) == 1

    def test_by_event_type(self):
        """Filter alerts by event type."""
        buf = AlertBuffer(capacity=10)
        buf.append(_make_alert(event_type=EventType.ENTRY_ESCALATED))
        buf.append(_make_alert(event_type=EventType.RISK_HIGH))
        buf.append(_make_alert(event_type=EventType.ENTRY_ESCALATED))

        escalated = buf.by_event_type(EventType.ENTRY_ESCALATED)
        assert len(escalated) == 2

    def test_query_with_filter(self):
        """Query alerts with AlertFilter."""
        buf = AlertBuffer(capacity=10)
        buf.append(_make_alert(
            severity=EventSeverity.WARNING,
            event_type=EventType.ENTRY_ESCALATED,
            exam_id=1,
        ))
        buf.append(_make_alert(
            severity=EventSeverity.CRITICAL,
            event_type=EventType.RISK_CRITICAL,
            exam_id=2,
        ))
        buf.append(_make_alert(
            severity=EventSeverity.WARNING,
            event_type=EventType.ENTRY_ESCALATED,
            exam_id=1,
        ))

        f = AlertFilter(severity=EventSeverity.WARNING, exam_id=1)
        results = buf.query(f)
        assert len(results) == 2
        assert all(a.severity == EventSeverity.WARNING for a in results)
        assert all(a.exam_id == 1 for a in results)

    def test_query_no_match(self):
        """Query returning no matches gives empty list."""
        buf = AlertBuffer(capacity=10)
        buf.append(_make_alert(exam_id=1))
        f = AlertFilter(exam_id=999)
        assert buf.query(f) == []

    def test_query_limit(self):
        """Query respects limit parameter."""
        buf = AlertBuffer(capacity=100)
        for _ in range(20):
            buf.append(_make_alert())
        assert len(buf.query(AlertFilter(), limit=5)) == 5


# ---------------------------------------------------------------------------
# AlertBuffer FIFO
# ---------------------------------------------------------------------------


class TestAlertBufferFIFO:
    def test_fifo_eviction(self):
        """Oldest alerts are discarded when capacity is reached."""
        buf = AlertBuffer(capacity=3)
        for i in range(5):
            buf.append(_make_alert(entity_id=i))
        assert len(buf) == 3
        recent = buf.recent()
        assert recent[0].entity_id == 4
        assert recent[1].entity_id == 3
        assert recent[2].entity_id == 2

    def test_capacity_enforcement(self):
        """Buffer never exceeds capacity."""
        buf = AlertBuffer(capacity=5)
        for i in range(100):
            buf.append(_make_alert(entity_id=i))
        assert len(buf) == 5

    def test_invalid_capacity(self):
        """Zero capacity raises ValueError."""
        with pytest.raises(ValueError, match="capacity must be >= 1"):
            AlertBuffer(capacity=0)


# ---------------------------------------------------------------------------
# EventPublisher Integration
# ---------------------------------------------------------------------------


class TestPublisherAlertIntegration:
    def _setup(self):
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        return mgr, ebuf, abuf, pub

    def test_warning_creates_alert(self):
        """WARNING event creates alert in buffer."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.ENTRY_ESCALATED)
        pub.publish(event)
        assert len(abuf) == 1
        alert = abuf.recent(limit=1)[0]
        assert alert.severity == EventSeverity.WARNING
        assert alert.message == "Entry verification requires review."

    def test_critical_creates_alert(self):
        """CRITICAL event creates alert in buffer."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.RISK_CRITICAL)
        pub.publish(event)
        assert len(abuf) == 1
        alert = abuf.recent(limit=1)[0]
        assert alert.severity == EventSeverity.CRITICAL
        assert alert.message == "Critical proxy-risk assessment detected."

    def test_info_no_alert(self):
        """INFO event does not create alert."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.ENTRY_GRANTED)
        pub.publish(event)
        assert len(abuf) == 0

    def test_duplicate_event_no_duplicate_alert(self):
        """Same event_id published twice creates only one alert."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.ENTRY_ESCALATED)
        pub.publish(event)
        pub.publish(event)
        assert len(abuf) == 1

    def test_multiple_different_events_separate_alerts(self):
        """Different events create separate alerts."""
        _, _, abuf, pub = self._setup()
        e1 = _make_event(event_type=EventType.ENTRY_ESCALATED, entity_id=1)
        e2 = _make_event(event_type=EventType.RISK_HIGH, entity_id=2)
        pub.publish(e1)
        pub.publish(e2)
        assert len(abuf) == 2

    def test_camera_offline_creates_alert(self):
        """CAMERA_OFFLINE creates a WARNING alert."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.CAMERA_OFFLINE)
        pub.publish(event)
        assert len(abuf) == 1
        assert abuf.recent(limit=1)[0].message == "Camera reported offline."

    def test_risk_elevated_creates_alert(self):
        """RISK_ELEVATED creates a WARNING alert."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.RISK_ELEVATED)
        pub.publish(event)
        assert len(abuf) == 1
        assert "Elevated" in abuf.recent(limit=1)[0].message

    def test_risk_high_creates_alert(self):
        """RISK_HIGH creates a WARNING alert."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.RISK_HIGH)
        pub.publish(event)
        assert len(abuf) == 1
        assert "High" in abuf.recent(limit=1)[0].message

    def test_alert_preserves_event_context(self):
        """Alert preserves exam_id, hall_id, student_id from event."""
        _, _, abuf, pub = self._setup()
        event = _make_event(
            event_type=EventType.ENTRY_ESCALATED,
            exam_id=10,
            hall_id=5,
            student_id=20,
        )
        pub.publish(event)
        alert = abuf.recent(limit=1)[0]
        assert alert.exam_id == 10
        assert alert.hall_id == 5
        assert alert.student_id == 20


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class TestAlertSecurity:
    def test_monitoring_event_rejects_biometric_payload(self):
        """MonitoringEvent rejects biometric data at creation time."""
        with pytest.raises(ValueError, match="prohibited key"):
            _make_event(
                event_type=EventType.RISK_CRITICAL,
                payload={"biometric_data": "encrypted"},
            )

    def test_monitoring_event_rejects_credentials_payload(self):
        """MonitoringEvent rejects credentials at creation time."""
        with pytest.raises(ValueError, match="prohibited key"):
            _make_event(
                event_type=EventType.RISK_CRITICAL,
                payload={"api_key": "sk-12345"},
            )

    def test_monitoring_event_rejects_stack_trace_payload(self):
        """MonitoringEvent rejects stack traces at creation time."""
        with pytest.raises(ValueError, match="prohibited key"):
            _make_event(
                event_type=EventType.RISK_CRITICAL,
                payload={"stack_trace": "File \"/app/main.py\"..."},
            )

    def test_monitoring_event_rejects_raw_ocr_payload(self):
        """MonitoringEvent rejects raw OCR at creation time."""
        with pytest.raises(ValueError, match="prohibited key"):
            _make_event(
                event_type=EventType.RISK_CRITICAL,
                payload={"raw_ocr": " extracted text"},
            )

    def test_no_filesystem_paths_in_messages(self):
        """Alert messages contain no filesystem paths."""
        for event_type in alert_worthy_event_types():
            event = _make_event(event_type=event_type)
            msg = alert_message(event)
            assert "D:\\" not in msg
            assert "/home/" not in msg
            assert "/var/" not in msg

    def test_no_database_urls_in_messages(self):
        """Alert messages contain no database URLs."""
        for event_type in alert_worthy_event_types():
            event = _make_event(event_type=event_type)
            msg = alert_message(event)
            assert "postgresql://" not in msg
            assert "sqlite://" not in msg

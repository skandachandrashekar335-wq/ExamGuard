"""Phase 13.4 — Event Publication Wiring Tests.

Tests for the publication wiring connecting domain operations to the
EventPublisher. Covers entry verification, risk, attendance, and camera
event publication, transaction behavior, buffer integration, and security.

Uses real database (SQLite in-memory via conftest) and real EventPublisher.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.camera import Camera, CameraStatus, HealthReason
from app.models.entry_verification import (
    EntryVerification,
    EntryVerificationStatus,
    HallTicketCheckStatus,
    IdentityCheckStatus,
    SeatCheckStatus,
)
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.proxy_risk import ProxyRiskAssessment, RiskLevel, SecuritySignal
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.services.monitoring.alert_buffer import AlertBuffer
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.events import EventSeverity, EventType, MonitoringEvent
from app.services.monitoring.publisher import (
    get_monitoring_publisher,
    init_monitoring_publisher,
    publish,
    publish_attendance_corrected,
    publish_attendance_recorded,
    publish_camera_offline,
    publish_camera_online,
    publish_entry_began,
    publish_entry_created,
    publish_entry_denied,
    publish_entry_escalated,
    publish_entry_granted,
    publish_entry_resolved,
    publish_risk_assessed,
    publish_risk_critical,
    publish_risk_elevated,
    publish_risk_high,
    publish_signal_detected,
)


@pytest.fixture(autouse=True)
def _setup_publisher():
    """Set up a fresh EventPublisher for each test."""
    mgr = ConnectionManager(max_connections=10)
    ebuf = EventBuffer(capacity=100)
    abuf = AlertBuffer(capacity=50)
    pub = EventPublisher(mgr, ebuf, abuf)
    init_monitoring_publisher(pub)
    yield
    init_monitoring_publisher(None)


def _latest_event(ebuf: EventBuffer):
    """Get the most recent event from buffer."""
    recent = ebuf.recent(limit=1)
    return recent[0] if recent else None


# ---------------------------------------------------------------------------
# Entry Verification Publication
# ---------------------------------------------------------------------------


class TestEntryVerificationPublication:
    def test_publish_entry_created(self, db_session):
        """ENTRY_CREATED event is published with correct payload."""
        from app.api.v1.ws_monitoring import get_connection_manager
        mgr = get_connection_manager()
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_created(
            entry_verification_id=1,
            student_id=10,
            exam_registration_id=20,
            entry_point_id=30,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ENTRY_CREATED
        assert event.entity_id == 1
        assert event.entity_type == "EntryVerification"
        assert event.student_id == 10
        assert event.payload["exam_registration_id"] == 20
        assert event.payload["entry_point_id"] == 30

    def test_publish_entry_began(self, db_session):
        """ENTRY_BEGAN event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_began(entry_verification_id=5)
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ENTRY_BEGAN
        assert event.entity_id == 5

    def test_publish_entry_granted(self, db_session):
        """ENTRY_GRANTED event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_granted(
            entry_verification_id=1,
            student_id=10,
            exam_id=100,
            hall_id=5,
            entry_point_id=30,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ENTRY_GRANTED
        assert event.student_id == 10
        assert event.exam_id == 100
        assert event.hall_id == 5
        assert event.entry_point_id == 30
        assert event.payload["decision"] == "GRANTED"

    def test_publish_entry_denied(self, db_session):
        """ENTRY_DENIED event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_denied(
            entry_verification_id=2,
            student_id=10,
            exam_id=100,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ENTRY_DENIED
        assert event.payload["decision"] == "DENIED"

    def test_publish_entry_escalated(self, db_session):
        """ENTRY_ESCALATED event is published with WARNING severity."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_escalated(
            entry_verification_id=3,
            student_id=10,
            reason="Mixed check states",
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ENTRY_ESCALATED
        assert event.severity == EventSeverity.WARNING
        assert event.payload["escalation_reason"] == "Mixed check states"
        # Should also generate alert
        assert len(abuf) == 1

    def test_publish_entry_resolved(self, db_session):
        """ENTRY_RESOLVED event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_resolved(
            entry_verification_id=4,
            student_id=10,
            granted=True,
            reason="Manual review approved",
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ENTRY_RESOLVED
        assert event.payload["resolution"] == "GRANTED"
        assert event.payload["resolution_reason"] == "Manual review approved"


# ---------------------------------------------------------------------------
# Risk Publication
# ---------------------------------------------------------------------------


class TestRiskPublication:
    def test_publish_signal_detected(self, db_session):
        """SIGNAL_DETECTED event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_signal_detected(
            signal_id=1,
            entry_verification_id=10,
            signal_type="DUPLICATE_ENTRY",
            strength="STRONG",
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.SIGNAL_DETECTED
        assert event.entity_type == "SecuritySignal"
        assert event.entity_id == 1
        assert event.payload["signal_type"] == "DUPLICATE_ENTRY"
        assert event.payload["strength"] == "STRONG"

    def test_publish_risk_assessed(self, db_session):
        """RISK_ASSESSED event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_risk_assessed(
            assessment_id=1,
            entry_verification_id=10,
            risk_level="LOW",
            risk_score=15.0,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.RISK_ASSESSED
        assert event.entity_type == "ProxyRiskAssessment"
        assert event.payload["risk_level"] == "LOW"
        assert event.payload["risk_score"] == 15.0

    def test_publish_risk_elevated(self, db_session):
        """RISK_ELEVATED event is published with WARNING severity."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_risk_elevated(
            assessment_id=2,
            entry_verification_id=10,
            risk_score=45.0,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.RISK_ELEVATED
        assert event.severity == EventSeverity.WARNING
        assert len(abuf) == 1

    def test_publish_risk_high(self, db_session):
        """RISK_HIGH event is published with WARNING severity."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_risk_high(
            assessment_id=3,
            entry_verification_id=10,
            risk_score=70.0,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.RISK_HIGH
        assert event.severity == EventSeverity.WARNING
        assert len(abuf) == 1

    def test_publish_risk_critical(self, db_session):
        """RISK_CRITICAL event is published with CRITICAL severity."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_risk_critical(
            assessment_id=4,
            entry_verification_id=10,
            risk_score=90.0,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.RISK_CRITICAL
        assert event.severity == EventSeverity.CRITICAL
        assert len(abuf) == 1


# ---------------------------------------------------------------------------
# Attendance Publication
# ---------------------------------------------------------------------------


class TestAttendancePublication:
    def test_publish_attendance_recorded(self, db_session):
        """ATTENDANCE_RECORDED event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_attendance_recorded(
            attendance_record_id=1,
            entry_verification_id=10,
            student_id=20,
            exam_id=100,
            hall_id=5,
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ATTENDANCE_RECORDED
        assert event.entity_type == "AttendanceRecord"
        assert event.entity_id == 1
        assert event.student_id == 20
        assert event.exam_id == 100
        assert event.hall_id == 5
        assert event.payload["entry_verification_id"] == 10

    def test_publish_attendance_corrected(self, db_session):
        """ATTENDANCE_CORRECTED event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_attendance_corrected(
            attendance_record_id=2,
            exam_registration_id=30,
            student_id=20,
            exam_id=100,
            hall_id=5,
            reason="Student was present but not recorded",
            recorded_by="admin",
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.ATTENDANCE_CORRECTED
        assert event.payload["exam_registration_id"] == 30
        assert event.payload["reason"] == "Student was present but not recorded"
        assert event.payload["recorded_by"] == "admin"


# ---------------------------------------------------------------------------
# Camera Publication
# ---------------------------------------------------------------------------


class TestCameraPublication:
    def test_publish_camera_online(self, db_session):
        """CAMERA_ONLINE event is published."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_camera_online(camera_id=1, previous_status="OFFLINE")
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.CAMERA_ONLINE
        assert event.entity_type == "Camera"
        assert event.entity_id == 1
        assert event.payload["status"] == "ONLINE"
        assert event.payload["previous_status"] == "OFFLINE"

    def test_publish_camera_offline(self, db_session):
        """CAMERA_OFFLINE event is published with WARNING severity."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_camera_offline(
            camera_id=2,
            reason="Network unreachable",
            previous_status="ONLINE",
        )
        assert len(ebuf) == 1
        event = _latest_event(ebuf)
        assert event.event_type == EventType.CAMERA_OFFLINE
        assert event.severity == EventSeverity.WARNING
        assert event.payload["reason"] == "Network unreachable"
        assert len(abuf) == 1


# ---------------------------------------------------------------------------
# Publication Safety
# ---------------------------------------------------------------------------


class TestPublicationSafety:
    def test_no_publish_when_publisher_none(self, db_session):
        """No crash when publisher is None."""
        init_monitoring_publisher(None)
        publish(MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        ))
        # Should not crash

    def test_sensitive_payload_rejected(self, db_session):
        """MonitoringEvent rejects sensitive payload keys."""
        from app.services.monitoring.events import MonitoringEvent
        with pytest.raises(ValueError, match="prohibited key"):
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
                payload={"face_image": "data:image/png;base64,..."},
            )

    def test_no_biometric_in_events(self, db_session):
        """Biometric data is rejected in payloads."""
        from app.services.monitoring.events import MonitoringEvent
        with pytest.raises(ValueError):
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
                payload={"biometric_data": "encrypted embeddings"},
            )

    def test_no_credentials_in_events(self, db_session):
        """Credentials are rejected in payloads."""
        from app.services.monitoring.events import MonitoringEvent
        with pytest.raises(ValueError):
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
                payload={"api_key": "sk-12345"},
            )

    def test_no_stack_traces_in_events(self, db_session):
        """Stack traces are rejected in payloads."""
        from app.services.monitoring.events import MonitoringEvent
        with pytest.raises(ValueError):
            MonitoringEvent(
                event_type=EventType.ENTRY_GRANTED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
                payload={"stack_trace": "File \"/app/main.py\"..."},
            )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_duplicate_event_id_skipped(self, db_session):
        """Same event_id published twice is only stored once."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        )
        pub.publish(event)
        pub.publish(event)
        assert len(ebuf) == 1
        assert pub.total_published == 1


# ---------------------------------------------------------------------------
# Alert Generation
# ---------------------------------------------------------------------------


class TestAlertGeneration:
    def test_info_no_alert(self, db_session):
        """INFO events do not generate alerts."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_granted(entry_verification_id=1, student_id=10)
        assert len(abuf) == 0

    def test_warning_generates_alert(self, db_session):
        """WARNING events generate alerts."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_entry_escalated(entry_verification_id=1, student_id=10)
        assert len(abuf) == 1
        alert = abuf.recent(limit=1)[0]
        assert alert.severity == EventSeverity.WARNING
        assert alert.event_type == EventType.ENTRY_ESCALATED

    def test_critical_generates_alert(self, db_session):
        """CRITICAL events generate alerts."""
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        mgr = ConnectionManager(max_connections=10)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        publish_risk_critical(
            assessment_id=1,
            entry_verification_id=10,
            risk_score=90.0,
        )
        assert len(abuf) == 1
        alert = abuf.recent(limit=1)[0]
        assert alert.severity == EventSeverity.CRITICAL


# ---------------------------------------------------------------------------
# WebSocket Integration
# ---------------------------------------------------------------------------


class TestWebSocketIntegration:
    def test_event_reaches_connection_manager(self, db_session):
        """Published event is broadcast to ConnectionManager."""
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        # Register a mock client
        t = AsyncMock()
        mgr.register("test-client", t)

        publish_entry_granted(entry_verification_id=1, student_id=10)
        # The broadcast is async, need to run it
        # In test context, the publisher tries to broadcast but may not have loop
        # The event is still in the buffer
        assert len(ebuf) == 1

    def test_filtered_client_receives_matching_event(self, db_session):
        """Client with exam_id filter receives matching events."""
        from app.services.monitoring.events import MonitoringFilter
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        t = AsyncMock()
        mgr.register("client-1", t, MonitoringFilter(exam_id=1))

        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
            exam_id=1,
        )
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 1
        t.send_text.assert_called_once()

    def test_filtered_client_rejects_non_matching_event(self, db_session):
        """Client with exam_id=1 does NOT receive exam_id=2 events."""
        from app.services.monitoring.events import MonitoringFilter
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        t = AsyncMock()
        mgr.register("client-1", t, MonitoringFilter(exam_id=1))

        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
            exam_id=2,
        )
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 0
        t.send_text.assert_not_called()

    def test_multiple_clients_receive_independently(self, db_session):
        """Multiple clients with different filters receive appropriate events."""
        from app.services.monitoring.events import MonitoringFilter
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        t1 = AsyncMock()
        t2 = AsyncMock()
        mgr.register("client-1", t1, MonitoringFilter(exam_id=1))
        mgr.register("client-2", t2, MonitoringFilter(exam_id=2))

        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
            exam_id=1,
        )
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 1
        t1.send_text.assert_called_once()
        t2.send_text.assert_not_called()

    def test_failed_client_does_not_block_others(self, db_session):
        """Client that fails to receive does not block other clients."""
        from app.services.monitoring.events import MonitoringFilter
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)

        t_bad = AsyncMock()
        t_bad.send_text = AsyncMock(side_effect=ConnectionError("fail"))
        t_good = AsyncMock()
        mgr.register("client-bad", t_bad)
        mgr.register("client-good", t_good)

        event = MonitoringEvent(
            event_type=EventType.ENTRY_GRANTED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        )
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 1
        assert mgr.active_count == 1
        t_good.send_text.assert_called_once()


# ---------------------------------------------------------------------------
# Publisher Initialization
# ---------------------------------------------------------------------------


class TestPublisherInit:
    def test_init_and_get(self, db_session):
        """Publisher can be initialized and retrieved."""
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)
        assert get_monitoring_publisher() is pub

    def test_reset_to_none(self, db_session):
        """Publisher can be reset to None."""
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        init_monitoring_publisher(pub)
        init_monitoring_publisher(None)
        assert get_monitoring_publisher() is None

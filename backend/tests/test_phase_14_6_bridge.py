"""Tests for Phase 14.6 — Security event bridge (monitoring → SecurityEvent).

Verifies that monitoring events are correctly mapped to persistent SecurityEvent
records via the post-publish hook.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.security_event import SecurityEvent, SecurityEventType, SecurityEventSeverity
from app.services.monitoring.events import EventType, MonitoringEvent
from app.services.security_event_bridge import (
    EVENT_MAP,
    _extract_ids,
    create_security_event_from_monitoring,
    make_security_event_hook,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _clean_tables(SessionLocal):
    """Delete all security events before and after each test."""
    db = SessionLocal()
    try:
        db.query(SecurityEvent).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(SecurityEvent).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Unit tests — EVENT_MAP
# ---------------------------------------------------------------------------


class TestEventMap:
    """EVENT_MAP contains expected mappings."""

    def test_signal_detected_maps_to_signal_detected(self):
        sec_type, sev = EVENT_MAP[EventType.SIGNAL_DETECTED]
        assert sec_type == SecurityEventType.SIGNAL_DETECTED
        assert sev == SecurityEventSeverity.LOW

    def test_risk_elevated_maps_to_risk_threshold_exceeded(self):
        sec_type, sev = EVENT_MAP[EventType.RISK_ELEVATED]
        assert sec_type == SecurityEventType.RISK_THRESHOLD_EXCEEDED
        assert sev == SecurityEventSeverity.MEDIUM

    def test_risk_high_maps_to_risk_threshold_exceeded(self):
        sec_type, sev = EVENT_MAP[EventType.RISK_HIGH]
        assert sec_type == SecurityEventType.RISK_THRESHOLD_EXCEEDED
        assert sev == SecurityEventSeverity.HIGH

    def test_risk_critical_maps_to_proxy_risk_critical(self):
        sec_type, sev = EVENT_MAP[EventType.RISK_CRITICAL]
        assert sec_type == SecurityEventType.PROXY_RISK_CRITICAL
        assert sev == SecurityEventSeverity.CRITICAL

    def test_entry_escalated_maps(self):
        sec_type, sev = EVENT_MAP[EventType.ENTRY_ESCALATED]
        assert sec_type == SecurityEventType.ENTRY_ESCALATED
        assert sev == SecurityEventSeverity.MEDIUM

    def test_entry_denied_maps(self):
        sec_type, sev = EVENT_MAP[EventType.ENTRY_DENIED]
        assert sec_type == SecurityEventType.SIGNAL_DETECTED
        assert sev == SecurityEventSeverity.LOW

    def test_attendance_corrected_maps(self):
        sec_type, sev = EVENT_MAP[EventType.ATTENDANCE_CORRECTED]
        assert sec_type == SecurityEventType.ATTENDANCE_CORRECTED
        assert sev == SecurityEventSeverity.LOW

    def test_camera_offline_maps(self):
        sec_type, sev = EVENT_MAP[EventType.CAMERA_OFFLINE]
        assert sec_type == SecurityEventType.CAMERA_OFFLINE_DURING_EXAM
        assert sev == SecurityEventSeverity.MEDIUM

    def test_entry_created_not_mapped(self):
        assert EventType.ENTRY_CREATED not in EVENT_MAP

    def test_entry_began_not_mapped(self):
        assert EventType.ENTRY_BEGAN not in EVENT_MAP

    def test_camera_online_not_mapped(self):
        assert EventType.CAMERA_ONLINE not in EVENT_MAP

    def test_heartbeat_not_mapped(self):
        assert EventType.HEARTBEAT not in EVENT_MAP

    def test_risk_assessed_not_mapped(self):
        assert EventType.RISK_ASSESSED not in EVENT_MAP

    def test_entry_granted_not_mapped(self):
        assert EventType.ENTRY_GRANTED not in EVENT_MAP

    def test_entry_resolved_not_mapped(self):
        assert EventType.ENTRY_RESOLVED not in EVENT_MAP

    def test_attendance_recorded_not_mapped(self):
        assert EventType.ATTENDANCE_RECORDED not in EVENT_MAP


# ---------------------------------------------------------------------------
# Unit tests — _extract_ids
# ---------------------------------------------------------------------------


class TestExtractIds:
    """_extract_ids extracts entity IDs from MonitoringEvent."""

    def test_extracts_from_payload(self):
        event = MonitoringEvent(
            event_type=EventType.RISK_CRITICAL,
            entity_type="ProxyRiskAssessment",
            entity_id=42,
            timestamp=datetime.now(timezone.utc),
            student_id=10,
            exam_id=5,
            hall_id=3,
            entry_point_id=2,
            payload={"entry_verification_id": 99, "risk_score": 0.95},
        )
        ids = _extract_ids(event)
        assert ids["entry_verification_id"] == 99
        assert ids["student_id"] == 10
        assert ids["exam_id"] == 5
        assert ids["hall_id"] == 3
        assert ids["entry_point_id"] == 2

    def test_missing_payload_fields_are_none(self):
        event = MonitoringEvent(
            event_type=EventType.SIGNAL_DETECTED,
            entity_type="SecuritySignal",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        )
        ids = _extract_ids(event)
        assert ids["entry_verification_id"] is None
        assert ids["student_id"] is None


# ---------------------------------------------------------------------------
# Integration tests — create_security_event_from_monitoring
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_tables")
class TestCreateSecurityEventFromMonitoring:
    """create_security_event_from_monitoring creates correct SecurityEvent records."""

    def test_creates_event_for_risk_critical(self, SessionLocal):
        db = SessionLocal()
        try:
            event = MonitoringEvent(
                event_type=EventType.RISK_CRITICAL,
                entity_type="ProxyRiskAssessment",
                entity_id=42,
                timestamp=datetime.now(timezone.utc),
                student_id=10,
                exam_id=5,
                hall_id=3,
                entry_point_id=2,
                payload={"entry_verification_id": 99, "risk_score": 0.95, "risk_level": "CRITICAL"},
            )
            sec_event = create_security_event_from_monitoring(db, event)
            assert sec_event is not None
            assert sec_event.event_type == SecurityEventType.PROXY_RISK_CRITICAL
            assert sec_event.severity == SecurityEventSeverity.CRITICAL
            assert sec_event.entity_type == "ProxyRiskAssessment"
            assert sec_event.entity_id == 42
            assert sec_event.entry_verification_id == 99
            assert sec_event.student_id == 10
            assert sec_event.exam_id == 5
            assert sec_event.hall_id == 3
            assert sec_event.entry_point_id == 2
            assert sec_event.source == "monitoring"
            assert sec_event.description is not None
            assert sec_event.metadata_json is not None
        finally:
            db.close()

    def test_creates_event_for_signal_detected(self, SessionLocal):
        db = SessionLocal()
        try:
            event = MonitoringEvent(
                event_type=EventType.SIGNAL_DETECTED,
                entity_type="SecuritySignal",
                entity_id=7,
                timestamp=datetime.now(timezone.utc),
                student_id=10,
                payload={"entry_verification_id": 99, "signal_type": "IDENTITY_MISMATCH", "strength": "STRONG"},
            )
            sec_event = create_security_event_from_monitoring(db, event)
            assert sec_event is not None
            assert sec_event.event_type == SecurityEventType.SIGNAL_DETECTED
            assert sec_event.severity == SecurityEventSeverity.LOW
        finally:
            db.close()

    def test_returns_none_for_unmapped_event(self, SessionLocal):
        db = SessionLocal()
        try:
            event = MonitoringEvent(
                event_type=EventType.ENTRY_CREATED,
                entity_type="EntryVerification",
                entity_id=1,
                timestamp=datetime.now(timezone.utc),
            )
            result = create_security_event_from_monitoring(db, event)
            assert result is None
        finally:
            db.close()

    def test_event_is_persisted(self, SessionLocal):
        db = SessionLocal()
        try:
            event = MonitoringEvent(
                event_type=EventType.CAMERA_OFFLINE,
                entity_type="Camera",
                entity_id=3,
                timestamp=datetime.now(timezone.utc),
                payload={"reason": "Connection lost"},
            )
            sec_event = create_security_event_from_monitoring(db, event)
            assert sec_event is not None
            assert sec_event.id is not None

            # Verify persisted
            from sqlalchemy.orm import Session as SASession
            db2 = SessionLocal()
            try:
                fetched = db2.query(SecurityEvent).filter(SecurityEvent.id == sec_event.id).one()
                assert fetched.event_type == SecurityEventType.CAMERA_OFFLINE_DURING_EXAM
            finally:
                db2.close()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Unit tests — make_security_event_hook
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_tables")
class TestMakeSecurityEventHook:
    """make_security_event_hook returns a callable that creates SecurityEvents."""

    def test_hook_returns_callable(self):
        hook = make_security_event_hook()
        assert callable(hook)

    def test_hook_creates_event_for_mapped_type(self, SessionLocal):
        hook = make_security_event_hook()
        event = MonitoringEvent(
            event_type=EventType.ENTRY_ESCALATED,
            entity_type="EntryVerification",
            entity_id=5,
            timestamp=datetime.now(timezone.utc),
            student_id=10,
            exam_id=5,
            payload={"escalation_reason": "Multiple signals"},
        )
        with patch("app.services.security_event_bridge.SessionLocal", SessionLocal):
            hook(event)

        db = SessionLocal()
        try:
            events = db.query(SecurityEvent).all()
            assert len(events) == 1
            assert events[0].event_type == SecurityEventType.ENTRY_ESCALATED
        finally:
            db.close()

    def test_hook_ignores_unmapped_type(self, SessionLocal):
        hook = make_security_event_hook()
        event = MonitoringEvent(
            event_type=EventType.ENTRY_CREATED,
            entity_type="EntryVerification",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
        )
        with patch("app.services.security_event_bridge.SessionLocal", SessionLocal):
            hook(event)

        db = SessionLocal()
        try:
            count = db.query(SecurityEvent).count()
            assert count == 0
        finally:
            db.close()

    def test_hook_handles_db_error_gracefully(self):
        hook = make_security_event_hook()
        event = MonitoringEvent(
            event_type=EventType.RISK_CRITICAL,
            entity_type="ProxyRiskAssessment",
            entity_id=1,
            timestamp=datetime.now(timezone.utc),
            payload={"risk_score": 0.99, "risk_level": "CRITICAL"},
        )
        # Should not raise — hook catches exceptions
        with patch("app.services.security_event_bridge.SessionLocal", side_effect=RuntimeError("DB down")):
            hook(event)

    def test_multiple_events_create_multiple_records(self, SessionLocal):
        hook = make_security_event_hook()
        for i in range(3):
            event = MonitoringEvent(
                event_type=EventType.SIGNAL_DETECTED,
                entity_type="SecuritySignal",
                entity_id=i + 1,
                timestamp=datetime.now(timezone.utc),
                payload={"signal_type": "TEST", "strength": "WEAK"},
            )
            with patch("app.services.security_event_bridge.SessionLocal", SessionLocal):
                hook(event)

        db = SessionLocal()
        try:
            count = db.query(SecurityEvent).count()
            assert count == 3
        finally:
            db.close()

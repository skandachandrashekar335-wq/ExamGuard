"""Monitoring event publication helpers (Phase 13.4).

Provides functions to create and publish MonitoringEvents from domain
operations. Called from routers AFTER successful database commit.

Architectural rule: publication happens AFTER the service commits.
If the service raises an exception, no event is published.

Does NOT mutate domain state. Does NOT access the database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.events import EventType, MonitoringEvent

logger = logging.getLogger(__name__)

# Module-level publisher instance (set by init_monitoring_publisher)
_publisher: EventPublisher | None = None


def init_monitoring_publisher(publisher: EventPublisher) -> None:
    """Initialize the module-level publisher. Called once at app startup."""
    global _publisher
    _publisher = publisher


def get_monitoring_publisher() -> EventPublisher | None:
    """Return the current publisher (for testing or router use)."""
    return _publisher


def publish(event: MonitoringEvent) -> None:
    """Publish a monitoring event if publisher is initialized.

    Safe to call even if publisher is None (no-op).
    Logs a warning if publisher is not initialized.
    """
    if _publisher is None:
        logger.debug("Monitoring publisher not initialized; event not published")
        return
    _publisher.publish(event)


# ---------------------------------------------------------------------------
# Entry Verification events
# ---------------------------------------------------------------------------


def publish_entry_created(
    entry_verification_id: int,
    student_id: int,
    exam_registration_id: int,
    entry_point_id: int,
) -> None:
    """Publish ENTRY_CREATED after successful entry verification creation."""
    publish(MonitoringEvent(
        event_type=EventType.ENTRY_CREATED,
        entity_type="EntryVerification",
        entity_id=entry_verification_id,
        timestamp=datetime.now(timezone.utc),
        student_id=student_id,
        entry_point_id=entry_point_id,
        payload={
            "student_id": student_id,
            "exam_registration_id": exam_registration_id,
            "entry_point_id": entry_point_id,
        },
    ))


def publish_entry_began(entry_verification_id: int) -> None:
    """Publish ENTRY_BEGAN after successful begin_processing."""
    publish(MonitoringEvent(
        event_type=EventType.ENTRY_BEGAN,
        entity_type="EntryVerification",
        entity_id=entry_verification_id,
        timestamp=datetime.now(timezone.utc),
    ))


def publish_entry_granted(
    entry_verification_id: int,
    student_id: int,
    exam_id: int | None = None,
    hall_id: int | None = None,
    entry_point_id: int | None = None,
) -> None:
    """Publish ENTRY_GRANTED after successful evaluation resulting in GRANTED."""
    publish(MonitoringEvent(
        event_type=EventType.ENTRY_GRANTED,
        entity_type="EntryVerification",
        entity_id=entry_verification_id,
        timestamp=datetime.now(timezone.utc),
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        entry_point_id=entry_point_id,
        payload={"decision": "GRANTED"},
    ))


def publish_entry_denied(
    entry_verification_id: int,
    student_id: int,
    exam_id: int | None = None,
    hall_id: int | None = None,
    entry_point_id: int | None = None,
) -> None:
    """Publish ENTRY_DENIED after successful evaluation resulting in DENIED."""
    publish(MonitoringEvent(
        event_type=EventType.ENTRY_DENIED,
        entity_type="EntryVerification",
        entity_id=entry_verification_id,
        timestamp=datetime.now(timezone.utc),
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        entry_point_id=entry_point_id,
        payload={"decision": "DENIED"},
    ))


def publish_entry_escalated(
    entry_verification_id: int,
    student_id: int,
    reason: str | None = None,
    exam_id: int | None = None,
    hall_id: int | None = None,
    entry_point_id: int | None = None,
) -> None:
    """Publish ENTRY_ESCALATED after successful escalation."""
    payload: dict = {}
    if reason:
        payload["escalation_reason"] = reason
    publish(MonitoringEvent(
        event_type=EventType.ENTRY_ESCALATED,
        entity_type="EntryVerification",
        entity_id=entry_verification_id,
        timestamp=datetime.now(timezone.utc),
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        entry_point_id=entry_point_id,
        payload=payload,
    ))


def publish_entry_resolved(
    entry_verification_id: int,
    student_id: int,
    granted: bool,
    reason: str | None = None,
    exam_id: int | None = None,
    hall_id: int | None = None,
    entry_point_id: int | None = None,
) -> None:
    """Publish ENTRY_RESOLVED after successful resolution of an escalation."""
    payload: dict = {"resolution": "GRANTED" if granted else "DENIED"}
    if reason:
        payload["resolution_reason"] = reason
    publish(MonitoringEvent(
        event_type=EventType.ENTRY_RESOLVED,
        entity_type="EntryVerification",
        entity_id=entry_verification_id,
        timestamp=datetime.now(timezone.utc),
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        entry_point_id=entry_point_id,
        payload=payload,
    ))


# ---------------------------------------------------------------------------
# Risk events
# ---------------------------------------------------------------------------


def publish_signal_detected(
    signal_id: int,
    entry_verification_id: int,
    signal_type: str,
    strength: str,
) -> None:
    """Publish SIGNAL_DETECTED when a SecuritySignal is created."""
    publish(MonitoringEvent(
        event_type=EventType.SIGNAL_DETECTED,
        entity_type="SecuritySignal",
        entity_id=signal_id,
        timestamp=datetime.now(timezone.utc),
        payload={
            "entry_verification_id": entry_verification_id,
            "signal_type": signal_type,
            "strength": strength,
        },
    ))


def publish_risk_assessed(
    assessment_id: int,
    entry_verification_id: int,
    risk_level: str,
    risk_score: float,
) -> None:
    """Publish RISK_ASSESSED when a ProxyRiskAssessment is created."""
    publish(MonitoringEvent(
        event_type=EventType.RISK_ASSESSED,
        entity_type="ProxyRiskAssessment",
        entity_id=assessment_id,
        timestamp=datetime.now(timezone.utc),
        payload={
            "entry_verification_id": entry_verification_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
        },
    ))


def publish_risk_elevated(
    assessment_id: int,
    entry_verification_id: int,
    risk_score: float,
) -> None:
    """Publish RISK_ELEVATED when assessment is ELEVATED."""
    publish(MonitoringEvent(
        event_type=EventType.RISK_ELEVATED,
        entity_type="ProxyRiskAssessment",
        entity_id=assessment_id,
        timestamp=datetime.now(timezone.utc),
        payload={
            "entry_verification_id": entry_verification_id,
            "risk_score": risk_score,
            "risk_level": "ELEVATED",
        },
    ))


def publish_risk_high(
    assessment_id: int,
    entry_verification_id: int,
    risk_score: float,
) -> None:
    """Publish RISK_HIGH when assessment is HIGH."""
    publish(MonitoringEvent(
        event_type=EventType.RISK_HIGH,
        entity_type="ProxyRiskAssessment",
        entity_id=assessment_id,
        timestamp=datetime.now(timezone.utc),
        payload={
            "entry_verification_id": entry_verification_id,
            "risk_score": risk_score,
            "risk_level": "HIGH",
        },
    ))


def publish_risk_critical(
    assessment_id: int,
    entry_verification_id: int,
    risk_score: float,
) -> None:
    """Publish RISK_CRITICAL when assessment is CRITICAL."""
    publish(MonitoringEvent(
        event_type=EventType.RISK_CRITICAL,
        entity_type="ProxyRiskAssessment",
        entity_id=assessment_id,
        timestamp=datetime.now(timezone.utc),
        payload={
            "entry_verification_id": entry_verification_id,
            "risk_score": risk_score,
            "risk_level": "CRITICAL",
        },
    ))


# ---------------------------------------------------------------------------
# Attendance events
# ---------------------------------------------------------------------------


def publish_attendance_recorded(
    attendance_record_id: int,
    entry_verification_id: int,
    student_id: int,
    exam_id: int | None = None,
    hall_id: int | None = None,
) -> None:
    """Publish ATTENDANCE_RECORDED after successful attendance recording."""
    publish(MonitoringEvent(
        event_type=EventType.ATTENDANCE_RECORDED,
        entity_type="AttendanceRecord",
        entity_id=attendance_record_id,
        timestamp=datetime.now(timezone.utc),
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        payload={"entry_verification_id": entry_verification_id},
    ))


def publish_attendance_corrected(
    attendance_record_id: int,
    exam_registration_id: int,
    student_id: int,
    exam_id: int | None = None,
    hall_id: int | None = None,
    reason: str | None = None,
    recorded_by: str | None = None,
) -> None:
    """Publish ATTENDANCE_CORRECTED after manual attendance correction."""
    payload: dict = {"exam_registration_id": exam_registration_id}
    if reason:
        payload["reason"] = reason
    if recorded_by:
        payload["recorded_by"] = recorded_by
    publish(MonitoringEvent(
        event_type=EventType.ATTENDANCE_CORRECTED,
        entity_type="AttendanceRecord",
        entity_id=attendance_record_id,
        timestamp=datetime.now(timezone.utc),
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        payload=payload,
    ))


# ---------------------------------------------------------------------------
# Camera events
# ---------------------------------------------------------------------------


def publish_camera_online(
    camera_id: int,
    previous_status: str | None = None,
) -> None:
    """Publish CAMERA_ONLINE after successful health observation showing online."""
    payload: dict = {"status": "ONLINE"}
    if previous_status:
        payload["previous_status"] = previous_status
    publish(MonitoringEvent(
        event_type=EventType.CAMERA_ONLINE,
        entity_type="Camera",
        entity_id=camera_id,
        timestamp=datetime.now(timezone.utc),
        payload=payload,
    ))


def publish_camera_offline(
    camera_id: int,
    reason: str | None = None,
    previous_status: str | None = None,
) -> None:
    """Publish CAMERA_OFFLINE after successful health observation showing offline."""
    payload: dict = {"status": "OFFLINE"}
    if reason:
        payload["reason"] = reason
    if previous_status:
        payload["previous_status"] = previous_status
    publish(MonitoringEvent(
        event_type=EventType.CAMERA_OFFLINE,
        entity_type="Camera",
        entity_id=camera_id,
        timestamp=datetime.now(timezone.utc),
        payload=payload,
    ))

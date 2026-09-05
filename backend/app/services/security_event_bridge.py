"""Security event bridge (Phase 14.6).

Maps monitoring events to persistent SecurityEvent records.
Called as a post-publish hook on EventPublisher.

Only maps events that represent security-relevant activity.
Routine events (ENTRY_CREATED, ENTRY_BEGAN, CAMERA_ONLINE, HEARTBEAT) are skipped.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.security_event import SecurityEvent, SecurityEventType, SecurityEventSeverity
from app.services.monitoring.events import EventType, MonitoringEvent

logger = logging.getLogger(__name__)

# Mapping: MonitoringEvent EventType → (SecurityEventType, severity)
EVENT_MAP: dict[str, tuple[SecurityEventType, SecurityEventSeverity]] = {
    EventType.SIGNAL_DETECTED: (
        SecurityEventType.SIGNAL_DETECTED,
        SecurityEventSeverity.LOW,
    ),
    EventType.RISK_ELEVATED: (
        SecurityEventType.RISK_THRESHOLD_EXCEEDED,
        SecurityEventSeverity.MEDIUM,
    ),
    EventType.RISK_HIGH: (
        SecurityEventType.RISK_THRESHOLD_EXCEEDED,
        SecurityEventSeverity.HIGH,
    ),
    EventType.RISK_CRITICAL: (
        SecurityEventType.PROXY_RISK_CRITICAL,
        SecurityEventSeverity.CRITICAL,
    ),
    EventType.ENTRY_ESCALATED: (
        SecurityEventType.ENTRY_ESCALATED,
        SecurityEventSeverity.MEDIUM,
    ),
    EventType.ENTRY_DENIED: (
        SecurityEventType.SIGNAL_DETECTED,
        SecurityEventSeverity.LOW,
    ),
    EventType.ATTENDANCE_CORRECTED: (
        SecurityEventType.ATTENDANCE_CORRECTED,
        SecurityEventSeverity.LOW,
    ),
    EventType.CAMERA_OFFLINE: (
        SecurityEventType.CAMERA_OFFLINE_DURING_EXAM,
        SecurityEventSeverity.MEDIUM,
    ),
}


def _extract_ids(event: MonitoringEvent) -> dict:
    """Extract entity IDs from event payload."""
    payload = event.payload or {}
    return {
        "entry_verification_id": payload.get("entry_verification_id"),
        "student_id": event.student_id,
        "exam_id": event.exam_id,
        "hall_id": event.hall_id,
        "entry_point_id": event.entry_point_id,
    }


def create_security_event_from_monitoring(
    db: Session, event: MonitoringEvent
) -> SecurityEvent | None:
    """Create a SecurityEvent from a MonitoringEvent.

    Returns the created SecurityEvent, or None if the event type is not mapped.
    """
    mapping = EVENT_MAP.get(event.event_type.value)
    if mapping is None:
        return None

    security_event_type, severity = mapping
    ids = _extract_ids(event)

    # Build description from event
    description = f"Monitoring event: {event.event_type.value}"
    if event.payload:
        key_fields = {
            k: v
            for k, v in event.payload.items()
            if k in ("risk_level", "risk_score", "signal_type", "strength", "escalation_reason", "resolution", "reason")
        }
        if key_fields:
            description += f" — {json.dumps(key_fields, default=str)}"

    security_event = SecurityEvent(
        event_type=security_event_type,
        severity=severity,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        entry_verification_id=ids["entry_verification_id"],
        student_id=ids["student_id"],
        exam_id=ids["exam_id"],
        hall_id=ids["hall_id"],
        entry_point_id=ids["entry_point_id"],
        description=description,
        metadata_json=json.dumps(event.payload, default=str) if event.payload else None,
        source="monitoring",
    )
    db.add(security_event)
    db.commit()
    return security_event


def make_security_event_hook() -> Callable[[MonitoringEvent], None]:
    """Create a post-publish hook that persists security-relevant events.

    Returns a callable suitable for EventPublisher's post_publish parameter.
    Each invocation opens its own DB session (safe for the post-commit context).
    """

    def hook(event: MonitoringEvent) -> None:
        mapping = EVENT_MAP.get(event.event_type.value)
        if mapping is None:
            return
        try:
            db = SessionLocal()
            try:
                create_security_event_from_monitoring(db, event)
            finally:
                db.close()
        except Exception:
            logger.debug("Failed to create SecurityEvent from monitoring event", exc_info=True)

    return hook

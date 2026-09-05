"""Alert classification and message generation (Phase 13.5).

Deterministic, stateless alert layer that answers:
- Should this MonitoringEvent create an alert?
- What message should the alert carry?

Consumes MonitoringEvent only. Does not query the database.
Does not mutate domain state. Does not make authorization decisions.

Alert lifecycle (Phase 13.5):
    EVENT OCCURS → MonitoringEvent → Alert classification → Alert → AlertBuffer

NO: acknowledgement, resolution, dismissal, assignment, persistence.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.monitoring.events import (
    EventSeverity,
    EventType,
    MonitoringEvent,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert-worthy event types (deterministic set)
# ---------------------------------------------------------------------------

_ALERT_WORTHY_EVENTS: frozenset[EventType] = frozenset({
    EventType.ENTRY_ESCALATED,
    EventType.RISK_ELEVATED,
    EventType.RISK_HIGH,
    EventType.RISK_CRITICAL,
    EventType.CAMERA_OFFLINE,
})


def should_alert(event: MonitoringEvent) -> bool:
    """Return True if this event should generate an alert.

    Classification rules:
    - WARNING/CRITICAL severity events generate alerts
    - INFO events never generate alerts
    - Only known alert-worthy event types generate alerts
    """
    if event.severity not in (EventSeverity.WARNING, EventSeverity.CRITICAL):
        return False
    return event.event_type in _ALERT_WORTHY_EVENTS


# ---------------------------------------------------------------------------
# Alert message templates (deterministic, safe)
# ---------------------------------------------------------------------------

_ALERT_MESSAGES: dict[EventType, str] = {
    EventType.ENTRY_ESCALATED: "Entry verification requires review.",
    EventType.RISK_ELEVATED: "Elevated proxy-risk assessment detected.",
    EventType.RISK_HIGH: "High proxy-risk assessment detected.",
    EventType.RISK_CRITICAL: "Critical proxy-risk assessment detected.",
    EventType.CAMERA_OFFLINE: "Camera reported offline.",
}


def alert_message(event: MonitoringEvent) -> str:
    """Generate a concise, safe operational summary for an alert.

    Messages are deterministic and contain no sensitive data.
    """
    template = _ALERT_MESSAGES.get(event.event_type)
    if template:
        return template
    # Fallback for unknown alert-worthy events (should not happen)
    return f"{event.event_type.value} detected."


def alert_payload(event: MonitoringEvent) -> dict[str, Any]:
    """Generate a minimal operational payload for the alert.

    Contains only safe, non-sensitive reference data.
    """
    payload: dict[str, Any] = {
        "event_type": event.event_type.value,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
    }
    if event.exam_id is not None:
        payload["exam_id"] = event.exam_id
    if event.hall_id is not None:
        payload["hall_id"] = event.hall_id
    if event.student_id is not None:
        payload["student_id"] = event.student_id
    return payload


# ---------------------------------------------------------------------------
# Alert-worthy event type set (for external use)
# ---------------------------------------------------------------------------


def alert_worthy_event_types() -> frozenset[EventType]:
    """Return the set of event types that can generate alerts."""
    return _ALERT_WORTHY_EVENTS

"""Monitoring event domain.

Immutable, ephemeral event objects for real-time monitoring delivery.
No database persistence. No ORM dependency. No FastAPI dependency.

These are delivery vehicles, not audit records.
Existing domain audit/history tables remain authoritative.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventCategory(str, enum.Enum):
    """High-level event category for filtering."""

    ENTRY = "ENTRY"
    RISK = "RISK"
    ATTENDANCE = "ATTENDANCE"
    CAMERA = "CAMERA"
    SYSTEM = "SYSTEM"


class EventType(str, enum.Enum):
    """Specific event types within categories."""

    # Entry verification events
    ENTRY_CREATED = "ENTRY_CREATED"
    ENTRY_BEGAN = "ENTRY_BEGAN"
    ENTRY_GRANTED = "ENTRY_GRANTED"
    ENTRY_DENIED = "ENTRY_DENIED"
    ENTRY_ESCALATED = "ENTRY_ESCALATED"
    ENTRY_RESOLVED = "ENTRY_RESOLVED"

    # Proxy risk events
    SIGNAL_DETECTED = "SIGNAL_DETECTED"
    RISK_ASSESSED = "RISK_ASSESSED"
    RISK_ELEVATED = "RISK_ELEVATED"
    RISK_HIGH = "RISK_HIGH"
    RISK_CRITICAL = "RISK_CRITICAL"

    # Attendance events
    ATTENDANCE_RECORDED = "ATTENDANCE_RECORDED"
    ATTENDANCE_CORRECTED = "ATTENDANCE_CORRECTED"

    # Camera events
    CAMERA_OFFLINE = "CAMERA_OFFLINE"
    CAMERA_ONLINE = "CAMERA_ONLINE"

    # System events
    HEARTBEAT = "HEARTBEAT"


class EventSeverity(str, enum.Enum):
    """Event severity level. Ordered: INFO < WARNING < CRITICAL."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[EventSeverity, int] = {
    EventSeverity.INFO: 0,
    EventSeverity.WARNING: 1,
    EventSeverity.CRITICAL: 2,
}


def severity_order(severity: EventSeverity) -> int:
    """Return numeric ordering for severity comparison."""
    return _SEVERITY_ORDER[severity]


# ---------------------------------------------------------------------------
# Deterministic event severity mapping
# ---------------------------------------------------------------------------

_EVENT_SEVERITY: dict[EventType, EventSeverity] = {
    # Entry — informational
    EventType.ENTRY_CREATED: EventSeverity.INFO,
    EventType.ENTRY_BEGAN: EventSeverity.INFO,
    EventType.ENTRY_GRANTED: EventSeverity.INFO,
    EventType.ENTRY_DENIED: EventSeverity.INFO,
    EventType.ENTRY_RESOLVED: EventSeverity.INFO,
    # Entry — warning
    EventType.ENTRY_ESCALATED: EventSeverity.WARNING,
    # Risk — informational
    EventType.SIGNAL_DETECTED: EventSeverity.INFO,
    EventType.RISK_ASSESSED: EventSeverity.INFO,
    # Risk — warning/critical
    EventType.RISK_ELEVATED: EventSeverity.WARNING,
    EventType.RISK_HIGH: EventSeverity.WARNING,
    EventType.RISK_CRITICAL: EventSeverity.CRITICAL,
    # Attendance — informational
    EventType.ATTENDANCE_RECORDED: EventSeverity.INFO,
    EventType.ATTENDANCE_CORRECTED: EventSeverity.INFO,
    # Camera
    EventType.CAMERA_OFFLINE: EventSeverity.WARNING,
    EventType.CAMERA_ONLINE: EventSeverity.INFO,
    # System
    EventType.HEARTBEAT: EventSeverity.INFO,
}


def default_severity(event_type: EventType) -> EventSeverity:
    """Return the deterministic severity for an event type."""
    return _EVENT_SEVERITY[event_type]


# ---------------------------------------------------------------------------
# Event category mapping
# ---------------------------------------------------------------------------

_EVENT_CATEGORY: dict[EventType, EventCategory] = {
    EventType.ENTRY_CREATED: EventCategory.ENTRY,
    EventType.ENTRY_BEGAN: EventCategory.ENTRY,
    EventType.ENTRY_GRANTED: EventCategory.ENTRY,
    EventType.ENTRY_DENIED: EventCategory.ENTRY,
    EventType.ENTRY_ESCALATED: EventCategory.ENTRY,
    EventType.ENTRY_RESOLVED: EventCategory.ENTRY,
    EventType.SIGNAL_DETECTED: EventCategory.RISK,
    EventType.RISK_ASSESSED: EventCategory.RISK,
    EventType.RISK_ELEVATED: EventCategory.RISK,
    EventType.RISK_HIGH: EventCategory.RISK,
    EventType.RISK_CRITICAL: EventCategory.RISK,
    EventType.ATTENDANCE_RECORDED: EventCategory.ATTENDANCE,
    EventType.ATTENDANCE_CORRECTED: EventCategory.ATTENDANCE,
    EventType.CAMERA_OFFLINE: EventCategory.CAMERA,
    EventType.CAMERA_ONLINE: EventCategory.CAMERA,
    EventType.HEARTBEAT: EventCategory.SYSTEM,
}


def event_category(event_type: EventType) -> EventCategory:
    """Return the category for an event type."""
    return _EVENT_CATEGORY[event_type]


# ---------------------------------------------------------------------------
# Sensitive payload keys — must never appear in event payloads
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "face_image",
    "face_embedding",
    "face_embeddings",
    "biometric_data",
    "biometric_payload",
    "provider_credentials",
    "device_credentials",
    "api_key",
    "api_keys",
    "secret",
    "secrets",
    "password",
    "token",
    "raw_ocr",
    "ocr_payload",
    "database_url",
    "filesystem_path",
    "stack_trace",
    "traceback",
})


def _validate_payload(payload: dict[str, Any]) -> None:
    """Raise ValueError if payload contains sensitive keys."""
    for key in payload:
        if key.lower() in _SENSITIVE_KEYS:
            raise ValueError(
                f"Payload contains prohibited key '{key}'. "
                f"Sensitive data must not appear in monitoring events."
            )


# ---------------------------------------------------------------------------
# MonitoringEvent — immutable event object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonitoringEvent:
    """Immutable monitoring event for real-time delivery.

    No database persistence. No ORM dependency.
    Created by EventPublisher after domain service commits.
    """

    event_type: EventType
    entity_type: str
    entity_id: int
    timestamp: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    category: EventCategory = field(init=False)
    severity: EventSeverity = field(init=False)
    exam_id: int | None = None
    hall_id: int | None = None
    student_id: int | None = None
    entry_point_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Derive category and severity from event_type
        object.__setattr__(self, "category", event_category(self.event_type))
        object.__setattr__(self, "severity", default_severity(self.event_type))
        # Validate payload safety
        if self.payload:
            _validate_payload(self.payload)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        result: dict[str, Any] = {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "category": self.category.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
        }
        if self.exam_id is not None:
            result["exam_id"] = self.exam_id
        if self.hall_id is not None:
            result["hall_id"] = self.hall_id
        if self.student_id is not None:
            result["student_id"] = self.student_id
        if self.entry_point_id is not None:
            result["entry_point_id"] = self.entry_point_id
        if self.payload:
            result["payload"] = self.payload
        return result


# ---------------------------------------------------------------------------
# MonitoringFilter — reusable filter criteria
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonitoringFilter:
    """Filter criteria for monitoring event subscription.

    Used by ConnectionManager (Phase 13.2) to match events to clients.
    """

    exam_id: int | None = None
    hall_id: int | None = None
    category: EventCategory | None = None
    event_type: EventType | None = None
    min_severity: EventSeverity = EventSeverity.INFO

    def matches(self, event: MonitoringEvent) -> bool:
        """Return True if the event passes all active filters."""
        if self.exam_id is not None and event.exam_id != self.exam_id:
            return False
        if self.hall_id is not None and event.hall_id != self.hall_id:
            return False
        if self.category is not None and event.category != self.category:
            return False
        if self.event_type is not None and event.event_type != self.event_type:
            return False
        if severity_order(event.severity) < severity_order(self.min_severity):
            return False
        return True

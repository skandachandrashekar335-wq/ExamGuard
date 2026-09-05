"""Bounded in-memory buffer for monitoring alerts.

Alerts are ephemeral advisory objects for operator attention.
Not persisted. Not an audit log. References originating MonitoringEvent by event_id.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from app.services.monitoring.events import EventSeverity, EventType


@dataclass(frozen=True)
class Alert:
    """Ephemeral monitoring alert referencing an originating event."""

    event_id: uuid.UUID
    event_type: EventType
    severity: EventSeverity
    message: str
    entity_type: str
    entity_id: int
    exam_id: int | None = None
    hall_id: int | None = None
    student_id: int | None = None
    alert_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        result: dict = {
            "alert_id": str(self.alert_id),
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }
        if self.exam_id is not None:
            result["exam_id"] = self.exam_id
        if self.hall_id is not None:
            result["hall_id"] = self.hall_id
        if self.student_id is not None:
            result["student_id"] = self.student_id
        return result


class AlertBuffer:
    """Bounded ring buffer for recent alerts.

    Thread-safe. Automatically discards oldest alerts when full.
    """

    def __init__(self, capacity: int = 200) -> None:
        if capacity < 1:
            raise ValueError(f"AlertBuffer capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._buffer: deque[Alert] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def append(self, alert: Alert) -> None:
        """Append an alert. Discards oldest if at capacity."""
        with self._lock:
            self._buffer.append(alert)

    def recent(self, limit: int = 50) -> list[Alert]:
        """Return the most recent alerts, newest first."""
        with self._lock:
            items = list(self._buffer)
        items.reverse()
        return items[:limit]

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

    def __iter__(self) -> Iterator[Alert]:
        with self._lock:
            items = list(self._buffer)
        return iter(items)

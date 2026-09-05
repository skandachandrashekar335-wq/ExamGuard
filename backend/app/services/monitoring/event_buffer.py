"""Bounded in-memory ring buffer for MonitoringEvents.

Not an audit log. Not persisted. Delivery buffer for recent events.
Automatically discards oldest events when capacity is reached.
Thread-safe for concurrent access.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Iterator

from app.services.monitoring.events import MonitoringEvent, MonitoringFilter


class EventBuffer:
    """Bounded ring buffer for recent MonitoringEvents.

    Thread-safe. Automatically discards oldest events when full.
    """

    def __init__(self, capacity: int = 1000) -> None:
        if capacity < 1:
            raise ValueError(f"EventBuffer capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._buffer: deque[MonitoringEvent] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def append(self, event: MonitoringEvent) -> None:
        """Append an event. Discards oldest if at capacity."""
        with self._lock:
            self._buffer.append(event)

    def recent(self, limit: int = 50) -> list[MonitoringEvent]:
        """Return the most recent events, newest first."""
        with self._lock:
            items = list(self._buffer)
        items.reverse()
        return items[:limit]

    def query(self, filter_obj: MonitoringFilter, limit: int = 50) -> list[MonitoringEvent]:
        """Return recent events matching the filter, newest first."""
        with self._lock:
            items = [e for e in self._buffer if filter_obj.matches(e)]
        items.reverse()
        return items[:limit]

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

    def __iter__(self) -> Iterator[MonitoringEvent]:
        with self._lock:
            items = list(self._buffer)
        return iter(items)

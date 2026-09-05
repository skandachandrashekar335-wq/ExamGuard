"""Event publisher for monitoring events.

Accepts MonitoringEvents, stores in event buffer, generates alerts
for WARNING/CRITICAL events, broadcasts to connected clients.

Does NOT mutate domain state. Does NOT access the database.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone

from app.services.monitoring.alert_buffer import Alert, AlertBuffer
from app.services.monitoring.alerting import alert_message, should_alert
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.events import EventSeverity, MonitoringEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes monitoring events to buffers and connected clients.

    Thread-safe. Does not mutate domain state.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        event_buffer: EventBuffer,
        alert_buffer: AlertBuffer,
    ) -> None:
        self._connection_manager = connection_manager
        self._event_buffer = event_buffer
        self._alert_buffer = alert_buffer
        self._published_ids: set[uuid.UUID] = set()
        self._lock = threading.Lock()
        self._total_published: int = 0

    @property
    def total_published(self) -> int:
        """Total events published since creation."""
        with self._lock:
            return self._total_published

    def publish(self, event: MonitoringEvent) -> None:
        """Publish a monitoring event.

        1. Validate (payload safety already enforced by MonitoringEvent)
        2. Idempotent by event_id — duplicate event_ids are silently skipped
        3. Store in event buffer
        4. Generate alert if alert classification says so
        5. Broadcast to connected clients (best-effort, non-blocking)
        """
        # Idempotent by event_id
        with self._lock:
            if event.event_id in self._published_ids:
                logger.debug(
                    "Skipping duplicate event %s (already published)",
                    event.event_id,
                )
                return
            self._published_ids.add(event.event_id)
            self._total_published += 1

        # Store in event buffer
        self._event_buffer.append(event)

        # Generate alert if classified as alert-worthy
        if should_alert(event):
            alert = Alert(
                event_id=event.event_id,
                event_type=event.event_type,
                severity=event.severity,
                message=alert_message(event),
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                exam_id=event.exam_id,
                hall_id=event.hall_id,
                student_id=event.student_id,
            )
            self._alert_buffer.append(alert)

        # Broadcast to clients (best-effort)
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — schedule the broadcast
                loop.create_task(self._connection_manager.broadcast(event))
            else:
                # Synchronous context — run the broadcast
                loop.run_until_complete(self._connection_manager.broadcast(event))
        except RuntimeError:
            # No event loop — broadcast will happen when WebSocket endpoint
            # is added in Phase 13.3 and provides the async context
            logger.debug(
                "No event loop available; broadcast deferred to WebSocket layer"
            )

    def status(self) -> dict:
        """Return publisher status for REST API use."""
        return {
            "active_connections": self._connection_manager.active_count,
            "buffered_events": len(self._event_buffer),
            "buffered_alerts": len(self._alert_buffer),
            "total_published": self.total_published,
        }

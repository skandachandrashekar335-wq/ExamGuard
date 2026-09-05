"""Monitoring schemas (Phase 13.1, 13.6).

Pydantic schemas for monitoring events, alerts, status, and REST responses.
No database dependency. No ORM dependency.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
)


# ---------------------------------------------------------------------------
# Monitoring Event schemas
# ---------------------------------------------------------------------------


class MonitoringEventSchema(BaseModel):
    """Serialized monitoring event for WebSocket and REST delivery."""

    event_id: str = Field(description="UUID identifying this event")
    event_type: EventType = Field(description="Specific event type")
    category: EventCategory = Field(description="Event category")
    entity_type: str = Field(description="Domain entity type")
    entity_id: int = Field(description="Domain entity ID")
    timestamp: datetime = Field(description="When the event occurred")
    severity: EventSeverity = Field(description="Event severity level")
    exam_id: int | None = Field(default=None, description="Exam ID if applicable")
    hall_id: int | None = Field(default=None, description="Exam hall ID if applicable")
    student_id: int | None = Field(default=None, description="Student ID if applicable")
    entry_point_id: int | None = Field(
        default=None, description="Entry point ID if applicable"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Operational event data"
    )


class MonitoringEventListResponse(BaseModel):
    """List of monitoring events from ring buffer (no page/page_size)."""

    items: list[MonitoringEventSchema]
    count: int


# ---------------------------------------------------------------------------
# Monitoring Filter schemas
# ---------------------------------------------------------------------------


class MonitoringFilterParams(BaseModel):
    """Filter parameters for monitoring event queries."""

    exam_id: int | None = Field(default=None, description="Filter by exam ID")
    hall_id: int | None = Field(default=None, description="Filter by hall ID")
    category: EventCategory | None = Field(
        default=None, description="Filter by event category"
    )
    event_type: EventType | None = Field(
        default=None, description="Filter by specific event type"
    )
    min_severity: EventSeverity = Field(
        default=EventSeverity.INFO,
        description="Minimum severity level (INFO < WARNING < CRITICAL)",
    )


# ---------------------------------------------------------------------------
# Monitoring Status schema
# ---------------------------------------------------------------------------


class MonitoringStatusResponse(BaseModel):
    """Monitoring system status from in-memory components."""

    active_connections: int = Field(description="Number of active WebSocket connections")
    buffered_events: int = Field(description="Events currently in ring buffer")
    buffered_alerts: int = Field(description="Alerts currently in ring buffer")
    total_published: int = Field(
        description="Total events published since server start"
    )
    event_buffer_capacity: int = Field(description="Max events in ring buffer")
    alert_buffer_capacity: int = Field(description="Max alerts in ring buffer")
    max_connections: int = Field(description="Max WebSocket connections")


# ---------------------------------------------------------------------------
# Alert schemas
# ---------------------------------------------------------------------------


class MonitoringAlertSchema(BaseModel):
    """Monitoring alert for operator attention."""

    alert_id: str = Field(description="UUID identifying this alert")
    event_id: str = Field(description="UUID of the originating event")
    event_type: EventType = Field(description="Event type that triggered the alert")
    severity: EventSeverity = Field(description="Alert severity")
    entity_type: str = Field(description="Domain entity type")
    entity_id: int = Field(description="Domain entity ID")
    exam_id: int | None = Field(default=None)
    hall_id: int | None = Field(default=None)
    student_id: int | None = Field(default=None)
    message: str = Field(description="Human-readable alert message")
    created_at: datetime = Field(description="When the alert was generated")


class MonitoringAlertListResponse(BaseModel):
    """List of monitoring alerts from ring buffer."""

    items: list[MonitoringAlertSchema]
    count: int


# ---------------------------------------------------------------------------
# Connection status schema
# ---------------------------------------------------------------------------


class MonitoringConnectionStatusResponse(BaseModel):
    """WebSocket connection status."""

    active_connections: int = Field(description="Number of active connections")
    max_connections: int = Field(description="Maximum allowed connections")

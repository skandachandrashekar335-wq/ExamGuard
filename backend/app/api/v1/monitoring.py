"""Monitoring REST API (Phase 13.6).

READ-ONLY endpoints exposing in-memory monitoring state:
- Event buffer (bounded ring buffer, no persistence)
- Alert buffer (bounded ring buffer, no persistence)
- Connection status (active WebSocket connections)
- Publisher status (aggregated counts)

No database dependency. No authentication. No authorization.
Monitoring data is ephemeral — restart clears all buffers.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.monitoring import (
    MonitoringAlertListResponse,
    MonitoringAlertSchema,
    MonitoringConnectionStatusResponse,
    MonitoringEventListResponse,
    MonitoringEventSchema,
    MonitoringStatusResponse,
)
from app.services.monitoring.alert_buffer import AlertFilter
from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
    MonitoringFilter,
)
from app.services.monitoring.publisher import get_monitoring_publisher

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/monitoring",
    tags=["Monitoring"],
)


def _require_publisher():
    """Return the EventPublisher or raise 503."""
    publisher = get_monitoring_publisher()
    if publisher is None:
        raise HTTPException(
            status_code=503,
            detail="Monitoring system not initialized",
        )
    return publisher


# ---------------------------------------------------------------------------
# GET /monitoring/status
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=MonitoringStatusResponse,
    summary="Monitoring system status",
)
def get_monitoring_status() -> MonitoringStatusResponse:
    """Return aggregated status from in-memory monitoring components.

    Values come from the actual EventPublisher and its buffers.
    """
    publisher = _require_publisher()
    status = publisher.status()
    return MonitoringStatusResponse(
        active_connections=status["active_connections"],
        buffered_events=status["buffered_events"],
        buffered_alerts=status["buffered_alerts"],
        total_published=status["total_published"],
        event_buffer_capacity=publisher._event_buffer.capacity,
        alert_buffer_capacity=publisher._alert_buffer.capacity,
        max_connections=publisher._connection_manager.max_connections,
    )


# ---------------------------------------------------------------------------
# GET /monitoring/events
# ---------------------------------------------------------------------------


@router.get(
    "/events",
    response_model=MonitoringEventListResponse,
    summary="Recent monitoring events",
)
def get_monitoring_events(
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
    category: EventCategory | None = Query(None, description="Filter by category"),
    event_type: EventType | None = Query(None, description="Filter by event type"),
    min_severity: EventSeverity | None = Query(
        None, description="Minimum severity level"
    ),
    exam_id: int | None = Query(None, description="Filter by exam ID"),
    hall_id: int | None = Query(None, description="Filter by hall ID"),
) -> MonitoringEventListResponse:
    """Return recent events from the in-memory ring buffer.

    Supports optional filtering by category, event_type, min_severity,
    exam_id, and hall_id. No page/page_size — ring buffer only has limit.
    """
    publisher = _require_publisher()

    filter_obj = MonitoringFilter(
        exam_id=exam_id,
        hall_id=hall_id,
        category=category,
        event_type=event_type,
        min_severity=min_severity if min_severity is not None else EventSeverity.INFO,
    )

    events = publisher._event_buffer.query(filter_obj, limit=limit)
    items = [
        MonitoringEventSchema(**e.to_dict()) for e in events
    ]
    return MonitoringEventListResponse(items=items, count=len(items))


# ---------------------------------------------------------------------------
# GET /monitoring/alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=MonitoringAlertListResponse,
    summary="Recent monitoring alerts",
)
def get_monitoring_alerts(
    limit: int = Query(50, ge=1, le=200, description="Max alerts to return"),
    severity: EventSeverity | None = Query(None, description="Filter by severity"),
    event_type: EventType | None = Query(
        None, description="Filter by event type"
    ),
    exam_id: int | None = Query(None, description="Filter by exam ID"),
    hall_id: int | None = Query(None, description="Filter by hall ID"),
) -> MonitoringAlertListResponse:
    """Return recent alerts from the in-memory ring buffer.

    Supports optional filtering by severity, event_type, exam_id, and hall_id.
    No page/page_size — ring buffer only has limit.
    """
    publisher = _require_publisher()

    alert_filter = AlertFilter(
        severity=severity,
        event_type=event_type,
        exam_id=exam_id,
        hall_id=hall_id,
    )

    alerts = publisher._alert_buffer.query(alert_filter, limit=limit)
    items = [
        MonitoringAlertSchema(**a.to_dict()) for a in alerts
    ]
    return MonitoringAlertListResponse(items=items, count=len(items))


# ---------------------------------------------------------------------------
# GET /monitoring/connections
# ---------------------------------------------------------------------------


@router.get(
    "/connections",
    response_model=MonitoringConnectionStatusResponse,
    summary="WebSocket connection status",
)
def get_monitoring_connections() -> MonitoringConnectionStatusResponse:
    """Return active WebSocket connection count and maximum capacity.

    Does not expose client IPs, credentials, or internal connection details.
    """
    publisher = _require_publisher()
    return MonitoringConnectionStatusResponse(
        active_connections=publisher._connection_manager.active_count,
        max_connections=publisher._connection_manager.max_connections,
    )

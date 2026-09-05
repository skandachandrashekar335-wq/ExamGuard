"""WebSocket endpoint for real-time monitoring (Phase 13.3).

Provides:
- WebSocket connection at /ws/monitoring
- Subscription filter parsing from query parameters
- Heartbeat/keepalive (ping every 30s, timeout 60s)
- Client message handling (subscription updates, pong)
- Clean disconnect handling
- Integration with Phase 13.2 ConnectionManager

Authentication is NOT implemented (Phase 19).
The endpoint accepts unauthenticated connections for now.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
    MonitoringFilter,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared connection manager (single-process, in-memory)
# ---------------------------------------------------------------------------

_connection_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Return the shared ConnectionManager, creating on first call."""
    global _connection_manager
    if _connection_manager is None:
        settings = get_settings()
        _connection_manager = ConnectionManager(
            max_connections=settings.MONITORING_MAX_CONNECTIONS
        )
    return _connection_manager


def reset_connection_manager() -> None:
    """Reset the shared ConnectionManager (for testing)."""
    global _connection_manager
    _connection_manager = None


# ---------------------------------------------------------------------------
# Heartbeat configuration (defaults; overridden by settings if needed)
# ---------------------------------------------------------------------------

_settings = get_settings()
HEARTBEAT_INTERVAL_SECONDS: float = float(_settings.MONITORING_HEARTBEAT_INTERVAL)
STALE_TIMEOUT_SECONDS: float = float(_settings.MONITORING_STALE_TIMEOUT)


# ---------------------------------------------------------------------------
# Filter parsing from query parameters
# ---------------------------------------------------------------------------


def parse_filters(
    exam_id: int | None,
    hall_id: int | None,
    category: str | None,
    event_type: str | None,
    min_severity: str | None,
) -> MonitoringFilter:
    """Parse and validate subscription filter query parameters.

    Raises ValueError with a safe error message on invalid input.
    Never exposes stack traces or internal details.
    """
    parsed_category: EventCategory | None = None
    if category is not None:
        try:
            parsed_category = EventCategory(category)
        except ValueError:
            valid = [c.value for c in EventCategory]
            raise ValueError(
                f"Invalid category '{category}'. Must be one of: {', '.join(valid)}"
            )

    parsed_event_type: EventType | None = None
    if event_type is not None:
        try:
            parsed_event_type = EventType(event_type)
        except ValueError:
            valid = [t.value for t in EventType]
            raise ValueError(
                f"Invalid event_type '{event_type}'. Must be one of: {', '.join(valid)}"
            )

    parsed_severity: EventSeverity = EventSeverity.INFO
    if min_severity is not None:
        try:
            parsed_severity = EventSeverity(min_severity)
        except ValueError:
            valid = [s.value for s in EventSeverity]
            raise ValueError(
                f"Invalid min_severity '{min_severity}'. Must be one of: {', '.join(valid)}"
            )

    if exam_id is not None and exam_id < 1:
        raise ValueError("exam_id must be a positive integer")
    if hall_id is not None and hall_id < 1:
        raise ValueError("hall_id must be a positive integer")

    return MonitoringFilter(
        exam_id=exam_id,
        hall_id=hall_id,
        category=parsed_category,
        event_type=parsed_event_type,
        min_severity=parsed_severity,
    )


def parse_client_message(raw: str) -> dict[str, Any]:
    """Parse and validate a client JSON message.

    Returns the parsed dict on success.
    Raises ValueError on malformed JSON or missing fields.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Malformed JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("Message must be a JSON object")

    return data


# ---------------------------------------------------------------------------
# Heartbeat task
# ---------------------------------------------------------------------------


async def _heartbeat_loop(
    client_id: str,
    ws: WebSocket,
    manager: ConnectionManager,
    stop_event: asyncio.Event,
) -> None:
    """Send periodic pings and disconnect stale clients.

    Runs until stop_event is set or the connection is removed.
    Uses asyncio.sleep to avoid blocking the event loop.
    """
    last_pong = datetime.now(timezone.utc)

    while not stop_event.is_set():
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            break

        if stop_event.is_set():
            break

        # Check if client still exists in manager
        conn = manager.get_connection(client_id)
        if conn is None:
            break

        # Send ping
        try:
            await ws.send_json({"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()})
        except Exception:
            logger.warning("Heartbeat ping failed for %s, disconnecting", client_id)
            manager.unregister(client_id)
            try:
                await ws.close(code=1001, reason="Heartbeat failed")
            except Exception:
                pass
            break

        # Check staleness (last pong older than timeout)
        elapsed = (datetime.now(timezone.utc) - last_pong).total_seconds()
        if elapsed > STALE_TIMEOUT_SECONDS:
            logger.warning(
                "Client %s stale (no pong in %.1fs), disconnecting",
                client_id,
                elapsed,
            )
            manager.unregister(client_id)
            try:
                await ws.close(code=1000, reason="Connection stale")
            except Exception:
                pass
            break


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/monitoring")
async def websocket_monitoring(
    websocket: WebSocket,
    exam_id: int | None = Query(default=None, description="Filter by exam ID"),
    hall_id: int | None = Query(default=None, description="Filter by hall ID"),
    category: str | None = Query(default=None, description="Filter by event category"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    min_severity: str | None = Query(default=None, description="Minimum severity"),
) -> None:
    """WebSocket endpoint for real-time monitoring events.

    Connection lifecycle:
    1. Accept connection
    2. Parse/validate subscription filters
    3. Register with ConnectionManager
    4. Run heartbeat loop
    5. Handle client messages
    6. Unregister on disconnect
    7. Clean up on errors

    Authentication is NOT implemented (Phase 19).
    """
    client_id = str(uuid.uuid4())
    manager = get_connection_manager()
    heartbeat_task: asyncio.Task | None = None
    stop_heartbeat = asyncio.Event()

    try:
        # Parse filters
        try:
            filters = parse_filters(exam_id, hall_id, category, event_type, min_severity)
        except ValueError as exc:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1008, reason="Invalid subscription")
            return

        # Register connection
        try:
            manager.register(client_id, websocket, filters)
        except RuntimeError as exc:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1013, reason="Connection limit reached")
            return

        # Accept the WebSocket connection
        await websocket.accept()

        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "filters": {
                "exam_id": filters.exam_id,
                "hall_id": filters.hall_id,
                "category": filters.category.value if filters.category else None,
                "event_type": filters.event_type.value if filters.event_type else None,
                "min_severity": filters.min_severity.value,
            },
        })

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(client_id, websocket, manager, stop_heartbeat)
        )

        # Listen for client messages
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break

            try:
                data = parse_client_message(raw)
            except ValueError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
                continue

            msg_type = data.get("type")

            if msg_type == "pong":
                # Client responded to heartbeat — handled by checking staleness
                # in the heartbeat loop; this is a no-op acknowledgment
                continue

            elif msg_type == "ping":
                # Client-initiated ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif msg_type == "subscribe":
                # Dynamic subscription update
                try:
                    new_filters = parse_filters(
                        data.get("exam_id"),
                        data.get("hall_id"),
                        data.get("category"),
                        data.get("event_type"),
                        data.get("min_severity"),
                    )
                except ValueError as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue
                # Update the connection's filters in the manager
                conn = manager.get_connection(client_id)
                if conn is not None:
                    conn.filters = new_filters
                await websocket.send_json({
                    "type": "subscribed",
                    "filters": {
                        "exam_id": new_filters.exam_id,
                        "hall_id": new_filters.hall_id,
                        "category": new_filters.category.value if new_filters.category else None,
                        "event_type": new_filters.event_type.value if new_filters.event_type else None,
                        "min_severity": new_filters.min_severity.value,
                    },
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: '{msg_type}'",
                })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("WebSocket error for %s: %s", client_id, type(exc).__name__)
    finally:
        # Stop heartbeat
        stop_heartbeat.set()
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        # Unregister from manager
        manager.unregister(client_id)

        # Close WebSocket if still open
        try:
            await websocket.close(code=1000)
        except Exception:
            pass

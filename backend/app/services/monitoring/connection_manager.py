"""In-process connection manager for monitoring WebSocket clients.

Tracks connected clients, matches events against client filters,
broadcasts matching events. Transport-agnostic: Phase 13.3 plugs
the actual WebSocket transport.

Thread-safe. Single-process only.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from app.services.monitoring.events import MonitoringEvent, MonitoringFilter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transport abstraction
# ---------------------------------------------------------------------------


@runtime_checkable
class MessageTransport(Protocol):
    """Protocol for sending messages to a connected client.

    Phase 13.3 will implement this with FastAPI WebSocket.
    """

    async def send_text(self, data: str) -> None: ...


# ---------------------------------------------------------------------------
# Connection representation
# ---------------------------------------------------------------------------


@dataclass
class ClientConnection:
    """Internal representation of a connected monitoring client."""

    client_id: str
    transport: MessageTransport
    filters: MonitoringFilter
    user_id: int | None = None  # placeholder for Phase 19 auth
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_event_at: datetime | None = None


# ---------------------------------------------------------------------------
# Connection Manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Manages connected monitoring clients and broadcasts events.

    Thread-safe. Transport-agnostic.
    """

    def __init__(self, max_connections: int = 100) -> None:
        if max_connections < 1:
            raise ValueError(f"max_connections must be >= 1, got {max_connections}")
        self._max_connections = max_connections
        self._connections: dict[str, ClientConnection] = {}
        self._lock = threading.Lock()

    @property
    def max_connections(self) -> int:
        return self._max_connections

    @property
    def active_count(self) -> int:
        """Number of currently active connections."""
        with self._lock:
            return len(self._connections)

    def register(
        self,
        client_id: str,
        transport: MessageTransport,
        filters: MonitoringFilter | None = None,
        user_id: int | None = None,
    ) -> ClientConnection:
        """Register a new client connection.

        If client_id already exists, replaces the old connection.
        Raises RuntimeError if at max capacity and client_id is new.
        """
        with self._lock:
            if client_id in self._connections:
                # Replace existing connection for same client_id
                old = self._connections[client_id]
                self._connections[client_id] = ClientConnection(
                    client_id=client_id,
                    transport=transport,
                    filters=filters or MonitoringFilter(),
                    user_id=user_id or old.user_id,
                )
                return self._connections[client_id]

            if len(self._connections) >= self._max_connections:
                raise RuntimeError(
                    f"Max connections ({self._max_connections}) reached. "
                    f"Client {client_id} rejected."
                )

            conn = ClientConnection(
                client_id=client_id,
                transport=transport,
                filters=filters or MonitoringFilter(),
                user_id=user_id,
            )
            self._connections[client_id] = conn
            return conn

    def unregister(self, client_id: str) -> None:
        """Remove a client connection."""
        with self._lock:
            self._connections.pop(client_id, None)

    def get_connection(self, client_id: str) -> ClientConnection | None:
        """Get a client connection by ID."""
        with self._lock:
            return self._connections.get(client_id)

    async def broadcast(self, event: MonitoringEvent) -> int:
        """Broadcast an event to all matching clients.

        Returns the number of clients the event was sent to.
        Failed clients are silently removed.
        """
        with self._lock:
            connections = list(self._connections.items())

        sent_count = 0
        failed_clients: list[str] = []

        for client_id, conn in connections:
            if not conn.filters.matches(event):
                continue

            try:
                await conn.transport.send_text(
                    __import__("json").dumps(event.to_dict())
                )
                with self._lock:
                    if client_id in self._connections:
                        self._connections[client_id].last_event_at = (
                            datetime.now(timezone.utc)
                        )
                sent_count += 1
            except Exception:
                logger.warning(
                    "Failed to send to client %s, removing connection",
                    client_id,
                    exc_info=True,
                )
                failed_clients.append(client_id)

        # Remove failed clients
        if failed_clients:
            with self._lock:
                for cid in failed_clients:
                    self._connections.pop(cid, None)

        return sent_count

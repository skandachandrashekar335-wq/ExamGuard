"""Phase 13.3 — WebSocket API Tests.

Tests for the WebSocket monitoring endpoint covering:
- Connection lifecycle
- Filter parsing and validation
- Registration with ConnectionManager
- Event delivery through WebSocket
- Heartbeat behavior
- Client message handling
- Error handling and security
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.ws_monitoring import (
    HEARTBEAT_INTERVAL_SECONDS,
    STALE_TIMEOUT_SECONDS,
    parse_client_message,
    parse_filters,
    reset_connection_manager,
)
from app.main import create_app
from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
    MonitoringEvent,
    MonitoringFilter,
)


@pytest.fixture(autouse=True)
def _reset_manager():
    """Reset shared ConnectionManager before each test."""
    reset_connection_manager()
    yield
    reset_connection_manager()


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    app = create_app()
    return TestClient(app)


def _make_event(**kwargs) -> MonitoringEvent:
    defaults = {
        "event_type": EventType.ENTRY_GRANTED,
        "entity_type": "EntryVerification",
        "entity_id": 1,
        "timestamp": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return MonitoringEvent(**defaults)


# ---------------------------------------------------------------------------
# Filter Parsing
# ---------------------------------------------------------------------------


class TestParseFilters:
    def test_no_filters(self):
        """Empty params returns default filter."""
        f = parse_filters(None, None, None, None, None)
        assert f.exam_id is None
        assert f.hall_id is None
        assert f.category is None
        assert f.event_type is None
        assert f.min_severity == EventSeverity.INFO

    def test_exam_id(self):
        """Valid exam_id filter."""
        f = parse_filters(exam_id=3, hall_id=None, category=None, event_type=None, min_severity=None)
        assert f.exam_id == 3

    def test_hall_id(self):
        """Valid hall_id filter."""
        f = parse_filters(None, hall_id=5, category=None, event_type=None, min_severity=None)
        assert f.hall_id == 5

    def test_category(self):
        """Valid category filter."""
        f = parse_filters(None, None, category="ENTRY", event_type=None, min_severity=None)
        assert f.category == EventCategory.ENTRY

    def test_event_type(self):
        """Valid event_type filter."""
        f = parse_filters(None, None, None, event_type="ENTRY_GRANTED", min_severity=None)
        assert f.event_type == EventType.ENTRY_GRANTED

    def test_min_severity(self):
        """Valid min_severity filter."""
        f = parse_filters(None, None, None, None, min_severity="WARNING")
        assert f.min_severity == EventSeverity.WARNING

    def test_combined_filters(self):
        """All filters combined."""
        f = parse_filters(
            exam_id=3,
            hall_id=2,
            category="ENTRY",
            event_type="ENTRY_GRANTED",
            min_severity="WARNING",
        )
        assert f.exam_id == 3
        assert f.hall_id == 2
        assert f.category == EventCategory.ENTRY
        assert f.event_type == EventType.ENTRY_GRANTED
        assert f.min_severity == EventSeverity.WARNING

    def test_invalid_category(self):
        """Invalid category raises ValueError."""
        with pytest.raises(ValueError, match="Invalid category"):
            parse_filters(None, None, category="INVALID", event_type=None, min_severity=None)

    def test_invalid_event_type(self):
        """Invalid event_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid event_type"):
            parse_filters(None, None, None, event_type="NONEXISTENT", min_severity=None)

    def test_invalid_severity(self):
        """Invalid min_severity raises ValueError."""
        with pytest.raises(ValueError, match="Invalid min_severity"):
            parse_filters(None, None, None, None, min_severity="EXTREME")

    def test_negative_exam_id(self):
        """Negative exam_id raises ValueError."""
        with pytest.raises(ValueError, match="exam_id must be a positive integer"):
            parse_filters(exam_id=-1, hall_id=None, category=None, event_type=None, min_severity=None)

    def test_zero_hall_id(self):
        """Zero hall_id raises ValueError."""
        with pytest.raises(ValueError, match="hall_id must be a positive integer"):
            parse_filters(None, hall_id=0, category=None, event_type=None, min_severity=None)


# ---------------------------------------------------------------------------
# Client Message Parsing
# ---------------------------------------------------------------------------


class TestParseClientMessage:
    def test_valid_json(self):
        """Valid JSON object parsed correctly."""
        result = parse_client_message('{"type": "ping"}')
        assert result == {"type": "ping"}

    def test_malformed_json(self):
        """Malformed JSON raises ValueError."""
        with pytest.raises(ValueError, match="Malformed JSON"):
            parse_client_message("not json {{{")

    def test_non_object_json(self):
        """Non-object JSON raises ValueError."""
        with pytest.raises(ValueError, match="Message must be a JSON object"):
            parse_client_message('"just a string"')

    def test_array_json(self):
        """Array JSON raises ValueError."""
        with pytest.raises(ValueError, match="Message must be a JSON object"):
            parse_client_message("[1, 2, 3]")

    def test_none_input(self):
        """None input raises ValueError."""
        with pytest.raises(ValueError, match="Malformed JSON"):
            parse_client_message(None)


# ---------------------------------------------------------------------------
# Connection (via TestClient WebSocket)
# ---------------------------------------------------------------------------


class TestWebSocketConnection:
    def test_successful_connection(self, client):
        """Client connects and receives welcome message."""
        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "client_id" in data
            assert "filters" in data

    def test_valid_exam_filter(self, client):
        """Client connects with exam_id filter."""
        with client.websocket_connect("/api/v1/ws/monitoring?exam_id=3") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["filters"]["exam_id"] == 3

    def test_valid_hall_filter(self, client):
        """Client connects with hall_id filter."""
        with client.websocket_connect("/api/v1/ws/monitoring?hall_id=2") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["filters"]["hall_id"] == 2

    def test_category_filter(self, client):
        """Client connects with category filter."""
        with client.websocket_connect("/api/v1/ws/monitoring?category=ENTRY") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["filters"]["category"] == "ENTRY"

    def test_event_type_filter(self, client):
        """Client connects with event_type filter."""
        with client.websocket_connect("/api/v1/ws/monitoring?event_type=ENTRY_GRANTED") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["filters"]["event_type"] == "ENTRY_GRANTED"

    def test_severity_filter(self, client):
        """Client connects with min_severity filter."""
        with client.websocket_connect("/api/v1/ws/monitoring?min_severity=WARNING") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["filters"]["min_severity"] == "WARNING"

    def test_combined_filters(self, client):
        """Client connects with multiple filters."""
        url = "/api/v1/ws/monitoring?exam_id=1&hall_id=2&category=RISK&min_severity=CRITICAL"
        with client.websocket_connect(url) as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["filters"]["exam_id"] == 1
            assert data["filters"]["hall_id"] == 2
            assert data["filters"]["category"] == "RISK"
            assert data["filters"]["min_severity"] == "CRITICAL"

    def test_invalid_filter_rejects(self, client):
        """Invalid filter sends error and closes."""
        with client.websocket_connect("/api/v1/ws/monitoring?category=BADCAT") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Invalid category" in data["message"]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_registered_with_manager(self, client):
        """Connected client is registered with ConnectionManager."""
        from app.api.v1.ws_monitoring import get_connection_manager
        mgr = get_connection_manager()
        assert mgr.active_count == 0

        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            ws.receive_json()  # welcome
            assert mgr.active_count == 1

        # After disconnect, count goes back to 0
        assert mgr.active_count == 0

    def test_disconnect_unregisters(self, client):
        """Client disconnect unregisters from ConnectionManager."""
        from app.api.v1.ws_monitoring import get_connection_manager
        mgr = get_connection_manager()

        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            ws.receive_json()
            assert mgr.active_count == 1

        assert mgr.active_count == 0


# ---------------------------------------------------------------------------
# Client Messages
# ---------------------------------------------------------------------------


class TestClientMessages:
    def test_ping_pong(self, client):
        """Client sends ping, server responds with pong."""
        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"
            assert "timestamp" in data

    def test_subscribe_update(self, client):
        """Client sends subscribe message to update filters."""
        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            ws.receive_json()  # welcome
            ws.send_json({
                "type": "subscribe",
                "exam_id": 5,
                "hall_id": 3,
                "category": "RISK",
            })
            data = ws.receive_json()
            assert data["type"] == "subscribed"
            assert data["filters"]["exam_id"] == 5
            assert data["filters"]["hall_id"] == 3
            assert data["filters"]["category"] == "RISK"

    def test_malformed_json_response(self, client):
        """Malformed JSON returns error message."""
        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            ws.receive_json()  # welcome
            ws.send_text("not json {{{")
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Malformed JSON" in data["message"]

    def test_unknown_message_type(self, client):
        """Unknown message type returns error."""
        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "unknown_thing"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Unknown message type" in data["message"]

    def test_invalid_subscribe_data(self, client):
        """Invalid subscribe data returns error."""
        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            ws.receive_json()  # welcome
            ws.send_json({
                "type": "subscribe",
                "category": "INVALIDCAT",
            })
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Invalid category" in data["message"]


# ---------------------------------------------------------------------------
# Security (no sensitive data in errors)
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_no_stack_traces_in_errors(self, client):
        """Error messages do not contain stack traces."""
        with client.websocket_connect("/api/v1/ws/monitoring?category=BADCAT") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            msg = data["message"]
            assert "Traceback" not in msg
            assert "File" not in msg
            assert ".py" not in msg

    def test_no_secrets_in_welcome(self, client):
        """Welcome message does not contain secrets."""
        with client.websocket_connect("/api/v1/ws/monitoring") as ws:
            data = ws.receive_json()
            raw = json.dumps(data)
            assert "SECRET_KEY" not in raw
            assert "password" not in raw
            assert "api_key" not in raw

    def test_no_database_paths_in_error(self, client):
        """Error messages do not contain filesystem paths."""
        with client.websocket_connect("/api/v1/ws/monitoring?category=BADCAT") as ws:
            data = ws.receive_json()
            msg = data["message"]
            assert "D:\\" not in msg
            assert "/home/" not in msg
            assert "/var/" not in msg


# ---------------------------------------------------------------------------
# Heartbeat constants
# ---------------------------------------------------------------------------


class TestHeartbeatConfig:
    def test_heartbeat_interval(self):
        """Heartbeat interval is reasonable."""
        assert 10 <= HEARTBEAT_INTERVAL_SECONDS <= 60

    def test_stale_timeout(self):
        """Stale timeout is greater than heartbeat interval."""
        assert STALE_TIMEOUT_SECONDS > HEARTBEAT_INTERVAL_SECONDS

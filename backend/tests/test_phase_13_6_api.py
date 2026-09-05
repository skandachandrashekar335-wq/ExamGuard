"""Phase 13.6 — Monitoring REST API Tests.

Tests for the monitoring REST endpoints covering:
- Route registration
- Status endpoint
- Events endpoint with filtering and limit
- Alerts endpoint with filtering and limit
- Connections endpoint
- 503 when publisher unavailable
- Schema/response contract
- Security/privacy (no sensitive data)

Uses real EventPublisher and in-memory ring buffers.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.monitoring.alert_buffer import AlertBuffer
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
    MonitoringEvent,
)
from app.services.monitoring.publisher import (
    get_monitoring_publisher,
    init_monitoring_publisher,
)


@pytest.fixture(autouse=True)
def _setup_publisher():
    """Set up a fresh EventPublisher for each test."""
    mgr = ConnectionManager(max_connections=10)
    ebuf = EventBuffer(capacity=100)
    abuf = AlertBuffer(capacity=50)
    pub = EventPublisher(mgr, ebuf, abuf)
    init_monitoring_publisher(pub)
    yield
    init_monitoring_publisher(None)


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
# Route Registration
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    def test_status_route_exists(self, client):
        resp = client.get("/api/v1/monitoring/status")
        assert resp.status_code == 200

    def test_events_route_exists(self, client):
        resp = client.get("/api/v1/monitoring/events")
        assert resp.status_code == 200

    def test_alerts_route_exists(self, client):
        resp = client.get("/api/v1/monitoring/alerts")
        assert resp.status_code == 200

    def test_connections_route_exists(self, client):
        resp = client.get("/api/v1/monitoring/connections")
        assert resp.status_code == 200

    def test_wrong_method_post_status(self, client):
        resp = client.post("/api/v1/monitoring/status")
        assert resp.status_code in (405, 404)

    def test_wrong_method_post_events(self, client):
        resp = client.post("/api/v1/monitoring/events")
        assert resp.status_code in (405, 404)

    def test_wrong_method_post_alerts(self, client):
        resp = client.post("/api/v1/monitoring/alerts")
        assert resp.status_code in (405, 404)

    def test_wrong_method_post_connections(self, client):
        resp = client.post("/api/v1/monitoring/connections")
        assert resp.status_code in (405, 404)


# ---------------------------------------------------------------------------
# GET /monitoring/status
# ---------------------------------------------------------------------------


class TestMonitoringStatus:
    def test_status_response_fields(self, client):
        resp = client.get("/api/v1/monitoring/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_connections" in data
        assert "buffered_events" in data
        assert "buffered_alerts" in data
        assert "total_published" in data
        assert "event_buffer_capacity" in data
        assert "alert_buffer_capacity" in data
        assert "max_connections" in data

    def test_status_empty_buffers(self, client):
        resp = client.get("/api/v1/monitoring/status")
        data = resp.json()
        assert data["buffered_events"] == 0
        assert data["buffered_alerts"] == 0
        assert data["total_published"] == 0
        assert data["active_connections"] == 0

    def test_status_real_counts(self, client):
        publisher = get_monitoring_publisher()
        event = _make_event()
        publisher.publish(event)
        resp = client.get("/api/v1/monitoring/status")
        data = resp.json()
        assert data["buffered_events"] == 1
        assert data["total_published"] == 1

    def test_status_real_capacities(self, client):
        publisher = get_monitoring_publisher()
        resp = client.get("/api/v1/monitoring/status")
        data = resp.json()
        assert data["event_buffer_capacity"] == publisher._event_buffer.capacity
        assert data["alert_buffer_capacity"] == publisher._alert_buffer.capacity
        assert data["max_connections"] == publisher._connection_manager.max_connections

    def test_status_503_unavailable(self, client):
        init_monitoring_publisher(None)
        resp = client.get("/api/v1/monitoring/status")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /monitoring/events
# ---------------------------------------------------------------------------


class TestMonitoringEvents:
    def test_empty_buffer(self, client):
        resp = client.get("/api/v1/monitoring/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["count"] == 0

    def test_published_events_returned(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        publisher.publish(_make_event(event_type=EventType.ENTRY_DENIED))
        resp = client.get("/api/v1/monitoring/events")
        data = resp.json()
        assert data["count"] == 2

    def test_newest_first_ordering(self, client):
        publisher = get_monitoring_publisher()
        e1 = _make_event(
            event_type=EventType.ENTRY_GRANTED,
            entity_id=1,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        e2 = _make_event(
            event_type=EventType.ENTRY_DENIED,
            entity_id=2,
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        publisher.publish(e1)
        publisher.publish(e2)
        resp = client.get("/api/v1/monitoring/events")
        data = resp.json()
        assert data["items"][0]["entity_id"] == 2
        assert data["items"][1]["entity_id"] == 1

    def test_category_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        publisher.publish(_make_event(event_type=EventType.RISK_HIGH))
        resp = client.get(
            "/api/v1/monitoring/events",
            params={"category": "ENTRY"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["category"] == "ENTRY"

    def test_event_type_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        publisher.publish(_make_event(event_type=EventType.ENTRY_DENIED))
        resp = client.get(
            "/api/v1/monitoring/events",
            params={"event_type": "ENTRY_GRANTED"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["event_type"] == "ENTRY_GRANTED"

    def test_min_severity_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        publisher.publish(_make_event(event_type=EventType.RISK_CRITICAL))
        resp = client.get(
            "/api/v1/monitoring/events",
            params={"min_severity": "CRITICAL"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["severity"] == "CRITICAL"

    def test_exam_id_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED, exam_id=1))
        publisher.publish(_make_event(event_type=EventType.ENTRY_DENIED, exam_id=2))
        resp = client.get(
            "/api/v1/monitoring/events",
            params={"exam_id": 1},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["exam_id"] == 1

    def test_hall_id_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED, hall_id=10))
        publisher.publish(_make_event(event_type=EventType.ENTRY_DENIED, hall_id=20))
        resp = client.get(
            "/api/v1/monitoring/events",
            params={"hall_id": 10},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["hall_id"] == 10

    def test_combined_filters(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(
            _make_event(event_type=EventType.ENTRY_GRANTED, exam_id=1, hall_id=10)
        )
        publisher.publish(
            _make_event(event_type=EventType.ENTRY_GRANTED, exam_id=2, hall_id=10)
        )
        publisher.publish(
            _make_event(event_type=EventType.ENTRY_DENIED, exam_id=1, hall_id=10)
        )
        resp = client.get(
            "/api/v1/monitoring/events",
            params={"exam_id": 1, "event_type": "ENTRY_GRANTED"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["exam_id"] == 1
        assert data["items"][0]["event_type"] == "ENTRY_GRANTED"

    def test_default_limit_50(self, client):
        publisher = get_monitoring_publisher()
        for i in range(60):
            publisher.publish(
                _make_event(
                    event_type=EventType.ENTRY_GRANTED,
                    entity_id=i,
                    timestamp=datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc),
                )
            )
        resp = client.get("/api/v1/monitoring/events")
        data = resp.json()
        assert data["count"] == 50

    def test_custom_limit(self, client):
        publisher = get_monitoring_publisher()
        for i in range(10):
            publisher.publish(
                _make_event(
                    event_type=EventType.ENTRY_GRANTED,
                    entity_id=i,
                    timestamp=datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc),
                )
            )
        resp = client.get("/api/v1/monitoring/events", params={"limit": 5})
        data = resp.json()
        assert data["count"] == 5

    def test_limit_200_accepted(self, client):
        resp = client.get("/api/v1/monitoring/events", params={"limit": 200})
        assert resp.status_code == 200

    def test_limit_201_rejected(self, client):
        resp = client.get("/api/v1/monitoring/events", params={"limit": 201})
        assert resp.status_code == 422

    def test_limit_0_rejected(self, client):
        resp = client.get("/api/v1/monitoring/events", params={"limit": 0})
        assert resp.status_code == 422

    def test_negative_limit_rejected(self, client):
        resp = client.get("/api/v1/monitoring/events", params={"limit": -1})
        assert resp.status_code == 422

    def test_503_unavailable(self, client):
        init_monitoring_publisher(None)
        resp = client.get("/api/v1/monitoring/events")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /monitoring/alerts
# ---------------------------------------------------------------------------


class TestMonitoringAlerts:
    def test_empty_buffer(self, client):
        resp = client.get("/api/v1/monitoring/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["count"] == 0

    def test_alert_producing_event_returned(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_ESCALATED))
        resp = client.get("/api/v1/monitoring/alerts")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["event_type"] == "ENTRY_ESCALATED"

    def test_no_alert_for_info_event(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        resp = client.get("/api/v1/monitoring/alerts")
        data = resp.json()
        assert data["count"] == 0

    def test_severity_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_ESCALATED))
        publisher.publish(_make_event(event_type=EventType.RISK_CRITICAL))
        resp = client.get(
            "/api/v1/monitoring/alerts",
            params={"severity": "CRITICAL"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["severity"] == "CRITICAL"

    def test_event_type_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_ESCALATED))
        publisher.publish(_make_event(event_type=EventType.RISK_HIGH))
        resp = client.get(
            "/api/v1/monitoring/alerts",
            params={"event_type": "ENTRY_ESCALATED"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["event_type"] == "ENTRY_ESCALATED"

    def test_exam_id_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(
            _make_event(event_type=EventType.ENTRY_ESCALATED, exam_id=1)
        )
        publisher.publish(
            _make_event(event_type=EventType.ENTRY_ESCALATED, exam_id=2)
        )
        resp = client.get(
            "/api/v1/monitoring/alerts",
            params={"exam_id": 1},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["exam_id"] == 1

    def test_hall_id_filter(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(
            _make_event(event_type=EventType.RISK_HIGH, hall_id=10)
        )
        publisher.publish(
            _make_event(event_type=EventType.RISK_HIGH, hall_id=20)
        )
        resp = client.get(
            "/api/v1/monitoring/alerts",
            params={"hall_id": 10},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["hall_id"] == 10

    def test_combined_filters(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(
            _make_event(event_type=EventType.ENTRY_ESCALATED, exam_id=1)
        )
        publisher.publish(
            _make_event(event_type=EventType.RISK_HIGH, exam_id=1)
        )
        publisher.publish(
            _make_event(event_type=EventType.ENTRY_ESCALATED, exam_id=2)
        )
        resp = client.get(
            "/api/v1/monitoring/alerts",
            params={"exam_id": 1, "event_type": "ENTRY_ESCALATED"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["event_type"] == "ENTRY_ESCALATED"

    def test_default_limit(self, client):
        publisher = get_monitoring_publisher()
        for i in range(60):
            publisher.publish(
                _make_event(
                    event_type=EventType.RISK_CRITICAL,
                    entity_id=i,
                    timestamp=datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc),
                )
            )
        resp = client.get("/api/v1/monitoring/alerts")
        data = resp.json()
        assert data["count"] == 50

    def test_custom_limit(self, client):
        publisher = get_monitoring_publisher()
        for i in range(10):
            publisher.publish(
                _make_event(
                    event_type=EventType.RISK_CRITICAL,
                    entity_id=i,
                    timestamp=datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc),
                )
            )
        resp = client.get("/api/v1/monitoring/alerts", params={"limit": 5})
        data = resp.json()
        assert data["count"] == 5

    def test_limit_200_accepted(self, client):
        resp = client.get("/api/v1/monitoring/alerts", params={"limit": 200})
        assert resp.status_code == 200

    def test_limit_201_rejected(self, client):
        resp = client.get("/api/v1/monitoring/alerts", params={"limit": 201})
        assert resp.status_code == 422

    def test_limit_0_rejected(self, client):
        resp = client.get("/api/v1/monitoring/alerts", params={"limit": 0})
        assert resp.status_code == 422

    def test_negative_limit_rejected(self, client):
        resp = client.get("/api/v1/monitoring/alerts", params={"limit": -1})
        assert resp.status_code == 422

    def test_503_unavailable(self, client):
        init_monitoring_publisher(None)
        resp = client.get("/api/v1/monitoring/alerts")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /monitoring/connections
# ---------------------------------------------------------------------------


class TestMonitoringConnections:
    def test_connections_response_fields(self, client):
        resp = client.get("/api/v1/monitoring/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_connections" in data
        assert "max_connections" in data

    def test_connections_real_counts(self, client):
        publisher = get_monitoring_publisher()
        resp = client.get("/api/v1/monitoring/connections")
        data = resp.json()
        assert data["active_connections"] == 0
        assert data["max_connections"] == publisher._connection_manager.max_connections

    def test_503_unavailable(self, client):
        init_monitoring_publisher(None)
        resp = client.get("/api/v1/monitoring/connections")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Schema / Response Contract
# ---------------------------------------------------------------------------


class TestSchemaContract:
    def test_event_fields(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(
            _make_event(
                event_type=EventType.ENTRY_GRANTED,
                exam_id=1,
                hall_id=10,
                student_id=100,
                entry_point_id=5,
            )
        )
        resp = client.get("/api/v1/monitoring/events")
        item = resp.json()["items"][0]
        expected_keys = {
            "event_id",
            "event_type",
            "category",
            "severity",
            "entity_type",
            "entity_id",
            "timestamp",
            "exam_id",
            "hall_id",
            "student_id",
            "entry_point_id",
            "payload",
        }
        assert expected_keys == set(item.keys())

    def test_alert_fields(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(
            _make_event(
                event_type=EventType.ENTRY_ESCALATED,
                exam_id=1,
                hall_id=10,
                student_id=100,
            )
        )
        resp = client.get("/api/v1/monitoring/alerts")
        item = resp.json()["items"][0]
        expected_keys = {
            "alert_id",
            "event_id",
            "event_type",
            "severity",
            "entity_type",
            "entity_id",
            "exam_id",
            "hall_id",
            "student_id",
            "message",
            "created_at",
        }
        assert expected_keys == set(item.keys())

    def test_status_fields(self, client):
        resp = client.get("/api/v1/monitoring/status")
        data = resp.json()
        expected_keys = {
            "active_connections",
            "buffered_events",
            "buffered_alerts",
            "total_published",
            "event_buffer_capacity",
            "alert_buffer_capacity",
            "max_connections",
        }
        assert expected_keys == set(data.keys())

    def test_connection_fields(self, client):
        resp = client.get("/api/v1/monitoring/connections")
        data = resp.json()
        expected_keys = {"active_connections", "max_connections"}
        assert expected_keys == set(data.keys())

    def test_nullable_optional_ids(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        resp = client.get("/api/v1/monitoring/events")
        item = resp.json()["items"][0]
        assert item["exam_id"] is None
        assert item["hall_id"] is None
        assert item["student_id"] is None
        assert item["entry_point_id"] is None


# ---------------------------------------------------------------------------
# Security / Privacy
# ---------------------------------------------------------------------------


class TestSecurityPrivacy:
    def test_no_biometric_data_in_events(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        resp = client.get("/api/v1/monitoring/events")
        text = resp.text
        assert "biometric" not in text.lower()
        assert "face_image" not in text.lower()
        assert "embedding" not in text.lower()

    def test_no_credentials_in_events(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        resp = client.get("/api/v1/monitoring/events")
        text = resp.text
        assert "api_key" not in text.lower()
        assert "password" not in text.lower()
        assert "token" not in text.lower()

    def test_no_database_urls_in_events(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        resp = client.get("/api/v1/monitoring/events")
        text = resp.text
        assert "postgresql://" not in text
        assert "sqlite://" not in text

    def test_no_filesystem_paths_in_events(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        resp = client.get("/api/v1/monitoring/events")
        text = resp.text
        assert "D:\\" not in text
        assert "/home/" not in text
        assert "/var/" not in text

    def test_no_stack_traces_in_events(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        resp = client.get("/api/v1/monitoring/events")
        text = resp.text
        assert "stack_trace" not in text.lower()
        assert "traceback" not in text.lower()

    def test_no_biometric_data_in_alerts(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_ESCALATED))
        resp = client.get("/api/v1/monitoring/alerts")
        text = resp.text
        assert "biometric" not in text.lower()
        assert "face_image" not in text.lower()

    def test_no_filesystem_paths_in_alert_messages(self, client):
        publisher = get_monitoring_publisher()
        publisher.publish(_make_event(event_type=EventType.ENTRY_ESCALATED))
        resp = client.get("/api/v1/monitoring/alerts")
        data = resp.json()
        for alert in data["items"]:
            msg = alert["message"]
            assert "D:\\" not in msg
            assert "/home/" not in msg
            assert "/var/" not in msg

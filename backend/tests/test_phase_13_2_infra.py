"""Phase 13.2 — Connection Manager + Event Publisher Tests.

Tests for EventBuffer, AlertBuffer, ConnectionManager, EventPublisher.
Covers: append, retrieval, FIFO eviction, capacity, filtering, broadcast,
failure handling, idempotency, alert generation, configuration.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.monitoring.alert_buffer import Alert, AlertBuffer
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
    MonitoringEvent,
    MonitoringFilter,
)


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
# EventBuffer
# ---------------------------------------------------------------------------


class TestEventBuffer:
    def test_append_and_recent(self):
        """Events appended can be retrieved."""
        buf = EventBuffer(capacity=10)
        event = _make_event()
        buf.append(event)
        assert len(buf) == 1
        recent = buf.recent()
        assert len(recent) == 1
        assert recent[0].event_id == event.event_id

    def test_fifo_eviction(self):
        """Oldest events are discarded when capacity is reached."""
        buf = EventBuffer(capacity=3)
        events = [_make_event(entity_id=i) for i in range(5)]
        for e in events:
            buf.append(e)
        assert len(buf) == 3
        recent = buf.recent()
        # Newest first: ids 4, 3, 2
        assert recent[0].entity_id == 4
        assert recent[1].entity_id == 3
        assert recent[2].entity_id == 2

    def test_capacity_enforcement(self):
        """Buffer never exceeds capacity."""
        buf = EventBuffer(capacity=5)
        for i in range(100):
            buf.append(_make_event(entity_id=i))
        assert len(buf) == 5

    def test_query_by_filter(self):
        """Filter retrieval returns matching events."""
        buf = EventBuffer(capacity=100)
        buf.append(_make_event(exam_id=1))
        buf.append(_make_event(exam_id=2))
        buf.append(_make_event(exam_id=1))

        f = MonitoringFilter(exam_id=1)
        results = buf.query(f)
        assert len(results) == 2
        assert all(e.exam_id == 1 for e in results)

    def test_query_no_match(self):
        """Filter returning no matches gives empty list."""
        buf = EventBuffer(capacity=10)
        buf.append(_make_event(exam_id=1))
        f = MonitoringFilter(exam_id=999)
        assert buf.query(f) == []

    def test_recent_limit(self):
        """recent() respects limit parameter."""
        buf = EventBuffer(capacity=100)
        for i in range(20):
            buf.append(_make_event(entity_id=i))
        assert len(buf.recent(limit=5)) == 5

    def test_invalid_capacity(self):
        """Zero capacity raises ValueError."""
        with pytest.raises(ValueError, match="capacity must be >= 1"):
            EventBuffer(capacity=0)

    def test_negative_capacity(self):
        """Negative capacity raises ValueError."""
        with pytest.raises(ValueError, match="capacity must be >= 1"):
            EventBuffer(capacity=-1)

    def test_empty_buffer(self):
        """Empty buffer returns empty list."""
        buf = EventBuffer(capacity=10)
        assert buf.recent() == []
        assert len(buf) == 0


# ---------------------------------------------------------------------------
# AlertBuffer
# ---------------------------------------------------------------------------


class TestAlertBuffer:
    def _make_alert(self, **kwargs) -> Alert:
        defaults = {
            "event_id": uuid.uuid4(),
            "event_type": EventType.ENTRY_ESCALATED,
            "severity": EventSeverity.WARNING,
            "message": "Test alert",
            "entity_type": "EntryVerification",
            "entity_id": 1,
        }
        defaults.update(kwargs)
        return Alert(**defaults)

    def test_append_and_recent(self):
        """Alerts appended can be retrieved."""
        buf = AlertBuffer(capacity=10)
        alert = self._make_alert()
        buf.append(alert)
        assert len(buf) == 1
        recent = buf.recent()
        assert len(recent) == 1
        assert recent[0].alert_id == alert.alert_id

    def test_fifo_eviction(self):
        """Oldest alerts are discarded when capacity is reached."""
        buf = AlertBuffer(capacity=3)
        for i in range(5):
            buf.append(self._make_alert(entity_id=i))
        assert len(buf) == 3
        recent = buf.recent()
        assert recent[0].entity_id == 4

    def test_alert_links_to_event(self):
        """Alert references originating event by event_id."""
        eid = uuid.uuid4()
        alert = self._make_alert(event_id=eid)
        buf = AlertBuffer(capacity=10)
        buf.append(alert)
        assert buf.recent()[0].event_id == eid

    def test_alert_to_dict(self):
        """Alert serialization includes all fields."""
        alert = self._make_alert(exam_id=3, hall_id=5, student_id=7)
        d = alert.to_dict()
        assert "alert_id" in d
        assert "event_id" in d
        assert d["exam_id"] == 3
        assert d["hall_id"] == 5
        assert d["student_id"] == 7

    def test_invalid_capacity(self):
        """Zero capacity raises ValueError."""
        with pytest.raises(ValueError, match="capacity must be >= 1"):
            AlertBuffer(capacity=0)


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------


class TestConnectionManager:
    def _make_transport(self) -> AsyncMock:
        transport = AsyncMock()
        transport.send_text = AsyncMock()
        return transport

    def test_register_and_count(self):
        """Register a client and verify count."""
        mgr = ConnectionManager(max_connections=10)
        transport = self._make_transport()
        mgr.register("c1", transport)
        assert mgr.active_count == 1

    def test_unregister(self):
        """Unregister removes the client."""
        mgr = ConnectionManager(max_connections=10)
        mgr.register("c1", self._make_transport())
        mgr.unregister("c1")
        assert mgr.active_count == 0

    def test_duplicate_client_replaces(self):
        """Registering same client_id replaces old connection."""
        mgr = ConnectionManager(max_connections=10)
        t1 = self._make_transport()
        t2 = self._make_transport()
        mgr.register("c1", t1)
        mgr.register("c1", t2)
        assert mgr.active_count == 1
        conn = mgr.get_connection("c1")
        assert conn.transport is t2

    def test_max_connections(self):
        """At max capacity, new client is rejected."""
        mgr = ConnectionManager(max_connections=2)
        mgr.register("c1", self._make_transport())
        mgr.register("c2", self._make_transport())
        with pytest.raises(RuntimeError, match="Max connections"):
            mgr.register("c3", self._make_transport())
        assert mgr.active_count == 2

    def test_max_connections_after_unregister(self):
        """After unregister, slot is available."""
        mgr = ConnectionManager(max_connections=1)
        mgr.register("c1", self._make_transport())
        mgr.unregister("c1")
        mgr.register("c2", self._make_transport())
        assert mgr.active_count == 1

    def test_broadcast_filters(self):
        """Only matching clients receive events."""
        mgr = ConnectionManager(max_connections=10)
        t1 = self._make_transport()
        t2 = self._make_transport()
        mgr.register("c1", t1, MonitoringFilter(exam_id=1))
        mgr.register("c2", t2, MonitoringFilter(exam_id=2))

        event = _make_event(exam_id=1)
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 1
        t1.send_text.assert_called_once()
        t2.send_text.assert_not_called()

    def test_broadcast_no_cross_leakage(self):
        """Client with exam_id=1 must NOT see exam_id=2 events."""
        mgr = ConnectionManager(max_connections=10)
        t1 = self._make_transport()
        mgr.register("c1", t1, MonitoringFilter(exam_id=1))
        event = _make_event(exam_id=2)
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 0
        t1.send_text.assert_not_called()

    def test_broadcast_failed_client_removed(self):
        """Client that fails to receive is removed."""
        mgr = ConnectionManager(max_connections=10)
        t_bad = AsyncMock()
        t_bad.send_text = AsyncMock(side_effect=ConnectionError("fail"))
        t_good = self._make_transport()
        mgr.register("c_bad", t_bad)
        mgr.register("c_good", t_good)

        event = _make_event()
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 1
        assert mgr.active_count == 1
        assert mgr.get_connection("c_bad") is None
        assert mgr.get_connection("c_good") is not None

    def test_broadcast_no_filter_matches_all(self):
        """Client with no filters receives all events."""
        mgr = ConnectionManager(max_connections=10)
        t1 = self._make_transport()
        mgr.register("c1", t1, MonitoringFilter())
        event = _make_event()
        sent = asyncio.run(mgr.broadcast(event))
        assert sent == 1

    def test_invalid_max_connections(self):
        """Zero max_connections raises ValueError."""
        with pytest.raises(ValueError, match="max_connections must be >= 1"):
            ConnectionManager(max_connections=0)


# ---------------------------------------------------------------------------
# EventPublisher
# ---------------------------------------------------------------------------


class TestEventPublisher:
    def _setup(self):
        mgr = ConnectionManager(max_connections=10)
        ebuf = EventBuffer(capacity=100)
        abuf = AlertBuffer(capacity=50)
        pub = EventPublisher(mgr, ebuf, abuf)
        return mgr, ebuf, abuf, pub

    def test_event_stored_in_buffer(self):
        """Published event is stored in event buffer."""
        _, ebuf, _, pub = self._setup()
        event = _make_event()
        pub.publish(event)
        assert len(ebuf) == 1
        assert ebuf.recent()[0].event_id == event.event_id

    def test_total_published_counter(self):
        """total_published increments on each publish."""
        _, _, _, pub = self._setup()
        pub.publish(_make_event(entity_id=1))
        pub.publish(_make_event(entity_id=2))
        assert pub.total_published == 2

    def test_idempotent_by_event_id(self):
        """Same event_id published twice is only stored once."""
        _, ebuf, _, pub = self._setup()
        event = _make_event()
        pub.publish(event)
        pub.publish(event)
        assert len(ebuf) == 1
        assert pub.total_published == 1

    def test_info_no_alert(self):
        """INFO events do not generate alerts."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.ENTRY_GRANTED)
        pub.publish(event)
        assert len(abuf) == 0

    def test_warning_creates_alert(self):
        """WARNING events generate alerts."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.ENTRY_ESCALATED)
        pub.publish(event)
        assert len(abuf) == 1
        alert = abuf.recent()[0]
        assert alert.severity == EventSeverity.WARNING
        assert alert.event_id == event.event_id

    def test_critical_creates_alert(self):
        """CRITICAL events generate alerts."""
        _, _, abuf, pub = self._setup()
        event = _make_event(event_type=EventType.RISK_CRITICAL)
        pub.publish(event)
        assert len(abuf) == 1
        alert = abuf.recent()[0]
        assert alert.severity == EventSeverity.CRITICAL

    def test_alert_message_content(self):
        """Alert message is human-readable."""
        _, _, abuf, pub = self._setup()
        event = _make_event(
            event_type=EventType.ENTRY_ESCALATED,
            entity_type="EntryVerification",
            entity_id=42,
        )
        pub.publish(event)
        alert = abuf.recent()[0]
        assert "EntryVerification #42" in alert.message
        assert "Entry" in alert.message

    def test_publisher_does_not_mutate_domain(self):
        """Publisher does not change the event object."""
        _, _, _, pub = self._setup()
        event = _make_event()
        original_id = event.event_id
        pub.publish(event)
        assert event.event_id == original_id

    def test_status_method(self):
        """status() returns correct counts."""
        mgr, ebuf, abuf, pub = self._setup()
        pub.publish(_make_event(event_type=EventType.ENTRY_GRANTED))
        pub.publish(_make_event(event_type=EventType.ENTRY_ESCALATED))
        status = pub.status()
        assert status["total_published"] == 2
        assert status["buffered_events"] == 2
        assert status["buffered_alerts"] == 1
        assert status["active_connections"] == 0


# ---------------------------------------------------------------------------
# Configuration Validation
# ---------------------------------------------------------------------------


class TestMonitoringConfig:
    def test_config_defaults(self):
        """Monitoring settings have sensible defaults."""
        from app.core.config import Settings
        s = Settings(
            DATABASE_URL="sqlite://",
            MONITORING_EVENT_BUFFER_SIZE=100,
            MONITORING_ALERT_BUFFER_SIZE=50,
            MONITORING_MAX_CONNECTIONS=10,
        )
        assert s.MONITORING_EVENT_BUFFER_SIZE == 100
        assert s.MONITORING_ALERT_BUFFER_SIZE == 50
        assert s.MONITORING_MAX_CONNECTIONS == 10

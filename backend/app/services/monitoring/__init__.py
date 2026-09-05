"""Real-time monitoring infrastructure (Phase 13.1–13.5).

Ephemeral event types, buffers, connection management, event publishing,
alert classification, and domain publication wiring.

No database persistence. No ORM dependency.
Existing domain audit/history tables remain authoritative.
"""

from app.services.monitoring.alert_buffer import Alert, AlertBuffer, AlertFilter
from app.services.monitoring.alerting import (
    alert_message,
    alert_payload,
    alert_worthy_event_types,
    should_alert,
)
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.events import (
    EventCategory,
    EventSeverity,
    EventType,
    MonitoringEvent,
    MonitoringFilter,
    severity_order,
)
from app.services.monitoring.publisher import (
    get_monitoring_publisher,
    init_monitoring_publisher,
    publish,
)

__all__ = [
    "Alert",
    "AlertBuffer",
    "AlertFilter",
    "ConnectionManager",
    "EventBuffer",
    "EventCategory",
    "EventPublisher",
    "EventSeverity",
    "EventType",
    "MonitoringEvent",
    "MonitoringFilter",
    "alert_message",
    "alert_payload",
    "alert_worthy_event_types",
    "get_monitoring_publisher",
    "init_monitoring_publisher",
    "publish",
    "severity_order",
    "should_alert",
]

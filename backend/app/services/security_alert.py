"""Security alert service.

Manages alert lifecycle: OPEN → ACKNOWLEDGED → RESOLVED/DISMISSED.
Alerts reference persistent SecurityEvent records.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.security_event import (
    SecurityAlert,
    SecurityAlertStatus,
    SecurityEvent,
    SecurityEventSeverity,
)

logger = logging.getLogger(__name__)


def create_security_alert(
    db: Session,
    *,
    security_event_id: int,
    severity: SecurityEventSeverity | str,
    message: str,
) -> SecurityAlert:
    """Create a new security alert from a security event."""
    event = db.query(SecurityEvent).filter(SecurityEvent.id == security_event_id).first()
    if event is None:
        raise LookupError(f"Security event {security_event_id} not found")

    alert = SecurityAlert(
        security_event_id=security_event_id,
        severity=severity.value if isinstance(severity, SecurityEventSeverity) else severity,
        message=message,
    )
    db.add(alert)
    db.commit()
    logger.info(
        "Security alert created: event_id=%d severity=%s",
        security_event_id,
        alert.severity,
    )
    return alert


def acknowledge_alert(
    db: Session,
    alert_id: int,
    *,
    assigned_to: str | None = None,
) -> SecurityAlert:
    """Acknowledge a security alert."""
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if alert is None:
        raise LookupError(f"Security alert {alert_id} not found")
    if alert.status != SecurityAlertStatus.OPEN.value:
        raise ValueError(
            f"Cannot acknowledge alert in {alert.status} status"
        )
    alert.status = SecurityAlertStatus.ACKNOWLEDGED.value
    alert.acknowledged_at = datetime.now(timezone.utc)
    if assigned_to:
        alert.assigned_to = assigned_to
    db.commit()
    logger.info("Security alert %d acknowledged", alert_id)
    return alert


def resolve_alert(
    db: Session,
    alert_id: int,
    *,
    resolution_notes: str | None = None,
    assigned_to: str | None = None,
) -> SecurityAlert:
    """Resolve a security alert."""
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if alert is None:
        raise LookupError(f"Security alert {alert_id} not found")
    if alert.status not in (
        SecurityAlertStatus.OPEN.value,
        SecurityAlertStatus.ACKNOWLEDGED.value,
    ):
        raise ValueError(
            f"Cannot resolve alert in {alert.status} status"
        )
    alert.status = SecurityAlertStatus.RESOLVED.value
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolution_notes = resolution_notes
    if assigned_to:
        alert.assigned_to = assigned_to
    db.commit()
    logger.info("Security alert %d resolved", alert_id)
    return alert


def dismiss_alert(
    db: Session,
    alert_id: int,
    *,
    reason: str,
    assigned_to: str | None = None,
) -> SecurityAlert:
    """Dismiss a security alert."""
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if alert is None:
        raise LookupError(f"Security alert {alert_id} not found")
    if alert.status not in (
        SecurityAlertStatus.OPEN.value,
        SecurityAlertStatus.ACKNOWLEDGED.value,
    ):
        raise ValueError(
            f"Cannot dismiss alert in {alert.status} status"
        )
    alert.status = SecurityAlertStatus.DISMISSED.value
    alert.resolution_notes = reason
    if assigned_to:
        alert.assigned_to = assigned_to
    db.commit()
    logger.info("Security alert %d dismissed", alert_id)
    return alert


def list_security_alerts(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    severity: str | None = None,
    security_event_id: int | None = None,
) -> dict:
    """List security alerts with filtering and pagination."""
    query = db.query(SecurityAlert)

    if status:
        query = query.filter(SecurityAlert.status == status)
    if severity:
        query = query.filter(SecurityAlert.severity == severity)
    if security_event_id is not None:
        query = query.filter(SecurityAlert.security_event_id == security_event_id)

    total = query.count()
    items = (
        query.order_by(SecurityAlert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_security_alert(db: Session, alert_id: int) -> SecurityAlert:
    """Get a security alert by ID."""
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if alert is None:
        raise LookupError(f"Security alert {alert_id} not found")
    return alert


def count_security_alerts(db: Session) -> dict[str, int]:
    """Count security alerts grouped by status."""
    from sqlalchemy import func

    rows = (
        db.query(SecurityAlert.status, func.count(SecurityAlert.id))
        .group_by(SecurityAlert.status)
        .all()
    )
    return {row[0]: row[1] for row in rows}

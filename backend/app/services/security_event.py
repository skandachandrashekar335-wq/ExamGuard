"""Security event service.

Creates persistent, immutable security event records.
Events are append-only — no updates, no deletes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.security_event import (
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventType,
)

logger = logging.getLogger(__name__)


def create_security_event(
    db: Session,
    *,
    event_type: SecurityEventType | str,
    severity: SecurityEventSeverity | str,
    entity_type: str,
    entity_id: int,
    source: str,
    description: str | None = None,
    metadata: dict | None = None,
    entry_verification_id: int | None = None,
    student_id: int | None = None,
    exam_id: int | None = None,
    hall_id: int | None = None,
    entry_point_id: int | None = None,
) -> SecurityEvent:
    """Create an immutable security event record."""
    event = SecurityEvent(
        event_type=event_type.value if isinstance(event_type, SecurityEventType) else event_type,
        severity=severity.value if isinstance(severity, SecurityEventSeverity) else severity,
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
        description=description,
        metadata_json=json.dumps(metadata) if metadata else None,
        entry_verification_id=entry_verification_id,
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        entry_point_id=entry_point_id,
    )
    db.add(event)
    db.commit()
    logger.info(
        "Security event created: type=%s severity=%s entity=%s#%s source=%s",
        event.event_type,
        event.severity,
        event.entity_type,
        event.entity_id,
        event.source,
    )
    return event


def list_security_events(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    event_type: str | None = None,
    severity: str | None = None,
    entity_type: str | None = None,
    student_id: int | None = None,
    exam_id: int | None = None,
    hall_id: int | None = None,
    entry_verification_id: int | None = None,
    source: str | None = None,
) -> dict:
    """List security events with filtering and pagination."""
    query = db.query(SecurityEvent)

    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    if entity_type:
        query = query.filter(SecurityEvent.entity_type == entity_type)
    if student_id is not None:
        query = query.filter(SecurityEvent.student_id == student_id)
    if exam_id is not None:
        query = query.filter(SecurityEvent.exam_id == exam_id)
    if hall_id is not None:
        query = query.filter(SecurityEvent.hall_id == hall_id)
    if entry_verification_id is not None:
        query = query.filter(SecurityEvent.entry_verification_id == entry_verification_id)
    if source:
        query = query.filter(SecurityEvent.source == source)

    total = query.count()
    items = (
        query.order_by(SecurityEvent.created_at.desc())
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


def get_security_event(db: Session, event_id: int) -> SecurityEvent:
    """Get a security event by ID."""
    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
    if event is None:
        raise LookupError(f"Security event {event_id} not found")
    return event


def count_security_events(db: Session) -> int:
    """Count total security events."""
    return db.query(func.count(SecurityEvent.id)).scalar() or 0


def count_security_events_by_severity(db: Session) -> dict[str, int]:
    """Count security events grouped by severity."""
    rows = (
        db.query(SecurityEvent.severity, func.count(SecurityEvent.id))
        .group_by(SecurityEvent.severity)
        .all()
    )
    return {row[0]: row[1] for row in rows}

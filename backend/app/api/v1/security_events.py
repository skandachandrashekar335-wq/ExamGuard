"""Security Events REST API.

Provides read-only access to persistent security event records.
Events are immutable — no create/update/delete through this API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.security_event import (
    SecurityEventListResponse,
    SecurityEventResponse,
)
from app.services import security_event as svc

router = APIRouter(
    prefix="/security-events",
    tags=["Security Events"],
)


@router.get(
    "",
    response_model=SecurityEventListResponse,
    summary="List security events",
)
def list_security_events(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    event_type: str | None = Query(None, description="Filter by event type"),
    severity: str | None = Query(None, description="Filter by severity"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    student_id: int | None = Query(None, description="Filter by student ID"),
    exam_id: int | None = Query(None, description="Filter by exam ID"),
    hall_id: int | None = Query(None, description="Filter by hall ID"),
    entry_verification_id: int | None = Query(
        None, description="Filter by entry verification ID"
    ),
    source: str | None = Query(None, description="Filter by source"),
    db: Session = Depends(get_db),
) -> SecurityEventListResponse:
    result = svc.list_security_events(
        db,
        page=page,
        page_size=page_size,
        event_type=event_type,
        severity=severity,
        entity_type=entity_type,
        student_id=student_id,
        exam_id=exam_id,
        hall_id=hall_id,
        entry_verification_id=entry_verification_id,
        source=source,
    )
    return SecurityEventListResponse(**result)


@router.get(
    "/{event_id}",
    response_model=SecurityEventResponse,
    summary="Get a security event",
)
def get_security_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> SecurityEventResponse:
    try:
        event = svc.get_security_event(db, event_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return event

"""Security Alerts REST API.

Manages alert lifecycle: acknowledge, resolve, dismiss.
Alerts reference persistent SecurityEvent records.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.security_event import (
    AcknowledgeAlertRequest,
    DismissAlertRequest,
    ResolveAlertRequest,
    SecurityAlertListResponse,
    SecurityAlertResponse,
)
from app.services import security_alert as svc

router = APIRouter(
    prefix="/security-alerts",
    tags=["Security Alerts"],
)


@router.get(
    "",
    response_model=SecurityAlertListResponse,
    summary="List security alerts",
)
def list_security_alerts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    security_event_id: int | None = Query(
        None, description="Filter by security event ID"
    ),
    db: Session = Depends(get_db),
) -> SecurityAlertListResponse:
    result = svc.list_security_alerts(
        db,
        page=page,
        page_size=page_size,
        status=status,
        severity=severity,
        security_event_id=security_event_id,
    )
    return SecurityAlertListResponse(**result)


@router.get(
    "/{alert_id}",
    response_model=SecurityAlertResponse,
    summary="Get a security alert",
)
def get_security_alert(
    alert_id: int,
    db: Session = Depends(get_db),
) -> SecurityAlertResponse:
    try:
        alert = svc.get_security_alert(db, alert_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return alert


@router.post(
    "/{alert_id}/acknowledge",
    response_model=SecurityAlertResponse,
    summary="Acknowledge a security alert",
)
def acknowledge_alert(
    alert_id: int,
    body: AcknowledgeAlertRequest,
    db: Session = Depends(get_db),
) -> SecurityAlertResponse:
    try:
        alert = svc.acknowledge_alert(
            db, alert_id, assigned_to=body.assigned_to
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return alert


@router.post(
    "/{alert_id}/resolve",
    response_model=SecurityAlertResponse,
    summary="Resolve a security alert",
)
def resolve_alert(
    alert_id: int,
    body: ResolveAlertRequest,
    db: Session = Depends(get_db),
) -> SecurityAlertResponse:
    try:
        alert = svc.resolve_alert(
            db,
            alert_id,
            resolution_notes=body.resolution_notes,
            assigned_to=body.assigned_to,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return alert


@router.post(
    "/{alert_id}/dismiss",
    response_model=SecurityAlertResponse,
    summary="Dismiss a security alert",
)
def dismiss_alert(
    alert_id: int,
    body: DismissAlertRequest,
    db: Session = Depends(get_db),
) -> SecurityAlertResponse:
    try:
        alert = svc.dismiss_alert(
            db,
            alert_id,
            reason=body.reason,
            assigned_to=body.assigned_to,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return alert

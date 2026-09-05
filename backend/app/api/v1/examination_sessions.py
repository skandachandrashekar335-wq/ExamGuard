"""Examination Session REST API (Phase 15).

Endpoints for managing examination session lifecycle, gate operations,
and session summaries.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.examination_session import (
    EndSessionRequest,
    ExaminationSessionCreate,
    ExaminationSessionListResponse,
    ExaminationSessionResponse,
    ExaminationSessionSummary,
    GateEventListResponse,
    GateEventResponse,
    GateOperationRequest,
    StartSessionRequest,
)
from app.services import examination_session as svc

router = APIRouter(
    prefix="/examination-sessions",
    tags=["Examination Sessions"],
)


@router.get(
    "",
    response_model=ExaminationSessionListResponse,
    summary="List examination sessions",
)
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exam_id: int | None = Query(None),
    exam_hall_id: int | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ExaminationSessionListResponse:
    result = svc.list_examination_sessions(
        db,
        page=page,
        page_size=page_size,
        exam_id=exam_id,
        exam_hall_id=exam_hall_id,
        status=status,
    )
    return ExaminationSessionListResponse(**result)


@router.get(
    "/summary",
    response_model=ExaminationSessionSummary,
    summary="Get session summary",
)
def get_summary(db: Session = Depends(get_db)) -> ExaminationSessionSummary:
    return ExaminationSessionSummary(**svc.get_session_summary(db))


@router.get(
    "/{session_id}",
    response_model=ExaminationSessionResponse,
    summary="Get an examination session",
)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
) -> ExaminationSessionResponse:
    try:
        return svc.get_examination_session(db, session_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "",
    response_model=ExaminationSessionResponse,
    status_code=201,
    summary="Create an examination session",
)
def create_session(
    body: ExaminationSessionCreate,
    db: Session = Depends(get_db),
) -> ExaminationSessionResponse:
    return svc.create_examination_session(
        db,
        exam_id=body.exam_id,
        exam_hall_id=body.exam_hall_id,
        expected_capacity=body.expected_capacity,
        notes=body.notes,
        created_by=body.created_by,
    )


@router.post(
    "/{session_id}/start",
    response_model=ExaminationSessionResponse,
    summary="Start an examination session",
)
def start_session(
    session_id: int,
    body: StartSessionRequest,
    db: Session = Depends(get_db),
) -> ExaminationSessionResponse:
    try:
        return svc.start_session(db, session_id, performed_by=body.performed_by)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{session_id}/end",
    response_model=ExaminationSessionResponse,
    summary="End an examination session",
)
def end_session(
    session_id: int,
    body: EndSessionRequest,
    db: Session = Depends(get_db),
) -> ExaminationSessionResponse:
    try:
        return svc.end_session(db, session_id, performed_by=body.performed_by)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{session_id}/cancel",
    response_model=ExaminationSessionResponse,
    summary="Cancel an examination session",
)
def cancel_session(
    session_id: int,
    body: GateOperationRequest,
    db: Session = Depends(get_db),
) -> ExaminationSessionResponse:
    try:
        return svc.cancel_session(
            db, session_id,
            reason=body.reason,
            performed_by=body.performed_by,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{session_id}/close-gates",
    response_model=ExaminationSessionResponse,
    summary="Close gates for a session",
)
def close_gates(
    session_id: int,
    body: GateOperationRequest,
    db: Session = Depends(get_db),
) -> ExaminationSessionResponse:
    try:
        return svc.close_gates(
            db, session_id,
            reason=body.reason,
            performed_by=body.performed_by,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{session_id}/open-gates",
    response_model=ExaminationSessionResponse,
    summary="Open gates for a session",
)
def open_gates(
    session_id: int,
    body: GateOperationRequest,
    db: Session = Depends(get_db),
) -> ExaminationSessionResponse:
    try:
        return svc.open_gates(
            db, session_id,
            reason=body.reason,
            performed_by=body.performed_by,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/{session_id}/gate-events",
    response_model=GateEventListResponse,
    summary="List gate events for a session",
)
def list_gate_events(
    session_id: int,
    db: Session = Depends(get_db),
) -> GateEventListResponse:
    try:
        return GateEventListResponse(**svc.list_gate_events(db, session_id))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

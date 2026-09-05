"""Attendance REST API (Phase 12.3).

Thin API layer exposing attendance recording, listing, summary, and
manual correction through existing service functions. No business logic
in routers — only input validation, service calls, and error mapping.

Does NOT independently authorize entry — EntryVerification remains
the single source of authorization.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.attendance import (
    AttendanceCorrectionRequest,
    AttendanceEventListResponse,
    AttendanceEventResponse,
    AttendanceListResponse,
    AttendanceRecordResponse,
    AttendanceSummaryResponse,
)
from app.services.attendance import service as att_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ---------------------------------------------------------------------------
# 1. Record attendance from EntryVerification
# ---------------------------------------------------------------------------


@router.post(
    "/record/{entry_verification_id}",
    response_model=AttendanceRecordResponse | None,
    status_code=200,
    summary="Record attendance from a resolved entry verification",
)
def record_attendance(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    """Record attendance from a resolved EntryVerification.

    GRANTED: returns AttendanceRecord.
    DENIED: returns None (event recorded, no record created).
    Repeated same EV: idempotent — no duplicate events.

    Does NOT authorize entry. EntryVerification is the sole source
    of authorization.
    """
    try:
        result = att_service.record_attendance(db, entry_verification_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


# ---------------------------------------------------------------------------
# 2. List exam attendance
# ---------------------------------------------------------------------------


@router.get(
    "/exams/{exam_id}",
    response_model=AttendanceListResponse,
    summary="List attendance records for an exam",
)
def list_exam_attendance(
    exam_id: int,
    hall_id: int | None = Query(None, description="Filter by exam hall ID"),
    status: str | None = Query(None, description="Filter by attendance status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List attendance records for an exam with optional filters."""
    result = att_service.list_attendance(
        db,
        exam_id,
        hall_id=hall_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return AttendanceListResponse(
        items=[
            AttendanceRecordResponse.model_validate(item)
            for item in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


# ---------------------------------------------------------------------------
# 3. Exam attendance summary
# ---------------------------------------------------------------------------


@router.get(
    "/exams/{exam_id}/summary",
    response_model=AttendanceSummaryResponse,
    summary="Get attendance summary for an exam",
)
def get_exam_summary(
    exam_id: int,
    db: Session = Depends(get_db),
):
    """Get attendance summary with by-hall breakdown."""
    try:
        result = att_service.get_exam_summary(db, exam_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return AttendanceSummaryResponse(
        exam_id=result["exam_id"],
        total_registered=result["total_registered"],
        total_present=result["total_present"],
        total_absent=result["total_absent"],
        total_excused=result["total_excused"],
        attendance_rate=result["attendance_rate"],
        by_hall=result["by_hall"],
    )


# ---------------------------------------------------------------------------
# 4. Registration attendance
# ---------------------------------------------------------------------------


@router.get(
    "/registrations/{exam_registration_id}",
    response_model=AttendanceRecordResponse,
    summary="Get attendance record for a registration",
)
def get_registration_attendance(
    exam_registration_id: int,
    db: Session = Depends(get_db),
):
    """Return the current AttendanceRecord for a registration.

    Returns 404 if no attendance record exists.
    """
    record = att_service.get_attendance_by_registration(db, exam_registration_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No attendance record found for registration {exam_registration_id}",
        )
    return record


# ---------------------------------------------------------------------------
# 5. Manual attendance correction
# ---------------------------------------------------------------------------


@router.post(
    "/registrations/{exam_registration_id}/correct",
    response_model=AttendanceRecordResponse,
    status_code=200,
    summary="Manually correct attendance for a registration",
)
def correct_attendance(
    exam_registration_id: int,
    body: AttendanceCorrectionRequest,
    db: Session = Depends(get_db),
):
    """Manually set attendance for a registration.

    Allowed statuses: PRESENT, EXCUSED.
    Server remains authoritative — does not fabricate EntryVerification.
    """
    try:
        return att_service.mark_manual_attendance(
            db,
            exam_registration_id,
            status=body.status,
            reason=body.reason,
            recorded_by=body.recorded_by,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ---------------------------------------------------------------------------
# 6. Student attendance history
# ---------------------------------------------------------------------------


@router.get(
    "/students/{student_id}",
    response_model=AttendanceListResponse,
    summary="List attendance history for a student",
)
def list_student_attendance(
    student_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List attendance records for a student across exams."""
    try:
        result = att_service.list_student_attendance_history(
            db,
            student_id,
            page=page,
            page_size=page_size,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return AttendanceListResponse(
        items=[
            AttendanceRecordResponse.model_validate(item)
            for item in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


# ---------------------------------------------------------------------------
# 7. Entry event history
# ---------------------------------------------------------------------------


@router.get(
    "/events/{entry_verification_id}",
    response_model=AttendanceEventListResponse,
    summary="List attendance events for an entry verification",
)
def list_entry_events(
    entry_verification_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List attendance events for an entry verification with pagination."""
    result = att_service.get_entry_events(
        db,
        entry_verification_id,
        page=page,
        page_size=page_size,
    )
    return AttendanceEventListResponse(
        items=[
            AttendanceEventResponse.model_validate(item)
            for item in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )

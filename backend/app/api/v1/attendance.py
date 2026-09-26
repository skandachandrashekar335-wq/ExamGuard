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

from app.auth import Role, require_role, get_invigilator_scope, check_invigilator_scope
from app.core.database import get_db
from app.schemas.attendance import (
    AttendanceCorrectionRequest,
    AttendanceEventListResponse,
    AttendanceEventResponse,
    AttendanceListResponse,
    AttendanceRecordResponse,
    AttendanceSummaryResponse,
    ManualReviewRequest,
    ManualReviewResponse,
    ManualReviewStatusResponse,
)
from app.services.attendance import service as att_service
from app.services.monitoring.publisher import (
    publish_attendance_corrected,
    publish_attendance_recorded,
)

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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR])),
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
    # Publish monitoring event after successful commit
    if result is not None:
        publish_attendance_recorded(
            attendance_record_id=result.id,
            entry_verification_id=entry_verification_id,
            student_id=result.student_id,
            exam_id=result.exam_id,
            hall_id=result.hall_id,
        )
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """List attendance records for an exam with optional filters."""
    scope = get_invigilator_scope(_user, db)
    if scope:
        check_invigilator_scope(scope, exam_id)
        hall_id = scope.hall_id
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR])),
):
    """Get attendance summary with by-hall breakdown."""
    scope = get_invigilator_scope(_user, db)
    if scope:
        check_invigilator_scope(scope, exam_id)
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.REVIEWER])),
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Manually set attendance for a registration.

    Allowed statuses: PRESENT, EXCUSED.
    Server remains authoritative — does not fabricate EntryVerification.
    """
    try:
        result = att_service.mark_manual_attendance(
            db,
            exam_registration_id,
            status=body.status,
            reason=body.reason,
            recorded_by=body.recorded_by,
        )
        publish_attendance_corrected(
            attendance_record_id=result.id,
            exam_registration_id=exam_registration_id,
            student_id=result.student_id,
            exam_id=result.exam_id,
            hall_id=result.hall_id,
            reason=body.reason,
            recorded_by=body.recorded_by,
        )
        return result
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.REVIEWER])),
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """List attendance events for an entry verification with pagination."""
    scope = get_invigilator_scope(_user, db)
    if scope:
        from app.services import entry_verification as ev_svc
        ev = ev_svc.get_entry_verification(db, entry_verification_id)
        if ev:
            check_invigilator_scope(scope, ev.exam_id, ev.exam_hall_id)
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


# ---------------------------------------------------------------------------
# 8. Manual review of INCONCLUSIVE identity attempts
# ---------------------------------------------------------------------------


@router.get(
    "/manual-review/{exam_registration_id}",
    response_model=ManualReviewStatusResponse,
    summary="Manual review status for a registration",
)
def get_manual_review_status(
    exam_registration_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.INVIGILATOR])),
):
    """Current manual review state for a registration.

    Returns the derived review state (NOT_REVIEWED / CHECKED_IN /
    CHECKED_OUT), the latest identity verification attempt, the session
    status, and the full attendance event history for the registration.
    """
    scope = get_invigilator_scope(_user, db)
    if scope is None:
        raise HTTPException(
            status_code=403, detail="Invigilator assignment not found"
        )
    try:
        reg = att_service.get_registration(db, exam_registration_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    check_invigilator_scope(scope, reg.exam_id)

    try:
        status = att_service.get_manual_review_status(
            db, exam_registration_id, hall_id=scope.hall_id
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ManualReviewStatusResponse(
        exam_registration_id=status["exam_registration_id"],
        review_state=status["review_state"],
        latest_attempt_id=status["latest_attempt_id"],
        latest_attempt_decision=status["latest_attempt_decision"],
        session_status=status["session_status"],
        events=[
            AttendanceEventResponse.model_validate(ev)
            for ev in status["events"]
        ],
    )


@router.post(
    "/manual-review",
    response_model=ManualReviewResponse,
    status_code=200,
    summary="Record a manual review decision for an inconclusive identity attempt",
)
def submit_manual_review(
    body: ManualReviewRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.INVIGILATOR])),
):
    """Record an invigilator manual review decision (CHECK_IN / CHECK_OUT).

    Only INVIGILATOR may act, and only within their assigned exam/hall
    scope. The server enforces that the latest identity verification
    attempt is INCONCLUSIVE, that an exam session is in progress, and that
    the review state machine permits the action. A reason is required and
    recorded for audit. This endpoint never fabricates an
    EntryVerification.

    Admins should use POST /attendance/registrations/{id}/correct for
    post-hoc attendance correction.
    """
    scope = get_invigilator_scope(_user, db)
    if scope is None:
        raise HTTPException(
            status_code=403, detail="Invigilator assignment not found"
        )
    try:
        reg = att_service.get_registration(db, body.exam_registration_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    check_invigilator_scope(scope, reg.exam_id)

    recorded_by = _user.get("email") or _user.get("sub") or "unknown"
    try:
        event, record = att_service.record_manual_review(
            db,
            body.exam_registration_id,
            action=body.action,
            reason=body.reason,
            recorded_by=recorded_by,
            hall_id=scope.hall_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except att_service.ManualReviewConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Notify monitoring when an attendance record exists. Event-only
    # check-outs have no record — nothing to publish for them.
    if record is not None:
        publish_attendance_corrected(
            attendance_record_id=record.id,
            exam_registration_id=body.exam_registration_id,
            student_id=record.student_id,
            exam_id=record.exam_id,
            hall_id=record.hall_id,
            reason=body.reason,
            recorded_by=recorded_by,
        )
    return ManualReviewResponse(
        exam_registration_id=body.exam_registration_id,
        review_state=att_service.get_review_state(
            db, body.exam_registration_id
        ),
        event=AttendanceEventResponse.model_validate(event),
        attendance_record_id=record.id if record is not None else None,
    )

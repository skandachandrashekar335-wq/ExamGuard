"""Attendance service layer.

Records attendance from resolved EntryVerification decisions.
Does NOT independently authorize entry — EntryVerification is the
single source of authorization.

Architecture:
    ENTRY_VERIFICATION (GRANTED/DENIED/ESCALATED)
        ↓
    ATTENDANCE SERVICE (this module)
        ↓
    ATTENDANCE RECORD (current state) + ATTENDANCE EVENT (history)
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attendance import (
    AttendanceEvent,
    AttendanceEventType,
    AttendanceRecord,
    AttendanceStatus,
    EntryMethod,
)
from app.models.entry_verification import (
    EntryVerification,
    EntryVerificationStatus,
)
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.examination_session import ExaminationSession, SessionStatus
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _get_entry_verification(db: Session, ev_id: int) -> EntryVerification:
    ev = db.query(EntryVerification).filter(EntryVerification.id == ev_id).first()
    if not ev:
        raise LookupError(f"Entry verification with id {ev_id} not found")
    return ev


def _get_registration(db: Session, reg_id: int) -> ExamRegistration:
    reg = db.query(ExamRegistration).filter(ExamRegistration.id == reg_id).first()
    if not reg:
        raise LookupError(f"Exam registration with id {reg_id} not found")
    return reg


def _get_exam(db: Session, exam_id: int) -> Exam:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise LookupError(f"Exam with id {exam_id} not found")
    return exam


def _get_student(db: Session, student_id: int) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise LookupError(f"Student with id {student_id} not found")
    return student


def _get_hall(db: Session, hall_id: int) -> ExamHall:
    hall = db.query(ExamHall).filter(ExamHall.id == hall_id).first()
    if not hall:
        raise LookupError(f"Exam hall with id {hall_id} not found")
    return hall


# ---------------------------------------------------------------------------
# 1. record_attendance
# ---------------------------------------------------------------------------


def record_attendance(
    db: Session,
    entry_verification_id: int,
) -> AttendanceRecord | None:
    """Record attendance from a resolved EntryVerification.

    GRANTED:
        Create/update AttendanceRecord → PRESENT.
        Create ENTRY_GRANTED AttendanceEvent.
        Snapshot hall_id and seat_number from entry context.

    DENIED:
        Create ENTRY_DENIED AttendanceEvent only.
        Return None (no AttendanceRecord for denied entries).

    ESCALATED (unresolved):
        Raise ValueError — cannot record attendance for unresolved escalation.

    PENDING / IN_PROGRESS:
        Raise ValueError — EV must be in a terminal state.

    Idempotent: processing the same EV twice returns the existing
    AttendanceRecord without creating duplicate events.

    Args:
        db: Database session.
        entry_verification_id: ID of the resolved entry verification.

    Returns:
        AttendanceRecord if GRANTED, None if DENIED.

    Raises:
        LookupError: If entry verification not found.
        ValueError: If EV status is not valid for attendance recording.
    """
    ev = _get_entry_verification(db, entry_verification_id)

    # Validate EV status
    if ev.status == EntryVerificationStatus.ESCALATED.value:
        raise ValueError(
            f"Cannot record attendance for entry verification {ev.id} "
            f"in ESCALATED status — must be resolved first"
        )
    if ev.status in (
        EntryVerificationStatus.PENDING.value,
        EntryVerificationStatus.IN_PROGRESS.value,
    ):
        raise ValueError(
            f"Cannot record attendance for entry verification {ev.id} "
            f"in {ev.status} status — must be in a terminal state"
        )

    # Check for existing event (idempotency)
    existing_event = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.entry_verification_id == ev.id,
            AttendanceEvent.event_type.in_([
                AttendanceEventType.ENTRY_GRANTED.value,
                AttendanceEventType.ENTRY_DENIED.value,
            ]),
        )
        .first()
    )
    if existing_event is not None:
        # Already processed — return existing record if GRANTED, None if DENIED
        if ev.status == EntryVerificationStatus.GRANTED.value:
            record = (
                db.query(AttendanceRecord)
                .filter(AttendanceRecord.exam_registration_id == ev.exam_registration_id)
                .first()
            )
            return record
        return None

    # DENIED: create event only, no record
    if ev.status == EntryVerificationStatus.DENIED.value:
        event = AttendanceEvent(
            student_id=ev.student_id,
            exam_id=ev.exam_registration.exam_id,
            exam_registration_id=ev.exam_registration_id,
            entry_verification_id=ev.id,
            event_type=AttendanceEventType.ENTRY_DENIED.value,
            status_snapshot="N/A",
            recorded_by="system",
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        logger.info(
            "ATTENDANCE_AUDIT: ev_id=%d event=ENTRY_DENIED student_id=%d",
            ev.id, ev.student_id,
        )
        return None

    # GRANTED: create/update record + event
    # Snapshot seat assignment
    seat_number = None
    seat = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_registration_id == ev.exam_registration_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .first()
    )
    if seat is not None:
        seat_number = seat.seat_number

    # Create event (idempotent via DB unique constraint)
    event = AttendanceEvent(
        student_id=ev.student_id,
        exam_id=ev.exam_registration.exam_id,
        exam_registration_id=ev.exam_registration_id,
        entry_verification_id=ev.id,
        event_type=AttendanceEventType.ENTRY_GRANTED.value,
        status_snapshot=AttendanceStatus.PRESENT.value,
        recorded_by="system",
    )
    db.add(event)

    # Upsert AttendanceRecord
    record = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.exam_registration_id == ev.exam_registration_id)
        .first()
    )

    if record is not None:
        # Re-entry: update existing record
        record.entry_verification_id = ev.id
        record.entry_time = ev.created_at
        record.hall_id = ev.exam_hall_id
        record.seat_number = seat_number
        record.status = AttendanceStatus.PRESENT.value
    else:
        # First entry: create new record
        record = AttendanceRecord(
            student_id=ev.student_id,
            exam_id=ev.exam_registration.exam_id,
            exam_registration_id=ev.exam_registration_id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=ev.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=ev.created_at,
            hall_id=ev.exam_hall_id,
            seat_number=seat_number,
        )
        db.add(record)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent duplicate — return existing state
        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == ev.exam_registration_id)
            .first()
        )
        return record

    db.refresh(record)

    logger.info(
        "ATTENDANCE_AUDIT: ev_id=%d event=ENTRY_GRANTED student_id=%d "
        "registration_id=%d status=PRESENT",
        ev.id, ev.student_id, ev.exam_registration_id,
    )
    return record


# ---------------------------------------------------------------------------
# 2. get_attendance
# ---------------------------------------------------------------------------


def get_attendance(
    db: Session,
    exam_id: int,
    student_id: int,
) -> AttendanceRecord | None:
    """Get current attendance for a student in an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.
        student_id: Student ID.

    Returns:
        AttendanceRecord if found, None otherwise.
    """
    return (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.student_id == student_id,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# 2b. get_attendance_by_registration
# ---------------------------------------------------------------------------


def get_attendance_by_registration(
    db: Session,
    exam_registration_id: int,
) -> AttendanceRecord | None:
    """Get current attendance record for an exam registration.

    Args:
        db: Database session.
        exam_registration_id: Registration ID.

    Returns:
        AttendanceRecord if found, None otherwise.
    """
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.exam_registration_id == exam_registration_id)
        .first()
    )


# ---------------------------------------------------------------------------
# 3. list_attendance
# ---------------------------------------------------------------------------


def list_attendance(
    db: Session,
    exam_id: int,
    *,
    hall_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List attendance records for an exam with optional filters.

    Args:
        db: Database session.
        exam_id: Exam ID (required).
        hall_id: Optional hall filter.
        status: Optional status filter.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size.
    """
    query = db.query(AttendanceRecord).filter(
        AttendanceRecord.exam_id == exam_id,
    )

    if hall_id is not None:
        query = query.filter(AttendanceRecord.hall_id == hall_id)
    if status is not None:
        query = query.filter(AttendanceRecord.status == status)

    total = query.count()
    items = (
        query.order_by(AttendanceRecord.id)
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


# ---------------------------------------------------------------------------
# 4. get_entry_events
# ---------------------------------------------------------------------------


def get_entry_events(
    db: Session,
    entry_verification_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Get attendance events for an entry verification.

    Args:
        db: Database session.
        entry_verification_id: Entry verification ID.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size.
    """
    query = db.query(AttendanceEvent).filter(
        AttendanceEvent.entry_verification_id == entry_verification_id,
    )

    total = query.count()
    items = (
        query.order_by(AttendanceEvent.id)
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


# ---------------------------------------------------------------------------
# 5. mark_manual_attendance
# ---------------------------------------------------------------------------

ALLOWED_MANUAL_STATUSES = {
    AttendanceStatus.PRESENT.value,
    AttendanceStatus.EXCUSED.value,
}


def mark_manual_attendance(
    db: Session,
    exam_registration_id: int,
    *,
    status: str,
    reason: str,
    recorded_by: str,
) -> AttendanceRecord:
    """Manually set attendance for a registration.

    Allowed statuses: PRESENT, EXCUSED.

    Creates/updates AttendanceRecord and creates ATTENDANCE_CORRECTED event.

    The AttendanceEvent requires an entry_verification_id FK. This function
    finds the most recent EntryVerification for the registration to satisfy
    the FK constraint. If no EV exists for the registration, raises ValueError.

    Args:
        db: Database session.
        exam_registration_id: Registration ID.
        status: New attendance status (PRESENT or EXCUSED).
        reason: Reason for the correction.
        recorded_by: Admin identifier.

    Returns:
        Updated AttendanceRecord.

    Raises:
        LookupError: If registration not found.
        ValueError: If status not allowed, registration cancelled, or no EV exists.
    """
    if status not in ALLOWED_MANUAL_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Allowed: {sorted(ALLOWED_MANUAL_STATUSES)}"
        )

    reg = _get_registration(db, exam_registration_id)

    if reg.status == RegistrationStatus.CANCELLED.value:
        raise ValueError(f"Registration {exam_registration_id} is cancelled")

    if not reason or not reason.strip():
        raise ValueError("Reason is required for manual attendance correction")

    if not recorded_by or not recorded_by.strip():
        raise ValueError("recorded_by is required for manual attendance correction")

    # Find the most recent EV for this registration (needed for FK)
    latest_ev = (
        db.query(EntryVerification)
        .filter(EntryVerification.exam_registration_id == exam_registration_id)
        .order_by(EntryVerification.id.desc())
        .first()
    )
    if latest_ev is None:
        raise ValueError(
            f"No entry verification found for registration {exam_registration_id} "
            f"— cannot create attendance event without an entry verification reference"
        )

    # Create attendance event — always create for audit trail
    event = AttendanceEvent(
        student_id=reg.student_id,
        exam_id=reg.exam_id,
        exam_registration_id=exam_registration_id,
        entry_verification_id=latest_ev.id,
        event_type=AttendanceEventType.ATTENDANCE_CORRECTED.value,
        status_snapshot=status,
        recorded_by=recorded_by.strip(),
        reason=reason.strip(),
    )
    db.add(event)

    # Upsert AttendanceRecord
    with db.no_autoflush:
        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == exam_registration_id)
            .first()
        )

    now = datetime.now(timezone.utc)

    if record is not None:
        record.status = status
        record.entry_method = EntryMethod.MANUAL_ENTRY.value
    else:
        record = AttendanceRecord(
            student_id=reg.student_id,
            exam_id=reg.exam_id,
            exam_registration_id=exam_registration_id,
            status=status,
            entry_verification_id=latest_ev.id,
            entry_method=EntryMethod.MANUAL_ENTRY.value,
            entry_time=now,
            hall_id=latest_ev.exam_hall_id,
            seat_number=None,
        )
        db.add(record)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Concurrent modification for registration {exam_registration_id}"
        )

    db.refresh(record)

    logger.info(
        "ATTENDANCE_AUDIT: registration_id=%d event=ATTENDANCE_CORRECTED "
        "status=%s recorded_by=%s reason=%s",
        exam_registration_id, status, recorded_by, reason,
    )
    return record


# ---------------------------------------------------------------------------
# 5b. Manual review of INCONCLUSIVE identity attempts
# ---------------------------------------------------------------------------


class ManualReviewConflict(ValueError):
    """Manual review precondition or state conflict.

    Subclass of ValueError so generic ValueError handlers remain a safe
    fallback; the API layer maps it to HTTP 409.
    """


MANUAL_REVIEW_ACTIONS = {"CHECK_IN", "CHECK_OUT"}
REVIEW_NOT_REVIEWED = "NOT_REVIEWED"
REVIEW_CHECKED_IN = "CHECKED_IN"
REVIEW_CHECKED_OUT = "CHECKED_OUT"


def get_registration(db: Session, exam_registration_id: int) -> ExamRegistration:
    """Public registration lookup (for API scope checks).

    Raises:
        LookupError: If registration not found.
    """
    return _get_registration(db, exam_registration_id)


def get_review_state(db: Session, exam_registration_id: int) -> str:
    """Derive manual review state from recorded manual review events.

    CHECKED_OUT if any MANUAL_CHECK_OUT event exists, else CHECKED_IN if any
    MANUAL_CHECK_IN event exists, else NOT_REVIEWED.
    """
    has_check_out = (
        db.query(AttendanceEvent.id)
        .filter(
            AttendanceEvent.exam_registration_id == exam_registration_id,
            AttendanceEvent.event_type
            == AttendanceEventType.MANUAL_CHECK_OUT.value,
        )
        .first()
        is not None
    )
    if has_check_out:
        return REVIEW_CHECKED_OUT

    has_check_in = (
        db.query(AttendanceEvent.id)
        .filter(
            AttendanceEvent.exam_registration_id == exam_registration_id,
            AttendanceEvent.event_type
            == AttendanceEventType.MANUAL_CHECK_IN.value,
        )
        .first()
        is not None
    )
    if has_check_in:
        return REVIEW_CHECKED_IN
    return REVIEW_NOT_REVIEWED


def _get_latest_attempt(
    db: Session, exam_registration_id: int
) -> IdentityVerificationAttempt | None:
    return (
        db.query(IdentityVerificationAttempt)
        .filter(
            IdentityVerificationAttempt.exam_registration_id
            == exam_registration_id
        )
        .order_by(IdentityVerificationAttempt.id.desc())
        .first()
    )


def _get_session(
    db: Session, exam_id: int, hall_id: int | None
) -> ExaminationSession | None:
    if hall_id is None:
        return None
    return (
        db.query(ExaminationSession)
        .filter(
            ExaminationSession.exam_id == exam_id,
            ExaminationSession.exam_hall_id == hall_id,
        )
        .order_by(ExaminationSession.created_at.desc())
        .first()
    )


def get_manual_review_status(
    db: Session,
    exam_registration_id: int,
    *,
    hall_id: int | None,
) -> dict:
    """Current manual review status for a registration (read-only).

    Returns dict with review_state, latest_attempt_id,
    latest_attempt_decision, session_status, and events (full audit trail
    for the registration, oldest first).

    Raises:
        LookupError: If registration not found.
    """
    reg = _get_registration(db, exam_registration_id)
    attempt = _get_latest_attempt(db, exam_registration_id)
    session = _get_session(db, reg.exam_id, hall_id)
    with db.no_autoflush:
        seat = (
            db.query(SeatAssignment)
            .filter(
                SeatAssignment.exam_registration_id == exam_registration_id,
                SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
            )
            .first()
        )
    events = (
        db.query(AttendanceEvent)
        .filter(AttendanceEvent.exam_registration_id == exam_registration_id)
        .order_by(AttendanceEvent.id)
        .all()
    )
    return {
        "exam_registration_id": exam_registration_id,
        "review_state": get_review_state(db, exam_registration_id),
        "latest_attempt_id": attempt.id if attempt else None,
        "latest_attempt_decision": attempt.decision if attempt else None,
        "session_status": session.status if session else None,
        "seat_number": seat.seat_number if seat else None,
        "events": events,
    }


def record_manual_review(
    db: Session,
    exam_registration_id: int,
    *,
    action: str,
    reason: str,
    recorded_by: str,
    hall_id: int | None,
) -> tuple[AttendanceEvent, AttendanceRecord | None]:
    """Record an auditable manual review decision for an INCONCLUSIVE
    identity verification attempt.

    This is the only attendance path that acts on an inconclusive face
    decision, and it requires an explicit invigilator action plus reason.
    It never fabricates an EntryVerification.

    Preconditions:
        - action must be CHECK_IN or CHECK_OUT (ValueError).
        - reason and recorded_by required (ValueError).
        - registration exists (LookupError) and is not cancelled (ValueError).
        - latest identity verification attempt exists and is INCONCLUSIVE
          (ManualReviewConflict).
        - an examination session exists for (registration exam, hall) and is
          IN_PROGRESS (ManualReviewConflict).

    State machine (events are the source of truth):
        - CHECK_IN: only from NOT_REVIEWED, and only when no attendance
          record exists yet (ManualReviewConflict otherwise — verified
          entries/admin corrections are handled via attendance correction).
        - CHECK_OUT: from NOT_REVIEWED (event only, snapshot N/A — no
          record is created or flipped) or from CHECKED_IN (record status
          becomes ABSENT). CHECKED_OUT is terminal (ManualReviewConflict).

    Effects:
        - CHECK_IN: creates MANUAL_CHECK_IN event (status PRESENT) and a
          PRESENT AttendanceRecord (MANUAL_ENTRY, entry_verification_id
          null, hall/seat/session snapshot).
        - CHECK_OUT from NOT_REVIEWED: creates MANUAL_CHECK_OUT event only.
        - CHECK_OUT from CHECKED_IN: creates MANUAL_CHECK_OUT event
          (snapshot ABSENT) and flips the record to ABSENT.

    Returns:
        (event, record) — record is None for event-only check-out.

    Raises:
        LookupError: If registration not found.
        ManualReviewConflict: On precondition/state conflicts (HTTP 409).
        ValueError: On validation errors (HTTP 422).
    """
    if action not in MANUAL_REVIEW_ACTIONS:
        raise ValueError(
            f"Invalid review action '{action}'. "
            f"Allowed: {sorted(MANUAL_REVIEW_ACTIONS)}"
        )
    if not reason or not reason.strip():
        raise ValueError("Reason is required for a manual review decision")
    if not recorded_by or not recorded_by.strip():
        raise ValueError("recorded_by is required for a manual review decision")

    reg = _get_registration(db, exam_registration_id)
    if reg.status == RegistrationStatus.CANCELLED.value:
        raise ValueError(f"Registration {exam_registration_id} is cancelled")

    attempt = _get_latest_attempt(db, exam_registration_id)
    if attempt is None:
        raise ManualReviewConflict(
            f"No identity verification attempt found for registration "
            f"{exam_registration_id} — manual review is only available after "
            f"an identity check has been run"
        )
    if attempt.decision != IdentityVerificationDecision.INCONCLUSIVE.value:
        if attempt.decision == IdentityVerificationDecision.NO_MATCH.value:
            # Hard security rule: an automated NO_MATCH must never be
            # manually allowed — not via UI, API, or any hidden path.
            # Only REVERIFY (a fresh attempt) is available for NO_MATCH.
            raise ManualReviewConflict(
                f"Latest identity verification decision is NO_MATCH — "
                f"manual review cannot allow a failed identity check; "
                f"only REVERIFY is available"
            )
        raise ManualReviewConflict(
            f"Latest identity verification decision is {attempt.decision}, "
            f"not INCONCLUSIVE — manual review does not apply"
        )

    session = _get_session(db, reg.exam_id, hall_id)
    if session is None:
        raise ManualReviewConflict(
            f"No examination session found for exam {reg.exam_id} in "
            f"hall {hall_id} — start the exam before recording a manual "
            f"review decision"
        )
    if session.status != SessionStatus.IN_PROGRESS.value:
        raise ManualReviewConflict(
            f"Examination session for exam {reg.exam_id} in hall "
            f"{hall_id} is {session.status}, not IN_PROGRESS — start the "
            f"exam before recording a manual review decision"
        )

    review_state = get_review_state(db, exam_registration_id)

    with db.no_autoflush:
        record = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.exam_registration_id == exam_registration_id
            )
            .first()
        )

    now = datetime.now(timezone.utc)
    reason_clean = reason.strip()
    recorded_by_clean = recorded_by.strip()

    if action == "CHECK_IN":
        if review_state != REVIEW_NOT_REVIEWED:
            raise ManualReviewConflict(
                f"Registration {exam_registration_id} is already "
                f"{review_state} — reload the review panel for current state"
            )
        if record is not None:
            raise ManualReviewConflict(
                f"Attendance already recorded for registration "
                f"{exam_registration_id} ({record.status} via "
                f"{record.entry_method}) — use attendance correction instead"
            )

        seat_number = None
        seat = (
            db.query(SeatAssignment)
            .filter(
                SeatAssignment.exam_registration_id == exam_registration_id,
                SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
            )
            .first()
        )
        if seat is not None:
            seat_number = seat.seat_number

        event = AttendanceEvent(
            student_id=reg.student_id,
            exam_id=reg.exam_id,
            exam_registration_id=exam_registration_id,
            entry_verification_id=None,
            event_type=AttendanceEventType.MANUAL_CHECK_IN.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
            recorded_by=recorded_by_clean,
            reason=reason_clean,
        )
        db.add(event)

        record = AttendanceRecord(
            student_id=reg.student_id,
            exam_id=reg.exam_id,
            exam_registration_id=exam_registration_id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=None,
            entry_method=EntryMethod.MANUAL_ENTRY.value,
            entry_time=now,
            hall_id=session.exam_hall_id,
            session_id=session.id,
            seat_number=seat_number,
        )
        db.add(record)
    else:  # CHECK_OUT
        if review_state == REVIEW_CHECKED_OUT:
            raise ManualReviewConflict(
                f"Registration {exam_registration_id} is already CHECKED_OUT"
            )
        if review_state == REVIEW_CHECKED_IN:
            if record is None:
                raise ManualReviewConflict(
                    f"Registration {exam_registration_id} has a check-in "
                    f"event but no attendance record — inconsistent state, "
                    f"use attendance correction"
                )
            record.status = AttendanceStatus.ABSENT.value
            snapshot = AttendanceStatus.ABSENT.value
        else:
            # NOT_REVIEWED: an existing record was created by verified entry
            # or admin correction — a manual check-out must not flip it to
            # ABSENT (never mark ABSENT from a face decision alone).
            if record is not None:
                raise ManualReviewConflict(
                    f"Attendance already recorded for registration "
                    f"{exam_registration_id} ({record.status} via "
                    f"{record.entry_method}) — use attendance correction "
                    f"instead"
                )
            snapshot = "N/A"

        event = AttendanceEvent(
            student_id=reg.student_id,
            exam_id=reg.exam_id,
            exam_registration_id=exam_registration_id,
            entry_verification_id=None,
            event_type=AttendanceEventType.MANUAL_CHECK_OUT.value,
            status_snapshot=snapshot,
            recorded_by=recorded_by_clean,
            reason=reason_clean,
        )
        db.add(event)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ManualReviewConflict(
            f"Concurrent manual review for registration "
            f"{exam_registration_id} — reload and retry"
        )

    db.refresh(event)
    if record is not None:
        db.refresh(record)

    logger.info(
        "ATTENDANCE_AUDIT: registration_id=%d event=%s review_state=%s "
        "attempt_id=%d recorded_by=%s reason=%s",
        exam_registration_id,
        event.event_type,
        get_review_state(db, exam_registration_id),
        attempt.id,
        recorded_by_clean,
        reason_clean,
    )
    return event, record


# ---------------------------------------------------------------------------
# 6. get_exam_summary
# ---------------------------------------------------------------------------


def get_exam_summary(db: Session, exam_id: int) -> dict:
    """Get attendance summary for an exam.

    Returns:
        Dict with total_registered, total_present, total_excused,
        total_absent (computed), attendance_rate, by_hall breakdown.

    Raises:
        LookupError: If exam not found.
    """
    _get_exam(db, exam_id)

    # Count registered students
    total_registered = (
        db.query(func.count(ExamRegistration.id))
        .filter(
            ExamRegistration.exam_id == exam_id,
            ExamRegistration.status == RegistrationStatus.REGISTERED.value,
        )
        .scalar()
    )

    # Count by attendance status
    total_present = (
        db.query(func.count(AttendanceRecord.id))
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT.value,
        )
        .scalar()
    )

    total_excused = (
        db.query(func.count(AttendanceRecord.id))
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.status == AttendanceStatus.EXCUSED.value,
        )
        .scalar()
    )

    total_absent = max(0, total_registered - total_present - total_excused)

    attendance_rate = (
        round((total_present + total_excused) / total_registered * 100, 1)
        if total_registered > 0
        else 0.0
    )

    # By-hall breakdown
    hall_rows = (
        db.query(
            AttendanceRecord.hall_id,
            func.count(AttendanceRecord.id).label("total"),
        )
        .filter(AttendanceRecord.exam_id == exam_id)
        .group_by(AttendanceRecord.hall_id)
        .all()
    )

    hall_present_rows = (
        db.query(
            AttendanceRecord.hall_id,
            func.count(AttendanceRecord.id).label("present"),
        )
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT.value,
        )
        .group_by(AttendanceRecord.hall_id)
        .all()
    )

    hall_present_map = {row.hall_id: row.present for row in hall_present_rows}

    by_hall = []
    for row in hall_rows:
        hall = db.query(ExamHall).filter(ExamHall.id == row.hall_id).first()
        by_hall.append({
            "hall_id": row.hall_id,
            "hall_name": f"{hall.building} {hall.room_number}" if hall else str(row.hall_id),
            "total": row.total,
            "present": hall_present_map.get(row.hall_id, 0),
        })

    return {
        "exam_id": exam_id,
        "total_registered": total_registered,
        "total_present": total_present,
        "total_absent": total_absent,
        "total_excused": total_excused,
        "attendance_rate": attendance_rate,
        "by_hall": by_hall,
    }


# ---------------------------------------------------------------------------
# 7. list_student_attendance_history
# ---------------------------------------------------------------------------


def list_student_attendance_history(
    db: Session,
    student_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List attendance records for a student across exams.

    Args:
        db: Database session.
        student_id: Student ID.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size.
    """
    _get_student(db, student_id)

    query = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student_id,
    )

    total = query.count()
    items = (
        query.order_by(AttendanceRecord.id.desc())
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

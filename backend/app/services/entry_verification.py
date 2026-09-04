"""Entry verification service.

Orchestrates a single examination entry verification attempt.
Coordinates existing domains: Student, ExamRegistration, HallTicket,
SeatAssignment, EntryPoint, Camera, IdentityVerificationAttempt.

The service produces evidence/check states and an entry authorization decision.
AI/perception = evidence. Business layer = authorization decision.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.camera import Camera, CameraStatus
from app.models.camera_entry_point import CameraEntryPointMapping
from app.models.entry_point import EntryPoint
from app.models.entry_verification import (
    ENTRY_VERIFICATION_STATUS_TRANSITIONS,
    EntryVerification,
    EntryVerificationStatus,
    HallTicketCheckStatus,
    IdentityCheckStatus,
    SeatCheckStatus,
)
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationStatus,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_status_transition(current: str, new: str) -> None:
    allowed = ENTRY_VERIFICATION_STATUS_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValueError(
            f"Cannot transition from '{current}' to '{new}'. "
            f"Allowed: {sorted(allowed) if allowed else 'none (terminal)'}"
        )


def _get_student(db: Session, student_id: int) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise LookupError(f"Student with id {student_id} not found")
    return student


def _get_registration(db: Session, reg_id: int) -> ExamRegistration:
    reg = db.query(ExamRegistration).filter(ExamRegistration.id == reg_id).first()
    if not reg:
        raise LookupError(f"Exam registration with id {reg_id} not found")
    return reg


def _get_entry_point(db: Session, ep_id: int) -> EntryPoint:
    ep = db.query(EntryPoint).filter(EntryPoint.id == ep_id).first()
    if not ep:
        raise LookupError(f"Entry point with id {ep_id} not found")
    return ep


def _get_exam_hall(db: Session, hall_id: int) -> ExamHall:
    hall = db.query(ExamHall).filter(ExamHall.id == hall_id).first()
    if not hall:
        raise LookupError(f"Exam hall with id {hall_id} not found")
    return hall


def _get_camera(db: Session, camera_id: int) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise LookupError(f"Camera with id {camera_id} not found")
    return camera


def _get_hall_ticket(db: Session, ht_id: int) -> HallTicket:
    ht = db.query(HallTicket).filter(HallTicket.id == ht_id).first()
    if not ht:
        raise LookupError(f"Hall ticket with id {ht_id} not found")
    return ht


def _get_entry_verification(db: Session, ev_id: int) -> EntryVerification:
    ev = db.query(EntryVerification).filter(EntryVerification.id == ev_id).first()
    if not ev:
        raise LookupError(f"Entry verification with id {ev_id} not found")
    return ev


# ---------------------------------------------------------------------------
# Create entry verification
# ---------------------------------------------------------------------------


def create_entry_verification(
    db: Session,
    student_id: int,
    exam_registration_id: int,
    entry_point_id: int,
    *,
    camera_id: int | None = None,
    hall_ticket_id: int | None = None,
) -> EntryVerification:
    """Create a new entry verification attempt.

    Validates core relationships: student, registration, entry point,
    exam hall compatibility, camera mapping, and optional hall ticket.

    Args:
        db: Database session.
        student_id: ID of the student attempting entry.
        exam_registration_id: ID of the student's exam registration.
        entry_point_id: ID of the physical entry point.
        camera_id: Optional camera observing the entry.
        hall_ticket_id: Optional hall ticket to link.

    Returns:
        Created EntryVerification in PENDING status.

    Raises:
        LookupError: If any required entity not found.
        ValueError: If relationships are inconsistent.
    """
    student = _get_student(db, student_id)
    reg = _get_registration(db, exam_registration_id)
    entry_point = _get_entry_point(db, entry_point_id)

    # Registration belongs to student
    if reg.student_id != student_id:
        raise ValueError(
            f"Registration {exam_registration_id} belongs to student "
            f"{reg.student_id}, not {student_id}"
        )

    # Registration is not cancelled
    if reg.status == RegistrationStatus.CANCELLED.value:
        raise ValueError(f"Registration {exam_registration_id} is cancelled")

    # Entry point is active
    if not entry_point.is_active:
        raise ValueError(f"Entry point {entry_point_id} is not active")

    # Entry point belongs to an exam hall
    if entry_point.exam_hall_id is None:
        raise ValueError(f"Entry point {entry_point_id} is not associated with an exam hall")

    # Exam hall exists
    exam_hall = _get_exam_hall(db, entry_point.exam_hall_id)

    # Registration's exam is compatible with the entry point's hall
    # The seat assignment links registration → exam_hall; we don't enforce
    # a direct exam→hall link here (seat check will validate hall assignment).

    # Camera validation
    if camera_id is not None:
        camera = _get_camera(db, camera_id)

        if not camera.is_active:
            raise ValueError(f"Camera {camera_id} is not active")

        # Camera must be mapped to the entry point
        mapping = (
            db.query(CameraEntryPointMapping)
            .filter(
                CameraEntryPointMapping.camera_id == camera_id,
                CameraEntryPointMapping.entry_point_id == entry_point_id,
                CameraEntryPointMapping.is_enabled == True,
            )
            .first()
        )
        if not mapping:
            raise ValueError(
                f"Camera {camera_id} is not mapped to entry point {entry_point_id}"
            )

    # Hall ticket validation
    if hall_ticket_id is not None:
        ht = _get_hall_ticket(db, hall_ticket_id)
        if ht.exam_registration_id != exam_registration_id:
            raise ValueError(
                f"Hall ticket {hall_ticket_id} belongs to registration "
                f"{ht.exam_registration_id}, not {exam_registration_id}"
            )

    ev = EntryVerification(
        student_id=student_id,
        exam_registration_id=exam_registration_id,
        exam_hall_id=exam_hall.id,
        entry_point_id=entry_point_id,
        camera_id=camera_id,
        hall_ticket_id=hall_ticket_id,
        status=EntryVerificationStatus.PENDING.value,
        hall_ticket_check=HallTicketCheckStatus.PENDING.value,
        identity_check=IdentityCheckStatus.PENDING.value,
        seat_check=SeatCheckStatus.PENDING.value,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    logger.info(
        "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=created "
        "student_id=%d entry_point_id=%d",
        ev.id, student_id, entry_point_id,
    )

    return ev


# ---------------------------------------------------------------------------
# Get / list
# ---------------------------------------------------------------------------


def get_entry_verification(db: Session, ev_id: int) -> EntryVerification | None:
    return db.query(EntryVerification).filter(EntryVerification.id == ev_id).first()


def list_entry_verifications(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
    entry_point_id: int | None = None,
    status: str | None = None,
) -> dict:
    query = db.query(EntryVerification)

    if student_id is not None:
        query = query.filter(EntryVerification.student_id == student_id)
    if entry_point_id is not None:
        query = query.filter(EntryVerification.entry_point_id == entry_point_id)
    if status is not None:
        query = query.filter(EntryVerification.status == status)

    total = query.count()
    items = (
        query.order_by(EntryVerification.created_at.desc())
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
# Begin processing
# ---------------------------------------------------------------------------


def begin_processing(db: Session, ev_id: int) -> EntryVerification:
    """Transition entry verification from PENDING to IN_PROGRESS."""
    ev = _get_entry_verification(db, ev_id)
    _validate_status_transition(ev.status, EntryVerificationStatus.IN_PROGRESS.value)
    ev.status = EntryVerificationStatus.IN_PROGRESS.value
    db.commit()
    db.refresh(ev)

    logger.info("ENTRY_VERIFICATION_AUDIT: ev_id=%d event=begin_processing", ev_id)
    return ev


# ---------------------------------------------------------------------------
# Hall ticket check
# ---------------------------------------------------------------------------


def process_hall_ticket_check(db: Session, ev_id: int) -> EntryVerification:
    """Verify the hall ticket associated with this entry verification.

    Checks: ticket exists, belongs to this registration, is in VERIFIED state.
    Updates hall_ticket_check to PASSED or FAILED.
    Does not re-run OCR or mutate hall ticket state.
    """
    ev = _get_entry_verification(db, ev_id)

    if ev.status not in (
        EntryVerificationStatus.PENDING.value,
        EntryVerificationStatus.IN_PROGRESS.value,
    ):
        raise ValueError(
            f"Cannot process hall ticket check on entry verification "
            f"in status '{ev.status}'"
        )

    # Auto-link hall ticket from registration if not already linked
    if ev.hall_ticket_id is None:
        ht = (
            db.query(HallTicket)
            .filter(HallTicket.exam_registration_id == ev.exam_registration_id)
            .first()
        )
        if ht is not None:
            ev.hall_ticket_id = ht.id

    # No hall ticket linked
    if ev.hall_ticket_id is None:
        ev.hall_ticket_check = HallTicketCheckStatus.FAILED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=hall_ticket_check "
            "result=FAILED reason=no_ticket",
            ev_id,
        )
        return ev

    # Verify the hall ticket
    ht = db.query(HallTicket).filter(HallTicket.id == ev.hall_ticket_id).first()
    if not ht:
        ev.hall_ticket_check = HallTicketCheckStatus.FAILED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=hall_ticket_check "
            "result=FAILED reason=ticket_not_found",
            ev_id,
        )
        return ev

    # Ticket must belong to the same registration
    if ht.exam_registration_id != ev.exam_registration_id:
        ev.hall_ticket_check = HallTicketCheckStatus.FAILED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=hall_ticket_check "
            "result=FAILED reason=ticket_wrong_registration",
            ev_id,
        )
        return ev

    # Ticket must be in VERIFIED state
    if ht.status != HallTicketStatus.VERIFIED.value:
        ev.hall_ticket_check = HallTicketCheckStatus.FAILED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=hall_ticket_check "
            "result=FAILED reason=ticket_not_verified status=%s",
            ev_id, ht.status,
        )
        return ev

    ev.hall_ticket_check = HallTicketCheckStatus.PASSED.value
    db.commit()
    db.refresh(ev)

    logger.info(
        "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=hall_ticket_check result=PASSED",
        ev_id,
    )
    return ev


# ---------------------------------------------------------------------------
# Seat check
# ---------------------------------------------------------------------------


def process_seat_check(db: Session, ev_id: int) -> EntryVerification:
    """Verify seat assignment for this entry verification.

    Checks: registration is valid, seat assignment exists, assignment
    belongs to this registration, assigned exam hall matches.
    Does not mutate seat assignments.
    """
    ev = _get_entry_verification(db, ev_id)

    if ev.status not in (
        EntryVerificationStatus.PENDING.value,
        EntryVerificationStatus.IN_PROGRESS.value,
    ):
        raise ValueError(
            f"Cannot process seat check on entry verification "
            f"in status '{ev.status}'"
        )

    # Find seat assignment for this registration
    seat = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_registration_id == ev.exam_registration_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .first()
    )

    if seat is None:
        ev.seat_check = SeatCheckStatus.FAILED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=seat_check "
            "result=FAILED reason=no_seat_assignment",
            ev_id,
        )
        return ev

    # Seat must be in the same exam hall as the entry verification
    if seat.exam_hall_id != ev.exam_hall_id:
        ev.seat_check = SeatCheckStatus.FAILED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=seat_check "
            "result=FAILED reason=wrong_hall expected=%d actual=%d",
            ev_id, ev.exam_hall_id, seat.exam_hall_id,
        )
        return ev

    ev.seat_check = SeatCheckStatus.PASSED.value
    db.commit()
    db.refresh(ev)

    logger.info(
        "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=seat_check result=PASSED",
        ev_id,
    )
    return ev


# ---------------------------------------------------------------------------
# Identity check
# ---------------------------------------------------------------------------


def process_identity_check(
    db: Session,
    ev_id: int,
    *,
    identity_attempt_id: int | None = None,
) -> EntryVerification:
    """Process identity verification for this entry verification.

    If identity_attempt_id is provided, links the existing identity
    verification attempt and evaluates its decision.

    If no identity attempt is available, evaluates camera availability
    to determine if identity check can proceed.

    The identity verification service is evidence-producing; this function
    converts its outcome into IdentityCheckStatus.
    """
    ev = _get_entry_verification(db, ev_id)

    if ev.status not in (
        EntryVerificationStatus.PENDING.value,
        EntryVerificationStatus.IN_PROGRESS.value,
    ):
        raise ValueError(
            f"Cannot process identity check on entry verification "
            f"in status '{ev.status}'"
        )

    # If identity attempt is provided, link and evaluate it
    if identity_attempt_id is not None:
        attempt = db.query(IdentityVerificationAttempt).filter(
            IdentityVerificationAttempt.id == identity_attempt_id
        ).first()
        if not attempt:
            raise LookupError(
                f"Identity verification attempt {identity_attempt_id} not found"
            )

        # Link the attempt
        ev.identity_verification_attempt_id = identity_attempt_id

        # Evaluate the attempt's decision
        if attempt.decision == IdentityVerificationDecision.MATCH.value:
            ev.identity_check = IdentityCheckStatus.PASSED.value
        elif attempt.decision in (
            IdentityVerificationDecision.NO_MATCH.value,
            IdentityVerificationDecision.INCONCLUSIVE.value,
        ):
            ev.identity_check = IdentityCheckStatus.FAILED.value
        else:
            # PENDING or unknown — still waiting
            ev.identity_check = IdentityCheckStatus.PENDING.value

        db.commit()
        db.refresh(ev)

        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=identity_check "
            "result=%s attempt_id=%d attempt_decision=%s",
            ev_id, ev.identity_check, identity_attempt_id, attempt.decision,
        )
        return ev

    # No identity attempt — check camera availability
    if ev.camera_id is None:
        ev.identity_check = IdentityCheckStatus.SKIPPED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=identity_check "
            "result=SKIPPED reason=no_camera",
            ev_id,
        )
        return ev

    # Check camera state
    camera = db.query(Camera).filter(Camera.id == ev.camera_id).first()
    if camera is None or not camera.is_active:
        ev.identity_check = IdentityCheckStatus.SKIPPED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=identity_check "
            "result=SKIPPED reason=camera_inactive",
            ev_id,
        )
        return ev

    if camera.status in (
        CameraStatus.OFFLINE.value,
        CameraStatus.DISABLED.value,
    ):
        ev.identity_check = IdentityCheckStatus.SKIPPED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=identity_check "
            "result=SKIPPED reason=camera_%s",
            ev_id, camera.status.lower(),
        )
        return ev

    if camera.status == CameraStatus.UNKNOWN.value:
        ev.identity_check = IdentityCheckStatus.PENDING.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=identity_check "
            "result=PENDING reason=camera_unknown",
            ev_id,
        )
        return ev

    # Camera is ONLINE but no identity attempt linked yet
    ev.identity_check = IdentityCheckStatus.PENDING.value
    db.commit()
    db.refresh(ev)
    logger.info(
        "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=identity_check "
        "result=PENDING reason=camera_online_no_attempt",
        ev_id,
    )
    return ev


# ---------------------------------------------------------------------------
# Evaluate entry
# ---------------------------------------------------------------------------


def evaluate_entry(db: Session, ev_id: int) -> EntryVerification:
    """Evaluate all checks and produce an entry authorization decision.

    Decision logic:
    - All checks PASSED → GRANTED
    - Any check FAILED → DENIED
    - Pending/inconclusive/unavailable → ESCALATED
    """
    ev = _get_entry_verification(db, ev_id)

    if ev.status not in (
        EntryVerificationStatus.PENDING.value,
        EntryVerificationStatus.IN_PROGRESS.value,
        EntryVerificationStatus.ESCALATED.value,
    ):
        raise ValueError(
            f"Cannot evaluate entry verification in status '{ev.status}'"
        )

    checks = [ev.hall_ticket_check, ev.identity_check, ev.seat_check]

    # All must be PASSED for GRANTED
    if all(c == HallTicketCheckStatus.PASSED.value for c in checks):
        ev.status = EntryVerificationStatus.GRANTED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=evaluate result=GRANTED",
            ev_id,
        )
        return ev

    # Any FAILED → DENIED
    if any(c in (HallTicketCheckStatus.FAILED.value, IdentityCheckStatus.FAILED.value, SeatCheckStatus.FAILED.value) for c in checks):
        ev.status = EntryVerificationStatus.DENIED.value
        db.commit()
        db.refresh(ev)
        logger.info(
            "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=evaluate result=DENIED "
            "ht=%s id=%s seat=%s",
            ev_id, ev.hall_ticket_check, ev.identity_check, ev.seat_check,
        )
        return ev

    # Otherwise → ESCALATED (pending, skipped, or mixed states)
    ev.status = EntryVerificationStatus.ESCALATED.value
    if ev.escalation_reason is None:
        ev.escalation_reason = _build_escalation_reason(ev)
    db.commit()
    db.refresh(ev)
    logger.info(
        "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=evaluate result=ESCALATED "
        "ht=%s id=%s seat=%s",
        ev_id, ev.hall_ticket_check, ev.identity_check, ev.seat_check,
    )
    return ev


def _build_escalation_reason(ev: EntryVerification) -> str:
    parts = []
    if ev.hall_ticket_check != HallTicketCheckStatus.PASSED.value:
        parts.append(f"hall_ticket={ev.hall_ticket_check}")
    if ev.identity_check not in (
        IdentityCheckStatus.PASSED.value,
        IdentityCheckStatus.SKIPPED.value,
    ):
        parts.append(f"identity={ev.identity_check}")
    if ev.seat_check != SeatCheckStatus.PASSED.value:
        parts.append(f"seat={ev.seat_check}")
    return "Automated evaluation inconclusive: " + ", ".join(parts) if parts else "Automated evaluation inconclusive"


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


def escalate_for_review(
    db: Session,
    ev_id: int,
    reason: str,
) -> EntryVerification:
    """Escalate entry verification for human review.

    Moves to ESCALATED status, stores escalation reason, preserves
    all existing check states.
    """
    ev = _get_entry_verification(db, ev_id)
    _validate_status_transition(ev.status, EntryVerificationStatus.ESCALATED.value)

    if not reason or not reason.strip():
        raise ValueError("Escalation reason is required")

    ev.status = EntryVerificationStatus.ESCALATED.value
    ev.escalation_reason = reason.strip()
    db.commit()
    db.refresh(ev)

    logger.info(
        "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=escalate reason=%s",
        ev_id, reason.strip(),
    )
    return ev


def resolve_escalation(
    db: Session,
    ev_id: int,
    *,
    granted: bool,
    reason: str | None = None,
) -> EntryVerification:
    """Resolve an escalated entry verification.

    Sets status to GRANTED or DENIED and records resolved_at timestamp.
    """
    ev = _get_entry_verification(db, ev_id)

    if ev.status != EntryVerificationStatus.ESCALATED.value:
        raise ValueError(
            f"Cannot resolve entry verification in status '{ev.status}'. "
            f"Must be ESCALATED."
        )

    new_status = (
        EntryVerificationStatus.GRANTED.value
        if granted
        else EntryVerificationStatus.DENIED.value
    )
    ev.status = new_status
    ev.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ev)

    logger.info(
        "ENTRY_VERIFICATION_AUDIT: ev_id=%d event=resolve result=%s reason=%s",
        ev_id, new_status, reason,
    )
    return ev

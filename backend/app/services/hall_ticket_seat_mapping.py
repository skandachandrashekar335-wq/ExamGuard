"""Hall ticket to seat mapping service.

Resolves the chain: HallTicket → ExamRegistration → Student + Exam + SeatAssignment.
Surfaces UNRESOLVED cases with reasons for auditing.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student

logger = logging.getLogger(__name__)


@dataclass
class SeatMappingResult:
    """Result of resolving a hall ticket to a seat assignment."""

    hall_ticket_id: int
    exam_registration_id: int
    student_id: int | None = None
    student_usn: str | None = None
    student_name: str | None = None
    exam_id: int | None = None
    seat_assignment_id: int | None = None
    seat_number: str | None = None
    exam_hall_id: int | None = None
    exam_hall_name: str | None = None
    status: str = "UNRESOLVED"
    reasons: list[str] = field(default_factory=list)


def resolve_hall_ticket_seat(db: Session, hall_ticket_id: int) -> SeatMappingResult:
    """Resolve seat assignment from a hall ticket.

    Follows: HallTicket → ExamRegistration → Student + Exam → SeatAssignment → ExamHall.

    Returns SeatMappingResult with status RESOLVED or UNRESOLVED and reasons.
    """
    ht = db.query(HallTicket).filter(HallTicket.id == hall_ticket_id).first()
    if not ht:
        return SeatMappingResult(
            hall_ticket_id=hall_ticket_id,
            exam_registration_id=0,
            status="UNRESOLVED",
            reasons=["hall_ticket_not_found"],
        )

    result = SeatMappingResult(
        hall_ticket_id=ht.id,
        exam_registration_id=ht.exam_registration_id,
    )

    # Get registration
    reg = db.query(ExamRegistration).filter(
        ExamRegistration.id == ht.exam_registration_id
    ).first()
    if not reg:
        result.status = "UNRESOLVED"
        result.reasons.append("registration_not_found")
        return result

    result.student_id = reg.student_id
    result.exam_id = reg.exam_id

    # Get student
    student = db.query(Student).filter(Student.id == reg.student_id).first()
    if student:
        result.student_usn = student.usn
        result.student_name = student.name

    # Hall ticket must be VERIFIED
    if ht.status != HallTicketStatus.VERIFIED.value:
        result.status = "UNRESOLVED"
        result.reasons.append(f"hall_ticket_status_{ht.status.lower()}")
        return result

    # Find seat assignment for this registration
    seat = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_registration_id == ht.exam_registration_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .first()
    )

    if seat is None:
        result.status = "UNRESOLVED"
        result.reasons.append("no_seat_assignment")
        return result

    result.seat_assignment_id = seat.id
    result.seat_number = seat.seat_number
    result.exam_hall_id = seat.exam_hall_id

    # Get hall name
    hall = db.query(ExamHall).filter(ExamHall.id == seat.exam_hall_id).first()
    if hall:
        result.exam_hall_name = f"{hall.building} - Room {hall.room_number}"

    result.status = "RESOLVED"
    return result


def resolve_bulk_seat_mappings(
    db: Session,
    exam_id: int | None = None,
    exam_hall_id: int | None = None,
) -> list[SeatMappingResult]:
    """Resolve seat mappings for all hall tickets, optionally filtered.

    Returns list of results including both RESOLVED and UNRESOLVED cases.
    """
    query = db.query(HallTicket).join(ExamRegistration)

    if exam_id is not None:
        query = query.filter(ExamRegistration.exam_id == exam_id)

    # Filter by hall via seat assignment if hall specified
    if exam_hall_id is not None:
        query = query.join(
            SeatAssignment,
            SeatAssignment.exam_registration_id == HallTicket.exam_registration_id,
        ).filter(
            SeatAssignment.exam_hall_id == exam_hall_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )

    tickets = query.all()
    return [resolve_hall_ticket_seat(db, ht.id) for ht in tickets]


def get_unresolved_mappings(db: Session, exam_id: int | None = None) -> list[SeatMappingResult]:
    """Get all hall tickets that could not be resolved to a seat.

    Useful for pre-exam auditing: find students with tickets but no seats.
    """
    query = db.query(HallTicket).join(ExamRegistration)

    if exam_id is not None:
        query = query.filter(ExamRegistration.exam_id == exam_id)

    tickets = query.all()
    results = [resolve_hall_ticket_seat(db, ht.id) for ht in tickets]
    return [r for r in results if r.status == "UNRESOLVED"]

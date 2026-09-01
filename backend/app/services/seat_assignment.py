from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.schemas.seat_assignment import SeatAssignmentCreate


def _validate_registration(db: Session, registration_id: int) -> ExamRegistration:
    reg = db.query(ExamRegistration).filter(
        ExamRegistration.id == registration_id
    ).first()
    if not reg:
        raise LookupError(f"Registration with id {registration_id} not found")
    return reg


def _validate_hall(db: Session, hall_id: int) -> ExamHall:
    hall = db.query(ExamHall).filter(ExamHall.id == hall_id).first()
    if not hall:
        raise LookupError(f"Hall with id {hall_id} not found")
    return hall


def _check_seat_duplicate(
    db: Session,
    exam_id: int,
    hall_id: int,
    seat_number: str,
) -> None:
    count = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_id == exam_id,
            SeatAssignment.exam_hall_id == hall_id,
            SeatAssignment.seat_number == seat_number,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .count()
    )
    if count > 0:
        raise ValueError(
            f"Seat '{seat_number}' in hall {hall_id} is already assigned for this exam"
        )


def _check_registration_single_active(
    db: Session,
    registration_id: int,
) -> None:
    count = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_registration_id == registration_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .count()
    )
    if count > 0:
        raise ValueError(
            f"Registration {registration_id} already has an active seat assignment"
        )


def _check_capacity(
    db: Session,
    exam_id: int,
    hall_id: int,
    hall: ExamHall,
) -> None:
    active_count = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_id == exam_id,
            SeatAssignment.exam_hall_id == hall_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .count()
    )
    if active_count >= hall.capacity:
        raise ValueError(
            f"Hall {hall_id} has reached its capacity of {hall.capacity}"
        )


def create_assignment(db: Session, data: SeatAssignmentCreate) -> SeatAssignment:
    reg = _validate_registration(db, data.exam_registration_id)
    if reg.status != RegistrationStatus.REGISTERED.value:
        raise ValueError(
            f"Registration {data.exam_registration_id} is not active "
            f"(status: {reg.status})"
        )

    hall = _validate_hall(db, data.exam_hall_id)
    if not hall.is_active:
        raise ValueError(f"Hall {data.exam_hall_id} is not active")

    seat_number = data.seat_number.strip()

    if hall.rows is not None and data.row_number is not None:
        if data.row_number > hall.rows:
            raise ValueError(
                f"Row {data.row_number} exceeds hall rows ({hall.rows})"
            )

    if hall.columns is not None and data.column_number is not None:
        if data.column_number > hall.columns:
            raise ValueError(
                f"Column {data.column_number} exceeds hall columns ({hall.columns})"
            )

    _check_seat_duplicate(db, reg.exam_id, data.exam_hall_id, seat_number)
    _check_registration_single_active(db, data.exam_registration_id)
    _check_capacity(db, reg.exam_id, data.exam_hall_id, hall)

    assignment = SeatAssignment(
        exam_registration_id=data.exam_registration_id,
        exam_hall_id=data.exam_hall_id,
        seat_number=seat_number,
        row_number=data.row_number,
        column_number=data.column_number,
        exam_id=reg.exam_id,
        student_id=reg.student_id,
        status=SeatAssignmentStatus.ASSIGNED.value,
    )
    db.add(assignment)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Seat '{seat_number}' in hall {data.exam_hall_id} "
            f"is already assigned for this exam"
        )

    db.refresh(assignment)
    return assignment


def get_assignment(db: Session, assignment_id: int) -> SeatAssignment | None:
    return (
        db.query(SeatAssignment)
        .options(
            joinedload(SeatAssignment.registration),
            joinedload(SeatAssignment.hall),
            joinedload(SeatAssignment.student),
            joinedload(SeatAssignment.exam),
        )
        .filter(SeatAssignment.id == assignment_id)
        .first()
    )


def list_assignments(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    exam_id: int | None = None,
    exam_hall_id: int | None = None,
    student_id: int | None = None,
    registration_id: int | None = None,
    status: str | None = None,
) -> tuple[list[SeatAssignment], int]:
    query = db.query(SeatAssignment).options(
        joinedload(SeatAssignment.registration),
        joinedload(SeatAssignment.hall),
        joinedload(SeatAssignment.student),
        joinedload(SeatAssignment.exam),
    )

    if exam_id is not None:
        query = query.filter(SeatAssignment.exam_id == exam_id)

    if exam_hall_id is not None:
        query = query.filter(SeatAssignment.exam_hall_id == exam_hall_id)

    if student_id is not None:
        query = query.filter(SeatAssignment.student_id == student_id)

    if registration_id is not None:
        query = query.filter(
            SeatAssignment.exam_registration_id == registration_id
        )

    if status is not None:
        query = query.filter(SeatAssignment.status == status.strip())

    total = query.count()
    assignments = (
        query.order_by(SeatAssignment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return assignments, total


def update_assignment(
    db: Session,
    assignment_id: int,
    status: str,
) -> SeatAssignment:
    assignment = db.query(SeatAssignment).filter(
        SeatAssignment.id == assignment_id
    ).first()
    if not assignment:
        raise LookupError(f"Assignment with id {assignment_id} not found")

    status = status.strip()
    if status not in (s.value for s in SeatAssignmentStatus):
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: ASSIGNED, CANCELLED"
        )

    assignment.status = status

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to update assignment status")

    db.refresh(assignment)
    return assignment


def cancel_assignment(db: Session, assignment_id: int) -> SeatAssignment:
    assignment = db.query(SeatAssignment).filter(
        SeatAssignment.id == assignment_id
    ).first()
    if not assignment:
        raise LookupError(f"Assignment with id {assignment_id} not found")

    assignment.status = SeatAssignmentStatus.CANCELLED.value

    db.commit()
    db.refresh(assignment)
    return assignment

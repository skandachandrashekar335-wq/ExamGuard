from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate


VALID_STATUSES = {s.value for s in HallTicketStatus}

# Allowed status transitions: from -> set of valid targets
STATUS_TRANSITIONS: dict[str, set[str]] = {
    HallTicketStatus.CREATED.value: {
        HallTicketStatus.EXTRACTED.value,
        HallTicketStatus.CANCELLED.value,
    },
    HallTicketStatus.EXTRACTED.value: {
        HallTicketStatus.MATCHED.value,
        HallTicketStatus.CANCELLED.value,
    },
    HallTicketStatus.MATCHED.value: {
        HallTicketStatus.VERIFIED.value,
        HallTicketStatus.REJECTED.value,
        HallTicketStatus.CANCELLED.value,
    },
    HallTicketStatus.VERIFIED.value: set(),
    HallTicketStatus.REJECTED.value: set(),
    HallTicketStatus.CANCELLED.value: set(),
}


def _validate_registration_exists(db: Session, exam_registration_id: int) -> ExamRegistration:
    reg = db.query(ExamRegistration).filter(
        ExamRegistration.id == exam_registration_id
    ).first()
    if not reg:
        raise LookupError(f"Exam registration with id {exam_registration_id} not found")
    return reg


def _check_duplicate(db: Session, exam_registration_id: int) -> None:
    existing = (
        db.query(HallTicket)
        .filter(HallTicket.exam_registration_id == exam_registration_id)
        .first()
    )
    if existing:
        raise ValueError(
            f"Hall ticket already exists for exam registration {exam_registration_id} "
            f"(id={existing.id}, status={existing.status})"
        )


def _validate_status_transition(current_status: str, new_status: str) -> None:
    allowed = STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{current_status}' to '{new_status}'. "
            f"Allowed transitions: {sorted(allowed) if allowed else 'none (terminal state)'}"
        )


def create_hall_ticket(db: Session, data: HallTicketCreate) -> HallTicket:
    _validate_registration_exists(db, data.exam_registration_id)
    _check_duplicate(db, data.exam_registration_id)

    ht = HallTicket(
        exam_registration_id=data.exam_registration_id,
        document_id=data.document_id,
        status=HallTicketStatus.CREATED.value,
    )
    db.add(ht)
    db.commit()
    db.refresh(ht)
    return ht


def get_hall_ticket(db: Session, hall_ticket_id: int) -> HallTicket | None:
    return db.query(HallTicket).filter(HallTicket.id == hall_ticket_id).first()


def get_hall_ticket_by_registration(
    db: Session, exam_registration_id: int
) -> HallTicket | None:
    return (
        db.query(HallTicket)
        .filter(HallTicket.exam_registration_id == exam_registration_id)
        .first()
    )


def update_hall_ticket(
    db: Session, hall_ticket_id: int, data: HallTicketUpdate
) -> HallTicket:
    ht = db.query(HallTicket).filter(HallTicket.id == hall_ticket_id).first()
    if not ht:
        raise LookupError(f"Hall ticket with id {hall_ticket_id} not found")

    if data.document_id is not None:
        ht.document_id = data.document_id
    if data.extraction_result_id is not None:
        ht.extraction_result_id = data.extraction_result_id
    if data.match_result_id is not None:
        ht.match_result_id = data.match_result_id
    if data.verification_outcome_id is not None:
        ht.verification_outcome_id = data.verification_outcome_id
    if data.rejection_reason is not None:
        ht.rejection_reason = data.rejection_reason

    if data.status is not None:
        if data.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{data.status}'. "
                f"Valid statuses: {sorted(VALID_STATUSES)}"
            )
        _validate_status_transition(ht.status, data.status)
        ht.status = data.status

    db.commit()
    db.refresh(ht)
    return ht


def list_hall_tickets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    exam_registration_id: int | None = None,
    status: str | None = None,
) -> dict:
    query = db.query(HallTicket)

    if exam_registration_id is not None:
        query = query.filter(HallTicket.exam_registration_id == exam_registration_id)
    if status is not None:
        query = query.filter(HallTicket.status == status)

    total = query.count()
    items = (
        query.order_by(desc(HallTicket.created_at))
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

import logging
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentType
from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.student import Student
from app.models.subject import Subject
from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate

logger = logging.getLogger(__name__)


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


def _validate_document_exists(db: Session, document_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise LookupError(f"Document with id {document_id} not found")
    return doc


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


def _transition(ht: HallTicket, new_status: str) -> None:
    _validate_status_transition(ht.status, new_status)
    ht.status = new_status
    ht.updated_at = datetime.now(timezone.utc)


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


def link_document(
    db: Session, hall_ticket_id: int, document_id: int
) -> HallTicket:
    ht = get_hall_ticket(db, hall_ticket_id)
    if not ht:
        raise LookupError(f"Hall ticket with id {hall_ticket_id} not found")
    doc = _validate_document_exists(db, document_id)
    if doc.document_type != DocumentType.HALL_TICKET.value:
        raise ValueError(
            f"Document {document_id} is type '{doc.document_type}', expected 'HALL_TICKET'"
        )
    if ht.document_id is not None:
        raise ValueError(
            f"Hall ticket {hall_ticket_id} already linked to document {ht.document_id}"
        )
    ht.document_id = document_id
    ht.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ht)
    return ht


def on_extraction_complete(
    db: Session,
    document_id: int,
    extraction_result_id: int,
) -> HallTicket | None:
    ht = (
        db.query(HallTicket)
        .filter(HallTicket.document_id == document_id)
        .first()
    )
    if not ht:
        logger.debug("No hall ticket linked to document %d", document_id)
        return None
    _transition(ht, HallTicketStatus.EXTRACTED.value)
    ht.extraction_result_id = extraction_result_id
    db.commit()
    db.refresh(ht)
    return ht


def on_match_complete(
    db: Session,
    document_id: int,
    match_result_id: int,
    overall_status: str,
) -> HallTicket | None:
    ht = (
        db.query(HallTicket)
        .filter(HallTicket.document_id == document_id)
        .first()
    )
    if not ht:
        logger.debug("No hall ticket linked to document %d", document_id)
        return None
    _transition(ht, HallTicketStatus.MATCHED.value)
    ht.match_result_id = match_result_id
    db.commit()
    db.refresh(ht)
    return ht


def approve(
    db: Session,
    hall_ticket_id: int,
    verification_outcome_id: int | None = None,
) -> HallTicket:
    ht = get_hall_ticket(db, hall_ticket_id)
    if not ht:
        raise LookupError(f"Hall ticket with id {hall_ticket_id} not found")
    _transition(ht, HallTicketStatus.VERIFIED.value)
    if verification_outcome_id is not None:
        ht.verification_outcome_id = verification_outcome_id
    ht.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ht)
    return ht


def reject(
    db: Session,
    hall_ticket_id: int,
    reason: str,
    verification_outcome_id: int | None = None,
) -> HallTicket:
    ht = get_hall_ticket(db, hall_ticket_id)
    if not ht:
        raise LookupError(f"Hall ticket with id {hall_ticket_id} not found")
    _transition(ht, HallTicketStatus.REJECTED.value)
    ht.rejection_reason = reason
    if verification_outcome_id is not None:
        ht.verification_outcome_id = verification_outcome_id
    ht.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ht)
    return ht


def get_with_context(db: Session, hall_ticket_id: int) -> dict | None:
    ht = get_hall_ticket(db, hall_ticket_id)
    if not ht:
        return None
    reg = db.query(ExamRegistration).filter(
        ExamRegistration.id == ht.exam_registration_id
    ).first()
    student = None
    exam = None
    if reg:
        student = db.query(Student).filter(Student.id == reg.student_id).first()
        exam = db.query(Exam).filter(Exam.id == reg.exam_id).first()
    document = None
    if ht.document_id:
        document = db.query(Document).filter(Document.id == ht.document_id).first()
    return {
        "hall_ticket": ht,
        "registration": reg,
        "student": student,
        "exam": exam,
        "document": document,
    }


def search_hall_tickets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    usn: str | None = None,
    exam_id: int | None = None,
    status: str | None = None,
    subject_code: str | None = None,
) -> dict:
    query = db.query(HallTicket).join(
        ExamRegistration, HallTicket.exam_registration_id == ExamRegistration.id
    )

    if usn is not None:
        query = query.join(Student, ExamRegistration.student_id == Student.id)
        query = query.filter(Student.usn.ilike(f"%{usn}%"))
    if exam_id is not None:
        query = query.filter(ExamRegistration.exam_id == exam_id)
    if status is not None:
        query = query.filter(HallTicket.status == status)
    if subject_code is not None:
        query = query.join(Exam, ExamRegistration.exam_id == Exam.id).join(
            Subject, Exam.subject_id == Subject.id
        ).filter(Subject.code == subject_code)

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

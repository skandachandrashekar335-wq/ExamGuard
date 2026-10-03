import logging
import re
from datetime import date, datetime, time, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus, DocumentType
from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration
from app.models.examination_session import ExaminationSession
from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus, ReviewStatus
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationMethod,
    IdentityVerificationStatus,
)
from app.models.exam_hall import ExamHall
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.subject import Subject
from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
from app.schemas.import_audit_log import ImportAuditLogCreate
from app.services.import_audit_log import complete_audit_log, create_audit_log
from app.services.student import normalize_usn

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


def _confirmed_field(fields: list[ExtractedField], field_name: str) -> str | None:
    field = next((item for item in fields if item.field_name == field_name), None)
    if field is None:
        return None
    value = field.corrected_value if field.corrected_value is not None else field.extracted_value
    return value.strip() if value is not None else None


def _normalize_hall_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _audit_candidate_enrollment(
    db: Session,
    *,
    performed_by: str,
    created: bool,
) -> None:
    audit = create_audit_log(
        db,
        ImportAuditLogCreate(
            import_type="candidate_enrollment",
            operation="enroll",
            total_rows=1,
        ),
    )
    audit.actor = performed_by[:100]
    db.commit()
    complete_audit_log(
        db,
        audit.id,
        successful=1 if created else 0,
        skipped=0 if created else 1,
        failed=0,
    )


def _validate_exam_context(
    exam: Exam,
    fields: list[ExtractedField],
) -> None:
    exam_name = _confirmed_field(fields, "exam_name")
    if exam_name:
        actual = _normalize_hall_label(exam_name)
        expected = _normalize_hall_label(exam.exam_name)
        if actual not in expected and expected not in actual:
            raise ValueError(
                f"Extracted exam '{exam_name}' does not match selected exam '{exam.exam_name}'"
            )

    subject_value = _confirmed_field(fields, "subject")
    if subject_value and exam.subject:
        actual_subject = _normalize_hall_label(subject_value)
        expected_subjects = {
            _normalize_hall_label(exam.subject.name),
            _normalize_hall_label(exam.subject.code),
        }
        if not any(
            actual_subject in expected or expected in actual_subject
            for expected in expected_subjects if expected
        ):
            raise ValueError(
                f"Extracted subject '{subject_value}' does not match selected exam subject"
            )

    extracted_date = _confirmed_field(fields, "exam_date")
    if extracted_date:
        try:
            parsed_date = date.fromisoformat(extracted_date)
        except ValueError as exc:
            raise ValueError("Correct the extracted exam date before enrollment") from exc
        if parsed_date != exam.exam_date:
            raise ValueError(
                f"Extracted exam date {parsed_date} does not match selected exam date {exam.exam_date}"
            )

    for field_name, exam_time in (
        ("start_time", exam.start_time),
        ("end_time", exam.end_time),
    ):
        extracted_time = _confirmed_field(fields, field_name)
        if extracted_time:
            try:
                parsed_time = time.fromisoformat(extracted_time)
            except ValueError as exc:
                raise ValueError(f"Correct the extracted {field_name} before enrollment") from exc
            if parsed_time != exam_time:
                raise ValueError(
                    f"Extracted {field_name.replace('_', ' ')} does not match selected exam"
                )


def _find_admit_card_hall(db: Session, exam_id: int, hall_label: str | None) -> ExamHall | None:
    if not hall_label:
        return None
    normalized = _normalize_hall_label(hall_label)
    candidates = (
        db.query(ExamHall)
        .join(ExaminationSession, ExaminationSession.exam_hall_id == ExamHall.id)
        .filter(ExaminationSession.exam_id == exam_id, ExamHall.is_active.is_(True))
        .all()
    )
    matches = []
    for hall in candidates:
        labels = {
            _normalize_hall_label(hall.building),
            _normalize_hall_label(hall.room_number),
            _normalize_hall_label(f"{hall.building} {hall.room_number}"),
        }
        if hall.name:
            labels.add(_normalize_hall_label(hall.name))
        if normalized in labels:
            matches.append(hall)
    return matches[0] if len(matches) == 1 else None


def confirm_candidate_enrollment(
    db: Session,
    document_id: int,
    *,
    exam_id: int,
    confirmed: bool,
    performed_by: str,
) -> dict:
    """Create/link existing candidate records after explicit admin review."""
    if not confirmed:
        raise ValueError("Explicit admin confirmation is required")

    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise LookupError(f"Document {document_id} not found")
    if document.document_type != DocumentType.HALL_TICKET.value:
        raise ValueError("Only hall-ticket documents can enroll candidates")
    if document.exam_id is None or document.exam_id != exam_id:
        raise ValueError("Enrollment exam does not match the exam selected at upload")
    if document.status != DocumentStatus.PROCESSED.value:
        raise ValueError("Complete OCR review before confirming candidate enrollment")

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise LookupError(f"Exam with id {exam_id} not found")
    if not exam.is_active:
        raise ValueError(f"Exam {exam_id} is inactive")

    extraction = (
        db.query(ExtractionResult)
        .filter(ExtractionResult.document_id == document_id)
        .order_by(ExtractionResult.id.desc())
        .first()
    )
    if (
        extraction is None
        or extraction.status != ExtractionStatus.COMPLETED.value
        or extraction.reviewed_at is None
    ):
        raise ValueError("Complete OCR review before confirming candidate enrollment")
    fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.extraction_result_id == extraction.id)
        .order_by(ExtractedField.id)
        .all()
    )
    if any(field.review_status == ReviewStatus.REVIEW_REQUIRED.value for field in fields):
        raise ValueError("Resolve every uncertain extracted field before enrollment")
    _validate_exam_context(exam, fields)

    usn_value = _confirmed_field(fields, "usn")
    name_value = _confirmed_field(fields, "name")
    if not usn_value:
        raise ValueError("A reviewed USN / roll / registration number is required")
    if not name_value:
        raise ValueError("A reviewed student name is required")
    usn = normalize_usn(usn_value).upper()

    existing_ticket = (
        db.query(HallTicket)
        .filter(HallTicket.document_id == document_id)
        .first()
    )
    if existing_ticket is not None:
        registration = db.query(ExamRegistration).filter(
            ExamRegistration.id == existing_ticket.exam_registration_id
        ).first()
        if registration is None or registration.exam_id != exam_id:
            raise ValueError("This hall ticket is already linked outside the selected exam")
        student = db.query(Student).filter(Student.id == registration.student_id).first()
        attempt = (
            db.query(IdentityVerificationAttempt)
            .filter(
                IdentityVerificationAttempt.exam_registration_id == registration.id,
                IdentityVerificationAttempt.verification_method == IdentityVerificationMethod.FACE.value,
            )
            .order_by(IdentityVerificationAttempt.id.desc())
            .first()
        )
        seat = db.query(SeatAssignment).filter(
            SeatAssignment.exam_registration_id == registration.id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        ).first()
        if student is None or attempt is None:
            raise ValueError("Existing enrollment is incomplete and requires operator review")
        _audit_candidate_enrollment(
            db, performed_by=performed_by, created=False
        )
        return {
            "document_id": document_id,
            "exam_id": exam_id,
            "student_id": student.id,
            "registration_id": registration.id,
            "hall_ticket_id": existing_ticket.id,
            "seat_assignment_id": seat.id if seat else None,
            "identity_attempt_id": attempt.id,
            "student_created": False,
            "registration_created": False,
            "reference_photo_enrolled": bool(attempt.reference_face_url),
            "needs_seat_assignment": seat is None,
            "already_enrolled": True,
        }

    student = (
        db.query(Student)
        .filter(Student.usn.ilike(usn))
        .first()
    )
    student_created = student is None
    if student is None:
        student = Student(usn=usn, name=name_value)
        db.add(student)
        db.flush()
    elif not student.is_active:
        raise ValueError(f"Student with USN '{student.usn}' is inactive")
    elif student.name.strip().casefold() != name_value.strip().casefold():
        raise ValueError(
            f"Student name does not match existing USN '{student.usn}'. "
            "Correct the reviewed name before enrolling."
        )

    registration = db.query(ExamRegistration).filter(
        ExamRegistration.student_id == student.id,
        ExamRegistration.exam_id == exam_id,
    ).first()
    registration_created = registration is None
    if registration is None:
        registration = ExamRegistration(
            student_id=student.id,
            exam_id=exam_id,
            status="REGISTERED",
        )
        db.add(registration)
        db.flush()
    elif registration.status != "REGISTERED":
        raise ValueError(
            f"Registration for USN '{student.usn}' and this exam is not active"
        )

    existing_ticket = db.query(HallTicket).filter(
        HallTicket.exam_registration_id == registration.id
    ).first()
    if existing_ticket is not None and existing_ticket.document_id != document_id:
        raise ValueError(
            f"A hall ticket is already linked to this registration (ticket {existing_ticket.id})"
        )
    if existing_ticket is None:
        hall_ticket = HallTicket(
            exam_registration_id=registration.id,
            document_id=document_id,
            extraction_result_id=extraction.id,
            status=HallTicketStatus.EXTRACTED.value,
        )
        db.add(hall_ticket)
        db.flush()
    else:
        hall_ticket = existing_ticket

    seat_assignment = db.query(SeatAssignment).filter(
        SeatAssignment.exam_registration_id == registration.id,
        SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
    ).first()
    seat_number = _confirmed_field(fields, "seat_number")
    hall = _find_admit_card_hall(
        db, exam_id, _confirmed_field(fields, "exam_hall")
    )
    if seat_assignment is not None:
        if (
            hall is not None and seat_assignment.exam_hall_id != hall.id
        ) or (
            seat_number is not None
            and seat_assignment.seat_number.strip().casefold() != seat_number.casefold()
        ):
            raise ValueError(
                "A different active seat assignment already exists for this registration"
            )
    elif seat_number and hall is not None:
        seat_assignment = SeatAssignment(
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            seat_number=seat_number,
            exam_id=exam_id,
            student_id=student.id,
            status=SeatAssignmentStatus.ASSIGNED.value,
        )
        db.add(seat_assignment)
        db.flush()

    attempt = (
        db.query(IdentityVerificationAttempt)
        .filter(
            IdentityVerificationAttempt.exam_registration_id == registration.id,
            IdentityVerificationAttempt.verification_method == IdentityVerificationMethod.FACE.value,
        )
        .order_by(IdentityVerificationAttempt.id.desc())
        .first()
    )
    if attempt is None:
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            status=IdentityVerificationStatus.CREATED.value,
            verification_method=IdentityVerificationMethod.FACE.value,
            decision=IdentityVerificationDecision.PENDING.value,
        )
        db.add(attempt)
        db.flush()
    elif attempt.hall_ticket_id is None:
        attempt.hall_ticket_id = hall_ticket.id

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            "Enrollment conflicts with an existing student, registration, ticket, or seat assignment"
        ) from exc

    db.refresh(student)
    db.refresh(registration)
    db.refresh(hall_ticket)
    db.refresh(attempt)
    if seat_assignment is not None:
        db.refresh(seat_assignment)
    logger.info(
        "CANDIDATE_ENROLLMENT_AUDIT: document_id=%d exam_id=%d registration_id=%d "
        "student_id=%d performed_by=%s",
        document_id, exam_id, registration.id, student.id, performed_by,
    )
    _audit_candidate_enrollment(db, performed_by=performed_by, created=True)
    return {
        "document_id": document_id,
        "exam_id": exam_id,
        "student_id": student.id,
        "registration_id": registration.id,
        "hall_ticket_id": hall_ticket.id,
        "seat_assignment_id": seat_assignment.id if seat_assignment else None,
        "identity_attempt_id": attempt.id,
        "student_created": student_created,
        "registration_created": registration_created,
        "reference_photo_enrolled": bool(attempt.reference_face_url),
        "needs_seat_assignment": seat_assignment is None,
        "already_enrolled": False,
    }


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
    exam_id: int | None = None,
    status: str | None = None,
) -> dict:
    query = db.query(HallTicket)

    if exam_registration_id is not None:
        query = query.filter(HallTicket.exam_registration_id == exam_registration_id)
    if exam_id is not None:
        query = query.join(
            ExamRegistration, HallTicket.exam_registration_id == ExamRegistration.id
        ).filter(ExamRegistration.exam_id == exam_id)
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

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.student import Student
from app.schemas.exam_registration import ExamRegistrationCreate


def _validate_student(db: Session, student_id: int) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise LookupError(f"Student with id {student_id} not found")
    return student


def _validate_exam(db: Session, exam_id: int) -> Exam:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise LookupError(f"Exam with id {exam_id} not found")
    return exam


def _check_duplicate(
    db: Session,
    student_id: int,
    exam_id: int,
) -> None:
    query = db.query(ExamRegistration).filter(
        ExamRegistration.student_id == student_id,
        ExamRegistration.exam_id == exam_id,
    )
    if query.first():
        raise ValueError(
            f"Student {student_id} is already registered for exam {exam_id}"
        )


def create_registration(db: Session, data: ExamRegistrationCreate) -> ExamRegistration:
    student = _validate_student(db, data.student_id)
    if not student.is_active:
        raise ValueError(f"Student {data.student_id} is not active")

    exam = _validate_exam(db, data.exam_id)
    if not exam.is_active:
        raise ValueError(f"Exam {data.exam_id} is not active")

    _check_duplicate(db, data.student_id, data.exam_id)

    registration = ExamRegistration(
        student_id=data.student_id,
        exam_id=data.exam_id,
        status=RegistrationStatus.REGISTERED.value,
    )
    db.add(registration)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Student {data.student_id} is already registered for exam {data.exam_id}"
        )

    db.refresh(registration)
    return registration


def get_registration(db: Session, registration_id: int) -> ExamRegistration | None:
    return (
        db.query(ExamRegistration)
        .options(
            joinedload(ExamRegistration.student),
            joinedload(ExamRegistration.exam),
        )
        .filter(ExamRegistration.id == registration_id)
        .first()
    )


def list_registrations(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
    exam_id: int | None = None,
    status: str | None = None,
) -> tuple[list[ExamRegistration], int]:
    query = db.query(ExamRegistration).options(
        joinedload(ExamRegistration.student),
        joinedload(ExamRegistration.exam),
    )

    if student_id is not None:
        query = query.filter(ExamRegistration.student_id == student_id)

    if exam_id is not None:
        query = query.filter(ExamRegistration.exam_id == exam_id)

    if status is not None:
        query = query.filter(ExamRegistration.status == status.strip())

    total = query.count()
    registrations = (
        query.order_by(ExamRegistration.registered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return registrations, total


def update_registration(
    db: Session,
    registration_id: int,
    status: str,
) -> ExamRegistration:
    registration = db.query(ExamRegistration).filter(
        ExamRegistration.id == registration_id
    ).first()
    if not registration:
        raise LookupError(f"Registration with id {registration_id} not found")

    status = status.strip()
    if status not in (s.value for s in RegistrationStatus):
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: REGISTERED, CANCELLED"
        )

    registration.status = status

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to update registration status")

    db.refresh(registration)
    return registration


def cancel_registration(db: Session, registration_id: int) -> ExamRegistration:
    registration = db.query(ExamRegistration).filter(
        ExamRegistration.id == registration_id
    ).first()
    if not registration:
        raise LookupError(f"Registration with id {registration_id} not found")

    registration.status = RegistrationStatus.CANCELLED.value

    db.commit()
    db.refresh(registration)
    return registration

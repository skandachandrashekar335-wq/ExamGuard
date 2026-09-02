import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.student import Student
from app.schemas.import_registrations import (
    BulkCancelItemResult,
    BulkRegistrationItemResult,
)

logger = logging.getLogger(__name__)


def _process_single_registration(
    db: Session, exam_id: int, student_id: int
) -> BulkRegistrationItemResult:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return BulkRegistrationItemResult(
            student_id=student_id,
            status="failed",
            error=f"Student with id {student_id} not found",
        )
    if not student.is_active:
        return BulkRegistrationItemResult(
            student_id=student_id,
            status="failed",
            error=f"Student {student_id} is not active",
        )

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return BulkRegistrationItemResult(
            student_id=student_id,
            status="failed",
            error=f"Exam with id {exam_id} not found",
        )
    if not exam.is_active:
        return BulkRegistrationItemResult(
            student_id=student_id,
            status="failed",
            error=f"Exam {exam_id} is not active",
        )

    existing = (
        db.query(ExamRegistration)
        .filter(
            ExamRegistration.student_id == student_id,
            ExamRegistration.exam_id == exam_id,
        )
        .first()
    )
    if existing:
        return BulkRegistrationItemResult(
            student_id=student_id,
            status="skipped",
            registration_id=existing.id,
            error=(
                f"Student {student_id} is already registered for exam {exam_id}"
            ),
        )

    registration = ExamRegistration(
        student_id=student_id,
        exam_id=exam_id,
        status=RegistrationStatus.REGISTERED.value,
    )
    db.add(registration)

    try:
        db.commit()
        db.refresh(registration)
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(ExamRegistration)
            .filter(
                ExamRegistration.student_id == student_id,
                ExamRegistration.exam_id == exam_id,
            )
            .first()
        )
        return BulkRegistrationItemResult(
            student_id=student_id,
            status="skipped",
            registration_id=existing.id if existing else None,
            error=(
                f"Student {student_id} is already registered for exam {exam_id}"
            ),
        )

    return BulkRegistrationItemResult(
        student_id=student_id,
        status="created",
        registration_id=registration.id,
    )


def bulk_register(
    db: Session, exam_id: int, student_ids: list[int]
) -> dict:
    results: list[BulkRegistrationItemResult] = []
    created = 0
    skipped = 0
    failed = 0

    for student_id in student_ids:
        try:
            result = _process_single_registration(db, exam_id, student_id)
            results.append(result)
            if result.status == "created":
                created += 1
            elif result.status == "skipped":
                skipped += 1
            else:
                failed += 1
        except Exception:
            logger.exception(
                "Unexpected error registering student %d for exam %d",
                student_id,
                exam_id,
            )
            failed += 1
            results.append(
                BulkRegistrationItemResult(
                    student_id=student_id,
                    status="failed",
                    error="Unexpected error",
                )
            )

    return {
        "total": len(student_ids),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }


def _process_single_cancel(
    db: Session, registration_id: int
) -> BulkCancelItemResult:
    registration = db.query(ExamRegistration).filter(
        ExamRegistration.id == registration_id
    ).first()
    if not registration:
        return BulkCancelItemResult(
            registration_id=registration_id,
            status="failed",
            error=f"Registration with id {registration_id} not found",
        )

    if registration.status == RegistrationStatus.CANCELLED.value:
        return BulkCancelItemResult(
            registration_id=registration_id,
            status="skipped",
            error=(
                f"Registration {registration_id} is already cancelled"
            ),
        )

    registration.status = RegistrationStatus.CANCELLED.value

    try:
        db.commit()
        db.refresh(registration)
    except IntegrityError:
        db.rollback()
        return BulkCancelItemResult(
            registration_id=registration_id,
            status="failed",
            error="Failed to cancel registration",
        )

    return BulkCancelItemResult(
        registration_id=registration_id,
        status="cancelled",
    )


def bulk_cancel(
    db: Session, registration_ids: list[int]
) -> dict:
    results: list[BulkCancelItemResult] = []
    cancelled = 0
    skipped = 0
    failed = 0

    for reg_id in registration_ids:
        try:
            result = _process_single_cancel(db, reg_id)
            results.append(result)
            if result.status == "cancelled":
                cancelled += 1
            elif result.status == "skipped":
                skipped += 1
            else:
                failed += 1
        except Exception:
            logger.exception("Unexpected error cancelling registration %d", reg_id)
            failed += 1
            results.append(
                BulkCancelItemResult(
                    registration_id=reg_id,
                    status="failed",
                    error="Unexpected error",
                )
            )

    return {
        "total": len(registration_ids),
        "cancelled": cancelled,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }

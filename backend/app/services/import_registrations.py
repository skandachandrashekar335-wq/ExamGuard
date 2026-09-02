from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.student import Student
from app.schemas.import_audit_log import ImportAuditLogCreate
from app.schemas.import_registrations import (
    BulkCancelItemResult,
    BulkRegistrationItemResult,
)
from app.services.import_audit_log import complete_audit_log, create_audit_log
from app.services.import_common import (
    build_error_summary,
    count_import_results,
    process_import_items,
)


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
    audit_log = create_audit_log(
        db,
        ImportAuditLogCreate(
            import_type="registrations",
            operation="import",
            total_rows=len(student_ids),
        ),
    )

    try:
        def _process(student_id: int) -> BulkRegistrationItemResult:
            return _process_single_registration(db, exam_id, student_id)

        def _error(student_id: int) -> BulkRegistrationItemResult:
            return BulkRegistrationItemResult(
                student_id=student_id,
                status="failed",
                error="Unexpected error",
            )

        results = process_import_items(student_ids, _process, _error)
        counts = count_import_results(results)

        response = {
            "total": len(student_ids),
            "created": counts.get("created", 0),
            "skipped": counts.get("skipped", 0),
            "failed": counts.get("failed", 0),
            "results": results,
        }

        complete_audit_log(
            db,
            audit_log.id,
            successful=response["created"],
            skipped=response["skipped"],
            failed=response["failed"],
            error_summary=build_error_summary(results),
        )

        return response
    except Exception as exc:
        from app.services.import_audit_log import fail_audit_log
        fail_audit_log(db, audit_log.id, error_summary=str(exc)[:2000])
        raise


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
    audit_log = create_audit_log(
        db,
        ImportAuditLogCreate(
            import_type="registration_cancellations",
            operation="cancellation",
            total_rows=len(registration_ids),
        ),
    )

    try:
        def _process(registration_id: int) -> BulkCancelItemResult:
            return _process_single_cancel(db, registration_id)

        def _error(registration_id: int) -> BulkCancelItemResult:
            return BulkCancelItemResult(
                registration_id=registration_id,
                status="failed",
                error="Unexpected error",
            )

        results = process_import_items(registration_ids, _process, _error)
        counts = count_import_results(results)

        cancelled = counts.get("cancelled", 0)
        response = {
            "total": len(registration_ids),
            "cancelled": cancelled,
            "skipped": counts.get("skipped", 0),
            "failed": counts.get("failed", 0),
            "results": results,
        }

        complete_audit_log(
            db,
            audit_log.id,
            successful=cancelled,
            skipped=response["skipped"],
            failed=response["failed"],
            error_summary=build_error_summary(results),
        )

        return response
    except Exception as exc:
        from app.services.import_audit_log import fail_audit_log
        fail_audit_log(db, audit_log.id, error_summary=str(exc)[:2000])
        raise

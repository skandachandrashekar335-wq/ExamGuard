from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student
from app.schemas.import_audit_log import ImportAuditLogCreate
from app.schemas.import_students import (
    ImportStudentItem,
    ImportStudentItemResult,
)
from app.services.import_audit_log import complete_audit_log, create_audit_log
from app.services.import_common import (
    build_error_summary,
    count_import_results,
    process_import_items,
)
from app.services.student import normalize_usn

IMPORT_TYPE = "students"
IMPORT_OPERATION = "import"


def _process_single(db: Session, item: ImportStudentItem) -> ImportStudentItemResult:
    usn = normalize_usn(item.usn)
    name = item.name.strip()

    existing = db.query(Student).filter(Student.usn == usn).first()
    if existing:
        return ImportStudentItemResult(
            usn=usn,
            status="skipped",
            error=f"Student with USN '{usn}' already exists",
        )

    student = Student(usn=usn, name=name)
    db.add(student)

    try:
        db.commit()
        db.refresh(student)
    except IntegrityError:
        db.rollback()
        return ImportStudentItemResult(
            usn=usn,
            status="skipped",
            error=f"Student with USN '{usn}' already exists",
        )

    return ImportStudentItemResult(usn=usn, status="created")


def import_students(
    db: Session, items: list[ImportStudentItem]
) -> dict:
    audit_log = create_audit_log(
        db,
        ImportAuditLogCreate(
            import_type=IMPORT_TYPE,
            operation=IMPORT_OPERATION,
            total_rows=len(items),
        ),
    )

    try:
        def _process(item: ImportStudentItem) -> ImportStudentItemResult:
            return _process_single(db, item)

        def _error(item: ImportStudentItem) -> ImportStudentItemResult:
            return ImportStudentItemResult(
                usn=item.usn.strip() if item.usn else "",
                status="failed",
                error="Unexpected error",
            )

        results = process_import_items(items, _process, _error)
        counts = count_import_results(results)

        response = {
            "total": len(items),
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

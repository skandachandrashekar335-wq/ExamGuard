import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student
from app.schemas.import_students import (
    ImportStudentItem,
    ImportStudentItemResult,
)
from app.services.student import normalize_usn

logger = logging.getLogger(__name__)


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
    results: list[ImportStudentItemResult] = []
    created = 0
    skipped = 0
    failed = 0

    for item in items:
        try:
            result = _process_single(db, item)
            results.append(result)
            if result.status == "created":
                created += 1
            else:
                skipped += 1
        except Exception:
            logger.exception("Unexpected error importing student USN=%s", item.usn)
            failed += 1
            results.append(
                ImportStudentItemResult(
                    usn=item.usn.strip() if item.usn else "",
                    status="failed",
                    error="Unexpected error",
                )
            )

    return {
        "total": len(items),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student
from app.schemas.import_students import (
    ImportStudentItem,
    ImportStudentItemResult,
)
from app.services.import_common import count_import_results, process_import_items
from app.services.student import normalize_usn


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

    return {
        "total": len(items),
        "created": counts.get("created", 0),
        "skipped": counts.get("skipped", 0),
        "failed": counts.get("failed", 0),
        "results": results,
    }

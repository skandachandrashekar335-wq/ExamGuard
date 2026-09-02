from datetime import date, time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.subject import Subject
from app.schemas.import_subjects_exams import (
    ImportExamItem,
    ImportExamItemResult,
    ImportSubjectItem,
    ImportSubjectItemResult,
)
from app.services.import_common import count_import_results, process_import_items


def _normalize_code(code: str) -> str:
    return code.strip()


def _normalize_department(dept: str) -> str:
    return dept.strip()


def _parse_time(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) == 2:
        return time(int(parts[0]), int(parts[1]))
    if len(parts) == 3:
        return time(int(parts[0]), int(parts[1]), int(parts[2]))
    raise ValueError(f"Invalid time format: {value}")


def _parse_date(value: str) -> date:
    parts = value.strip().split("-")
    if len(parts) != 3:
        raise ValueError(f"Invalid date format: {value}")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _process_subject(
    db: Session, item: ImportSubjectItem
) -> ImportSubjectItemResult:
    code = _normalize_code(item.code)
    department = _normalize_department(item.department)
    name = item.name.strip()

    existing = (
        db.query(Subject)
        .filter(Subject.code == code, Subject.department == department)
        .first()
    )
    if existing:
        return ImportSubjectItemResult(
            code=code,
            department=department,
            status="skipped",
            error=(
                f"Subject '{code}' already exists in department '{department}'"
            ),
        )

    subject = Subject(
        code=code,
        name=name,
        department=department,
        semester=item.semester,
        credits=item.credits,
    )
    db.add(subject)

    try:
        db.commit()
        db.refresh(subject)
    except IntegrityError:
        db.rollback()
        return ImportSubjectItemResult(
            code=code,
            department=department,
            status="skipped",
            error=(
                f"Subject '{code}' already exists in department '{department}'"
            ),
        )

    return ImportSubjectItemResult(
        code=code, department=department, status="created"
    )


def _resolve_subject(
    db: Session, subject_code: str, department: str
) -> Subject | None:
    code = _normalize_code(subject_code)
    dept = _normalize_department(department)
    return (
        db.query(Subject)
        .filter(Subject.code == code, Subject.department == dept)
        .first()
    )


def _process_exam(
    db: Session, item: ImportExamItem
) -> ImportExamItemResult:
    subject_code = _normalize_code(item.subject_code)
    department = _normalize_department(item.department)

    try:
        exam_date = _parse_date(item.exam_date)
    except ValueError as e:
        return ImportExamItemResult(
            subject_code=subject_code,
            exam_name=item.exam_name.strip(),
            status="failed",
            error=str(e),
        )

    try:
        start_time = _parse_time(item.start_time)
        end_time = _parse_time(item.end_time)
    except ValueError as e:
        return ImportExamItemResult(
            subject_code=subject_code,
            exam_name=item.exam_name.strip(),
            status="failed",
            error=str(e),
        )

    if start_time >= end_time:
        return ImportExamItemResult(
            subject_code=subject_code,
            exam_name=item.exam_name.strip(),
            status="failed",
            error="start_time must be before end_time",
        )

    subject = _resolve_subject(db, subject_code, department)
    if subject is None:
        return ImportExamItemResult(
            subject_code=subject_code,
            exam_name=item.exam_name.strip(),
            status="failed",
            error=(
                f"Subject '{subject_code}' not found in department '{department}'"
            ),
        )

    existing = (
        db.query(Exam)
        .filter(
            Exam.subject_id == subject.id,
            Exam.exam_date == exam_date,
            Exam.start_time == start_time,
        )
        .first()
    )
    if existing:
        return ImportExamItemResult(
            subject_code=subject_code,
            exam_name=item.exam_name.strip(),
            status="skipped",
            error=(
                f"Exam for subject '{subject_code}' on {exam_date} "
                f"at {start_time} already exists"
            ),
        )

    exam = Exam(
        subject_id=subject.id,
        exam_name=item.exam_name.strip(),
        exam_date=exam_date,
        start_time=start_time,
        end_time=end_time,
        semester=item.semester,
        department=department,
    )
    db.add(exam)

    try:
        db.commit()
        db.refresh(exam)
    except IntegrityError:
        db.rollback()
        return ImportExamItemResult(
            subject_code=subject_code,
            exam_name=item.exam_name.strip(),
            status="skipped",
            error=(
                f"Exam for subject '{subject_code}' on {exam_date} "
                f"at {start_time} already exists"
            ),
        )

    return ImportExamItemResult(
        subject_code=subject_code,
        exam_name=item.exam_name.strip(),
        status="created",
    )


def import_subjects_exams(
    db: Session,
    subject_items: list[ImportSubjectItem],
    exam_items: list[ImportExamItem],
) -> dict:
    def _process_subject_item(
        item: ImportSubjectItem,
    ) -> ImportSubjectItemResult:
        return _process_subject(db, item)

    def _subject_error(
        item: ImportSubjectItem,
    ) -> ImportSubjectItemResult:
        return ImportSubjectItemResult(
            code=item.code.strip() if item.code else "",
            department=item.department.strip() if item.department else "",
            status="failed",
            error="Unexpected error",
        )

    def _process_exam_item(item: ImportExamItem) -> ImportExamItemResult:
        return _process_exam(db, item)

    def _exam_error(item: ImportExamItem) -> ImportExamItemResult:
        return ImportExamItemResult(
            subject_code=item.subject_code.strip() if item.subject_code else "",
            exam_name=item.exam_name.strip() if item.exam_name else "",
            status="failed",
            error="Unexpected error",
        )

    subject_results = process_import_items(
        subject_items, _process_subject_item, _subject_error
    )
    subject_counts = count_import_results(subject_results)

    exam_results = process_import_items(
        exam_items, _process_exam_item, _exam_error
    )
    exam_counts = count_import_results(exam_results)

    return {
        "subject_total": len(subject_items),
        "subject_created": subject_counts.get("created", 0),
        "subject_skipped": subject_counts.get("skipped", 0),
        "subject_failed": subject_counts.get("failed", 0),
        "exam_total": len(exam_items),
        "exam_created": exam_counts.get("created", 0),
        "exam_skipped": exam_counts.get("skipped", 0),
        "exam_failed": exam_counts.get("failed", 0),
        "subject_results": subject_results,
        "exam_results": exam_results,
    }

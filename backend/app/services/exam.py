from datetime import date

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.exam import Exam
from app.models.subject import Subject
from app.schemas.exam import ExamCreate, ExamUpdate


def _validate_subject_exists(db: Session, subject_id: int) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise LookupError(f"Subject with id {subject_id} not found")
    return subject


def _check_duplicate(
    db: Session,
    subject_id: int,
    exam_date: date,
    start_time,
    exclude_id: int | None = None,
) -> None:
    query = db.query(Exam).filter(
        Exam.subject_id == subject_id,
        Exam.exam_date == exam_date,
        Exam.start_time == start_time,
    )
    if exclude_id is not None:
        query = query.filter(Exam.id != exclude_id)
    if query.first():
        raise ValueError(
            f"Exam for subject {subject_id} on {exam_date} at {start_time} already exists"
        )


def create_exam(db: Session, data: ExamCreate) -> Exam:
    _validate_subject_exists(db, data.subject_id)
    _check_duplicate(db, data.subject_id, data.exam_date, data.start_time)

    exam = Exam(
        subject_id=data.subject_id,
        exam_name=data.exam_name.strip(),
        exam_date=data.exam_date,
        start_time=data.start_time,
        end_time=data.end_time,
        semester=data.semester,
        department=data.department.strip(),
    )
    db.add(exam)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Exam for subject {data.subject_id} on {data.exam_date} at {data.start_time} already exists"
        )

    db.refresh(exam)
    return exam


def get_exam(db: Session, exam_id: int) -> Exam | None:
    return (
        db.query(Exam)
        .options(joinedload(Exam.subject))
        .filter(Exam.id == exam_id)
        .first()
    )


def list_exams(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    subject_id: int | None = None,
    department: str | None = None,
    semester: int | None = None,
    exam_date: date | None = None,
    include_inactive: bool = False,
) -> tuple[list[Exam], int]:
    query = db.query(Exam).options(joinedload(Exam.subject))

    if not include_inactive:
        query = query.filter(Exam.is_active == True)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(Exam.exam_name.ilike(pattern))

    if subject_id is not None:
        query = query.filter(Exam.subject_id == subject_id)

    if department:
        query = query.filter(Exam.department == department.strip())

    if semester is not None:
        query = query.filter(Exam.semester == semester)

    if exam_date is not None:
        query = query.filter(Exam.exam_date == exam_date)

    total = query.count()
    exams = (
        query.order_by(Exam.exam_date, Exam.start_time)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return exams, total


def update_exam(db: Session, exam_id: int, data: ExamUpdate) -> Exam:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise LookupError(f"Exam with id {exam_id} not found")

    update_data = data.model_dump(exclude_unset=True)

    if "exam_name" in update_data and update_data["exam_name"] is not None:
        update_data["exam_name"] = update_data["exam_name"].strip()

    if "department" in update_data and update_data["department"] is not None:
        update_data["department"] = update_data["department"].strip()

    if "subject_id" in update_data:
        _validate_subject_exists(db, update_data["subject_id"])

    new_subject_id = update_data.get("subject_id", exam.subject_id)
    new_exam_date = update_data.get("exam_date", exam.exam_date)
    new_start_time = update_data.get("start_time", exam.start_time)

    _check_duplicate(
        db,
        new_subject_id,
        new_exam_date,
        new_start_time,
        exclude_id=exam_id,
    )

    for field, value in update_data.items():
        setattr(exam, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Exam for subject {new_subject_id} on {new_exam_date} at {new_start_time} already exists"
        )

    db.refresh(exam)
    return exam


def deactivate_exam(db: Session, exam_id: int) -> Exam:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise LookupError(f"Exam with id {exam_id} not found")

    exam.is_active = False
    db.commit()
    db.refresh(exam)
    return exam

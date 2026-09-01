from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectUpdate


def normalize_code(code: str) -> str:
    return code.strip()


def normalize_department(department: str) -> str:
    return department.strip()


def create_subject(db: Session, data: SubjectCreate) -> Subject:
    code = normalize_code(data.code)
    department = normalize_department(data.department)
    name = data.name.strip()

    existing = (
        db.query(Subject)
        .filter(Subject.code == code, Subject.department == department)
        .first()
    )
    if existing:
        raise ValueError(
            f"Subject '{code}' already exists in department '{department}'"
        )

    subject = Subject(
        code=code,
        name=name,
        department=department,
        semester=data.semester,
        credits=data.credits,
    )
    db.add(subject)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Subject '{code}' already exists in department '{department}'"
        )

    db.refresh(subject)
    return subject


def get_subject(db: Session, subject_id: int) -> Subject | None:
    return db.query(Subject).filter(Subject.id == subject_id).first()


def list_subjects(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    department: str | None = None,
    semester: int | None = None,
    include_inactive: bool = False,
) -> tuple[list[Subject], int]:
    query = db.query(Subject)

    if not include_inactive:
        query = query.filter(Subject.is_active == True)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Subject.code.ilike(pattern),
                Subject.name.ilike(pattern),
            )
        )

    if department:
        query = query.filter(Subject.department == department.strip())

    if semester is not None:
        query = query.filter(Subject.semester == semester)

    total = query.count()
    subjects = (
        query.order_by(Subject.department, Subject.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return subjects, total


def update_subject(db: Session, subject_id: int, data: SubjectUpdate) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise LookupError(f"Subject with id {subject_id} not found")

    update_data = data.model_dump(exclude_unset=True)

    if "code" in update_data and update_data["code"] is not None:
        update_data["code"] = normalize_code(update_data["code"])

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    if "department" in update_data and update_data["department"] is not None:
        update_data["department"] = normalize_department(update_data["department"])

    new_code = update_data.get("code", subject.code)
    new_department = update_data.get("department", subject.department)

    if new_code != subject.code or new_department != subject.department:
        existing = (
            db.query(Subject)
            .filter(
                Subject.code == new_code,
                Subject.department == new_department,
                Subject.id != subject_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Subject '{new_code}' already exists in department '{new_department}'"
            )

    for field, value in update_data.items():
        setattr(subject, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Subject '{new_code}' already exists in department '{new_department}'"
        )

    db.refresh(subject)
    return subject


def deactivate_subject(db: Session, subject_id: int) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise LookupError(f"Subject with id {subject_id} not found")

    subject.is_active = False
    db.commit()
    db.refresh(subject)
    return subject

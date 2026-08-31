from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate


def normalize_usn(usn: str) -> str:
    return usn.strip()


def create_student(db: Session, data: StudentCreate) -> Student:
    usn = normalize_usn(data.usn)
    existing = db.query(Student).filter(Student.usn == usn).first()
    if existing:
        raise ValueError(f"Student with USN '{usn}' already exists")

    student = Student(usn=usn, name=data.name.strip())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def get_student(db: Session, student_id: int) -> Student | None:
    return db.query(Student).filter(Student.id == student_id).first()


def get_student_by_usn(db: Session, usn: str) -> Student | None:
    return db.query(Student).filter(Student.usn == normalize_usn(usn)).first()


def list_students(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    include_inactive: bool = False,
) -> tuple[list[Student], int]:
    query = db.query(Student)

    if not include_inactive:
        query = query.filter(Student.is_active == True)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Student.usn.ilike(pattern),
                Student.name.ilike(pattern),
            )
        )

    total = query.count()
    students = (
        query.order_by(Student.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return students, total


def update_student(db: Session, student_id: int, data: StudentUpdate) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise LookupError(f"Student with id {student_id} not found")

    update_data = data.model_dump(exclude_unset=True)

    if "usn" in update_data and update_data["usn"] is not None:
        new_usn = normalize_usn(update_data["usn"])
        if new_usn != student.usn:
            existing = db.query(Student).filter(Student.usn == new_usn).first()
            if existing:
                raise ValueError(f"Student with USN '{new_usn}' already exists")
            update_data["usn"] = new_usn

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    for field, value in update_data.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student


def deactivate_student(db: Session, student_id: int) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise LookupError(f"Student with id {student_id} not found")

    student.is_active = False
    db.commit()
    db.refresh(student)
    return student

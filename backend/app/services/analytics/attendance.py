"""Attendance analytics service.

Read-only aggregation over AttendanceRecord and AttendanceEvent domain models.
All functions use SQL-level aggregation. No business logic mutations.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.attendance import (
    AttendanceRecord,
    AttendanceEvent,
    AttendanceStatus,
    AttendanceEventType,
)
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student


# ---------------------------------------------------------------------------
# 1. Expanded exam summary with additional breakdowns
# ---------------------------------------------------------------------------


def get_exam_summary(db: Session, exam_id: int) -> dict:
    """Get comprehensive attendance summary for an exam.

    Returns dict with total_registered, present, excused, absent (computed),
    attendance_rate, by_hall breakdown, by_status breakdown, and trends.

    Raises:
        LookupError: If exam not found.
    """
    _get_exam(db, exam_id)

    # Count registered students
    total_registered = (
        db.query(func.count(ExamRegistration.id))
        .filter(
            ExamRegistration.exam_id == exam_id,
            ExamRegistration.status == RegistrationStatus.REGISTERED.value,
        )
        .scalar()
    )

    # Count by attendance status
    total_present = (
        db.query(func.count(AttendanceRecord.id))
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT.value,
        )
        .scalar()
    )

    total_excused = (
        db.query(func.count(AttendanceRecord.id))
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.status == AttendanceStatus.EXCUSED.value,
        )
        .scalar()
    )

    total_absent = max(0, total_registered - total_present - total_excused)

    attendance_rate = (
        round((total_present + total_excused) / total_registered * 100, 1)
        if total_registered > 0
        else 0.0
    )

    # By-hall breakdown
    hall_rows = (
        db.query(
            AttendanceRecord.hall_id,
            func.count(AttendanceRecord.id).label("total"),
        )
        .filter(AttendanceRecord.exam_id == exam_id)
        .group_by(AttendanceRecord.hall_id)
        .all()
    )

    hall_present_rows = (
        db.query(
            AttendanceRecord.hall_id,
            func.count(AttendanceRecord.id).label("present"),
        )
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT.value,
        )
        .group_by(AttendanceRecord.hall_id)
        .all()
    )

    hall_present_map = {row.hall_id: row.present for row in hall_present_rows}

    by_hall = []
    for row in hall_rows:
        hall = db.query(ExamHall).filter(ExamHall.id == row.hall_id).first()
        by_hall.append({
            "hall_id": row.hall_id,
            "hall_name": f"{hall.building} {hall.room_number}" if hall else str(row.hall_id),
            "total": row.total,
            "present": hall_present_map.get(row.hall_id, 0),
        })

    # By-status breakdown
    status_rows = (
        db.query(
            AttendanceRecord.status,
            func.count(AttendanceRecord.id).label("count"),
        )
        .filter(AttendanceRecord.exam_id == exam_id)
        .group_by(AttendanceRecord.status)
        .all()
    )

    by_status = {}
    for row in status_rows:
        by_status[row.status] = row.count

    # Entry events for the exam (gate events related to attendance)
    entry_event_rows = (
        db.query(
            AttendanceEvent.event_type,
            func.count(AttendanceEvent.id).label("count"),
        )
        .filter(AttendanceEvent.exam_id == exam_id)
        .group_by(AttendanceEvent.event_type)
        .all()
    )

    by_event_type = {}
    for row in entry_event_rows:
        by_event_type[row.event_type] = row.count

    return {
        "exam_id": exam_id,
        "total_registered": total_registered,
        "total_present": total_present,
        "total_absent": total_absent,
        "total_excused": total_excused,
        "attendance_rate": attendance_rate,
        "by_hall": by_hall,
        "by_status": by_status,
        "by_event_type": by_event_type,
    }


# ---------------------------------------------------------------------------
# 2. List attendance records with filtering
# ---------------------------------------------------------------------------


def list_attendance(
    db: Session,
    exam_id: int,
    *,
    hall_id: int | None = None,
    status: str | None = None,
    student_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List attendance records for an exam with optional filters.

    Args:
        db: Database session.
        exam_id: Exam ID (required).
        hall_id: Optional hall filter.
        status: Optional status filter.
        student_id: Optional student filter.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size.
    """
    query = db.query(AttendanceRecord).filter(
        AttendanceRecord.exam_id == exam_id,
    )

    if hall_id is not None:
        query = query.filter(AttendanceRecord.hall_id == hall_id)
    if status is not None:
        query = query.filter(AttendanceRecord.status == status)
    if student_id is not None:
        query = query.filter(AttendanceRecord.student_id == student_id)

    total = query.count()
    items = (
        query.order_by(AttendanceRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# 3. Attendance by hall with utilization percentage
# ---------------------------------------------------------------------------


def list_attendance_by_hall(
    db: Session,
    exam_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List hall-level attendance with utilization percentage.

    Args:
        db: Database session.
        exam_id: Exam ID (required).
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size.
        Each item includes hall info, total seats, present count, utilization %.
    """
    # Hall enrollment from seat assignments
    hall_seats = (
        db.query(
            SeatAssignment.hall_id,
            func.count(SeatAssignment.id).label("total_seats"),
        )
        .filter(
            SeatAssignment.exam_id == exam_id,
        )
        .group_by(SeatAssignment.hall_id)
        .all()
    )

    # Hall present count from attendance records
    hall_present = (
        db.query(
            AttendanceRecord.hall_id,
            func.count(AttendanceRecord.id).label("present"),
        )
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT.value,
        )
        .group_by(AttendanceRecord.hall_id)
        .all()
    )

    hall_present_map = {row.hall_id: row.present for row in hall_present}

    by_hall = []
    for row in hall_seats:
        present = hall_present_map.get(row.hall_id, 0)
        utilization = round(present / row.total_seats * 100, 1) if row.total_seats > 0 else 0.0
        hall = db.query(ExamHall).filter(ExamHall.id == row.hall_id).first()
        by_hall.append({
            "hall_id": row.hall_id,
            "hall_name": f"{hall.building} {hall.room_number}" if hall else str(row.hall_id),
            "total_seats": row.total_seats,
            "present": present,
            "utilization_percent": utilization,
        })

    total = len(by_hall)
    return {
        "items": by_hall,
        "total": total,
        "page": 1,
        "page_size": total,
    }


# ---------------------------------------------------------------------------
# 4. Student attendance history across exams
# ---------------------------------------------------------------------------


def list_student_attendance_history(
    db: Session,
    student_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List attendance records for a student across all exams.

    Args:
        db: Database session.
        student_id: Student ID.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size.
    """
    _get_student(db, student_id)

    query = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student_id,
    )

    total = query.count()
    items = (
        query.order_by(AttendanceRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# 5. Excused attendance entries
# ---------------------------------------------------------------------------


def list_excused_attendance(
    db: Session,
    exam_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List excused attendance records for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID (required).
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size.
    """
    query = db.query(AttendanceRecord).filter(
        AttendanceRecord.exam_id == exam_id,
        AttendanceRecord.status == AttendanceStatus.EXCUSED.value,
    )

    total = query.count()
    items = (
        query.order_by(AttendanceRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# 5b. Attendance trend across dates (if timestamps available)
# ---------------------------------------------------------------------------


def attendance_timeline(
    db: Session,
    exam_id: int,
    *,
    days: int = 30,
) -> dict:
    """Build an attendance timeline for the last N days.

    Note: This uses entry_time from AttendanceRecord. If finer granularity
    is needed, query AttendanceEvent.created_at instead.

    Args:
        db: Database session.
        exam_id: Exam ID (required).
        days: Number of days to look back.

    Returns:
        Dict with daily attendance counts.
    """
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    daily_rows = (
        db.query(
            func.date(AttendanceRecord.entry_time).label("date"),
            func.count(AttendanceRecord.id).label("count"),
        )
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.entry_time >= cutoff,
        )
        .group_by(func.date(AttendanceRecord.entry_time))
        .order_by(func.date(AttendanceRecord.entry_time))
        .all()
    )

    by_day = {}
    for row in daily_rows:
        by_day[str(row.date)] = row.count

    return {
        "exam_id": exam_id,
        "timeline": by_day,
        "window_days": days,
    }


# ---------------------------------------------------------------------------
# 5c. Present/absent/excused counts by date
# ---------------------------------------------------------------------------


def attendance_status_timeline(
    db: Session,
    exam_id: int,
    *,
    days: int = 30,
) -> dict:
    """Breakdown of present/excused/absent counts by date.

    Args:
        db: Database session.
        exam_id: Exam ID (required).
        days: Number of days to look back.

    Returns:
        Dict with daily breakdown by status.
    """
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(
            func.date(AttendanceRecord.entry_time).label("date"),
            AttendanceRecord.status,
            func.count(AttendanceRecord.id).label("count"),
        )
        .filter(
            AttendanceRecord.exam_id == exam_id,
            AttendanceRecord.entry_time >= cutoff,
        )
        .group_by(func.date(AttendanceRecord.entry_time), AttendanceRecord.status)
        .order_by(func.date(AttendanceRecord.entry_time))
        .all()
    )

    by_day = {}
    for row in rows:
        date_str = str(row.date)
        if date_str not in by_day:
            by_day[date_str] = {"present": 0, "excused": 0, "absent": 0}
        by_day[date_str][row.status] = row.count

    return {
        "exam_id": exam_id,
        "timeline": by_day,
        "window_days": days,
    }


# ---------------------------------------------------------------------------
# 6. Export: attendance data as dict for reporting
# ---------------------------------------------------------------------------


def export_exam_attendance(
    db: Session,
    exam_id: int,
    *,
    status: str | None = None,
    hall_id: int | None = None,
) -> dict:
    """Export attendance records for an exam as a dict suitable for reporting.

    Args:
        db: Database session.
        exam_id: Exam ID (required).
        status: Optional status filter.
        hall_id: Optional hall filter.

    Returns:
        Dict with records list and summary counts.
    """
    query = db.query(AttendanceRecord).filter(AttendanceRecord.exam_id == exam_id)

    if status is not None:
        query = query.filter(AttendanceRecord.status == status)
    if hall_id is not None:
        query = query.filter(AttendanceRecord.hall_id == hall_id)

    records = query.order_by(AttendanceRecord.id).all()

    present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT.value)
    excused = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED.value)
    absent = sum(1 for r in records if r.status not in (
        AttendanceStatus.PRESENT.value,
        AttendanceStatus.EXCUSED.value,
    ))

    return {
        "exam_id": exam_id,
        "records": [
            {
                "id": r.id,
                "student_id": r.student_id,
                "exam_registration_id": r.exam_registration_id,
                "status": r.status,
                "entry_time": str(r.entry_time) if r.entry_time else None,
                "hall_id": r.hall_id,
                "seat_number": r.seat_number,
            }
            for r in records
        ],
        "summary": {
            "total": len(records),
            "present": present,
            "excused": excused,
            "absent": absent,
        },
    }
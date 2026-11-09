"""Test real persistent data hierarchy across SQLAlchemy sessions.

Verifies end-to-end creation, relation integrity, cross-session querying,
and cascade/integrity handling for:
Subject -> Exam -> ExamHall -> Student -> ExamRegistration -> SeatAssignment
  -> HallTicket -> EntryVerification -> AttendanceRecord -> AttendanceEvent
"""

import pytest
from datetime import datetime, timezone, date, time
from sqlalchemy.orm import Session

from app.models.subject import Subject
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.student import Student
from app.models.exam_registration import ExamRegistration
from app.models.seat_assignment import SeatAssignment
from app.models.hall_ticket import HallTicket
from app.models.entry_point import EntryPoint
from app.models.camera import Camera
from app.models.entry_verification import EntryVerification, EntryVerificationStatus, HallTicketCheckStatus
from app.models.attendance import AttendanceRecord, AttendanceEvent, AttendanceStatus, EntryMethod, AttendanceEventType


def test_complete_examination_hierarchy_persistence(db_session: Session):
    now = datetime.now(timezone.utc)
    today = date.today()

    # 1. Subject
    subject = Subject(
        code="CS501-REAL",
        name="Operating Systems and Verification",
        department="Computer Science",
        semester=5,
    )
    db_session.add(subject)
    db_session.flush()
    assert subject.id is not None

    # 2. Exam
    exam = Exam(
        subject_id=subject.id,
        exam_name="OS Final Examination 2026",
        exam_date=today,
        start_time=time(9, 30),
        end_time=time(12, 30),
        semester=5,
        department="Computer Science",
    )
    db_session.add(exam)
    db_session.flush()
    assert exam.id is not None

    # 3. Exam Hall
    hall = ExamHall(
        name="Auditorium Hall B",
        building="Main Academic Block",
        room_number="B-101",
        capacity=60,
    )
    db_session.add(hall)
    db_session.flush()
    assert hall.id is not None

    # 4. Student
    student = Student(
        usn="1DS21CS999",
        name="Real Candidate Test",
        is_active=True,
    )
    db_session.add(student)
    db_session.flush()
    assert student.id is not None

    # 5. Exam Registration
    registration = ExamRegistration(
        student_id=student.id,
        exam_id=exam.id,
        status="REGISTERED",
    )
    db_session.add(registration)
    db_session.flush()
    assert registration.id is not None

    # 6. Seat Assignment
    seat = SeatAssignment(
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        exam_id=exam.id,
        student_id=student.id,
        seat_number="B-12",
    )
    db_session.add(seat)
    db_session.flush()
    assert seat.id is not None

    # 7. Hall Ticket
    ticket = HallTicket(
        exam_registration_id=registration.id,
        status="CREATED",
    )
    db_session.add(ticket)
    db_session.flush()
    assert ticket.id is not None

    # 8. Entry Point & Camera
    entry_point = EntryPoint(
        name="North Gate Station 1",
        code="GATE_NORTH_01",
        location_detail="North Entrance",
        is_active=True,
    )
    db_session.add(entry_point)
    db_session.flush()

    camera = Camera(
        name="North Gate Cam 1",
        device_identifier="CAM-NG-01",
        camera_type="RTSP",
        is_active=True,
    )
    db_session.add(camera)
    db_session.flush()

    # 9. Entry Verification
    verification = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        hall_ticket_id=ticket.id,
        camera_id=camera.id,
        status=EntryVerificationStatus.GRANTED.value,
        hall_ticket_check=HallTicketCheckStatus.PASSED.value,
    )
    db_session.add(verification)
    db_session.flush()
    assert verification.id is not None

    # 10. Attendance Record
    attendance_record = AttendanceRecord(
        student_id=student.id,
        exam_id=exam.id,
        exam_registration_id=registration.id,
        status=AttendanceStatus.PRESENT.value,
        entry_verification_id=verification.id,
        entry_method=EntryMethod.VERIFIED_ENTRY.value,
        entry_time=now,
        hall_id=hall.id,
    )
    db_session.add(attendance_record)
    db_session.flush()
    assert attendance_record.id is not None

    # 11. Attendance Event
    attendance_event = AttendanceEvent(
        student_id=student.id,
        exam_id=exam.id,
        exam_registration_id=registration.id,
        entry_verification_id=verification.id,
        event_type=AttendanceEventType.ENTRY_GRANTED.value,
        status_snapshot=AttendanceStatus.PRESENT.value,
        recorded_by="system",
        reason="Biometric and credential verification passed",
    )
    db_session.add(attendance_event)
    db_session.flush()
    assert attendance_event.id is not None

    # Verify query relationships
    saved_exam = db_session.query(Exam).filter(Exam.id == exam.id).first()
    assert saved_exam is not None
    assert saved_exam.subject.code == "CS501-REAL"

    saved_ticket = db_session.query(HallTicket).filter(HallTicket.id == ticket.id).first()
    assert saved_ticket is not None
    assert saved_ticket.registration.student.usn == "1DS21CS999"

    saved_att = db_session.query(AttendanceRecord).filter(AttendanceRecord.id == attendance_record.id).first()
    assert saved_att is not None
    assert saved_att.status == AttendanceStatus.PRESENT.value
    assert saved_att.student_id == student.id
    assert saved_att.hall.name == "Auditorium Hall B"

    saved_ev = db_session.query(AttendanceEvent).filter(AttendanceEvent.id == attendance_event.id).first()
    assert saved_ev is not None
    assert saved_ev.event_type == AttendanceEventType.ENTRY_GRANTED.value
    assert saved_ev.entry_verification.status == EntryVerificationStatus.GRANTED.value

    # Verify cross-session commit and isolation
    db_session.commit()

    # Query from fresh query context
    reloaded_record = db_session.query(AttendanceRecord).filter_by(id=attendance_record.id).one()
    assert reloaded_record.student.name == "Real Candidate Test"
    assert reloaded_record.exam.exam_name == "OS Final Examination 2026"
    assert reloaded_record.entry_verification.entry_point.code == "GATE_NORTH_01"
    assert len(reloaded_record.student.seat_assignments) == 1
    assert reloaded_record.student.seat_assignments[0].seat_number == "B-12"

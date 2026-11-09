"""Verify real PostgreSQL persistence, dialect, and end-to-end data lifecycle."""

import os
import sys
from datetime import date, datetime, time, timezone

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

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

DB_URL = "postgresql://skandachandrashekar335@localhost:5432/examguard_test_real"

def run_verification():
    print(f"Connecting to real PostgreSQL at: {DB_URL}")
    engine = create_engine(DB_URL)
    
    # 1. Verify Dialect
    dialect_name = engine.dialect.name
    print(f"Dialect confirmed: {dialect_name}")
    assert dialect_name == "postgresql", f"Expected postgresql dialect, got {dialect_name}"
    
    with engine.connect() as conn:
        res = conn.execute(text("SELECT version(), current_database(), inet_server_addr(), inet_server_port();")).fetchone()
        print(f"PostgreSQL server version: {res[0]}")
        print(f"Connected Database: {res[1]}")
        print(f"Server host: {res[2]}:{res[3]}")
        
        # Verify Alembic Head
        alembic_rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        print(f"Alembic Current Revision: {alembic_rev}")
        assert alembic_rev == "031", f"Expected revision 031, got {alembic_rev}"

    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    
    now = datetime.now(timezone.utc)
    today = date.today()
    
    print("\n--- PHASE 1: Real Data Population ---")
    
    unique_suffix = int(now.timestamp()) % 100000
    test_usn = f"1DS22CS{unique_suffix:05d}"

    # 1. Create Subject
    subject = Subject(
        code=f"CS601-{unique_suffix}",
        name="Distributed Systems Architecture",
        department="Computer Science",
        semester=6,
    )
    session.add(subject)
    session.flush()
    print(f"[SQL INSERT] Subject created: id={subject.id}, code='{subject.code}'")
    
    # 2. Create Exam
    exam = Exam(
        subject_id=subject.id,
        exam_name=f"Distributed Systems Final Exam {unique_suffix}",
        exam_date=today,
        start_time=time(10, 0),
        end_time=time(13, 0),
        semester=6,
        department="Computer Science",
    )
    session.add(exam)
    session.flush()
    print(f"[SQL INSERT] Exam created: id={exam.id}, name='{exam.exam_name}'")
    
    # 3. Create Exam Hall
    hall = ExamHall(
        name=f"Turing Computational Hall {unique_suffix}",
        building="Sir M. Visvesvaraya Block",
        room_number=f"V-{unique_suffix % 900 + 100}",
        capacity=80,
    )
    session.add(hall)
    session.flush()
    print(f"[SQL INSERT] ExamHall created: id={hall.id}, room='{hall.room_number}'")
    
    # 4. Create Student
    student = Student(
        usn=test_usn,
        name="Real PostgreSQL Candidate",
        is_active=True,
    )
    session.add(student)
    session.flush()
    print(f"[SQL INSERT] Student registered: id={student.id}, usn='{student.usn}'")
    
    # 5. Create Exam Registration (Enrollment)
    registration = ExamRegistration(
        student_id=student.id,
        exam_id=exam.id,
        status="REGISTERED",
    )
    session.add(registration)
    session.flush()
    print(f"[SQL INSERT] ExamRegistration created: id={registration.id}, status='{registration.status}'")
    
    # 6. Create Seat Assignment
    seat = SeatAssignment(
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        exam_id=exam.id,
        student_id=student.id,
        seat_number="A-01",
    )
    session.add(seat)
    session.flush()
    print(f"[SQL INSERT] SeatAssignment created: id={seat.id}, seat='{seat.seat_number}'")
    
    # 7. Create Hall Ticket
    ticket = HallTicket(
        exam_registration_id=registration.id,
        status="CREATED",
    )
    session.add(ticket)
    session.flush()
    print(f"[SQL INSERT] HallTicket created: id={ticket.id}")
    
    # 8. Entry Point & Camera
    entry_point = EntryPoint(
        name=f"Main West Entrance {unique_suffix}",
        code=f"GATE_WEST_{unique_suffix}",
        location_detail="West Portal Gate 1",
        is_active=True,
    )
    session.add(entry_point)
    session.flush()
    
    camera = Camera(
        name=f"West Gate Camera {unique_suffix}",
        device_identifier=f"CAM-WEST-{unique_suffix}",
        camera_type="RTSP",
        is_active=True,
    )
    session.add(camera)
    session.flush()
    
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
    session.add(verification)
    session.flush()
    print(f"[SQL INSERT] EntryVerification recorded: id={verification.id}, status='{verification.status}'")
    
    # 10. Attendance Record
    attendance = AttendanceRecord(
        student_id=student.id,
        exam_id=exam.id,
        exam_registration_id=registration.id,
        status=AttendanceStatus.PRESENT.value,
        entry_verification_id=verification.id,
        entry_method=EntryMethod.VERIFIED_ENTRY.value,
        entry_time=now,
        hall_id=hall.id,
    )
    session.add(attendance)
    session.flush()
    print(f"[SQL INSERT] AttendanceRecord created: id={attendance.id}, status='{attendance.status}'")
    
    # 11. Attendance Event
    att_event = AttendanceEvent(
        student_id=student.id,
        exam_id=exam.id,
        exam_registration_id=registration.id,
        entry_verification_id=verification.id,
        event_type=AttendanceEventType.ENTRY_GRANTED.value,
        status_snapshot=AttendanceStatus.PRESENT.value,
        recorded_by="system",
        reason="Biometric identity match confirmed at Gate West 01",
    )
    session.add(att_event)
    session.flush()
    print(f"[SQL INSERT] AttendanceEvent appended: id={att_event.id}, type='{att_event.event_type}'")
    
    # COMMIT & CLOSE
    session.commit()
    session.close()
    engine.dispose()
    print("\nSession committed and closed. Engine disposed.")
    
    print("\n--- PHASE 2: Cross-Session Retrieval After Disconnect ---")
    new_engine = create_engine(DB_URL)
    NewSession = sessionmaker(bind=new_engine)
    new_session = NewSession()
    
    # Query with raw SQL to prove DB storage
    with new_engine.connect() as conn:
        row = conn.execute(text("""
            SELECT s.usn, s.name, e.exam_name, h.name as hall_name, sa.seat_number, ar.status, ar.entry_time
            FROM attendance_records ar
            JOIN students s ON s.id = ar.student_id
            JOIN exams e ON e.id = ar.exam_id
            JOIN exam_halls h ON h.id = ar.hall_id
            JOIN seat_assignments sa ON sa.student_id = s.id AND sa.exam_id = e.id
            WHERE s.usn = :usn
        """), {"usn": test_usn}).fetchone()
        
        print("\n[SQL SELECT Result from new connection]:")
        print(f"  USN:           {row[0]}")
        print(f"  Student Name:  {row[1]}")
        print(f"  Exam:          {row[2]}")
        print(f"  Hall:          {row[3]}")
        print(f"  Seat Number:   {row[4]}")
        print(f"  Status:        {row[5]}")
        print(f"  Entry Time:    {row[6]}")
        
        assert row[0] == test_usn
        assert row[1] == "Real PostgreSQL Candidate"
        assert row[4] == "A-01"
        assert row[5] == "PRESENT"
    
    # Also verify via ORM relationships in new session
    new_student = new_session.query(Student).filter_by(usn=test_usn).one()
    reloaded_att = new_session.query(AttendanceRecord).filter_by(student_id=new_student.id).first()
    assert reloaded_att is not None
    assert reloaded_att.student.usn == test_usn
    assert reloaded_att.hall.room_number.startswith("V-")
    
    reloaded_event = new_session.query(AttendanceEvent).filter_by(student_id=new_student.id).first()
    assert reloaded_event is not None
    assert reloaded_event.event_type == AttendanceEventType.ENTRY_GRANTED.value
    assert reloaded_event.entry_verification.status == EntryVerificationStatus.GRANTED.value
    
    print("\nORM relational hierarchy retrieval verified across new session.")
    new_session.close()
    new_engine.dispose()
    print("ALL REAL POSTGRESQL PERSISTENCE CHECKS PASSED.")

if __name__ == "__main__":
    run_verification()

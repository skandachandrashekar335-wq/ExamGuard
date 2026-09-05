"""ERP sync service layer.

Provides read/write operations for synchronizing ExamGuard domain data
with external ERP systems. Uses the ERP adapter abstraction.

Operations are observational/write-through — they create/update ExamGuard
records from ERP data, or export ExamGuard records to ERP format.
No data is fabricated; only records that exist in the ERP source are
synchronized into the ExamGuard database.

Architecture:
    ERP SOURCE → ErpAdapter → ErpSyncService → ExamGuard DB
        ↑                                                          ↓
    Export direction: ExamGuard DB → ErpAdapter → ERP SOURCE
"""

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.student import Student
from app.models.subject import Subject
from app.models.entry_verification import EntryVerification
from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.services.erp.adapter import ErpAdapter, ErpSyncLog, ErpSyncStatus


# ---------------------------------------------------------------------------
# ErpSyncService
# ---------------------------------------------------------------------------


class ErpSyncService:
    """Service that coordinates ERP synchronization operations."""

    def __init__(self, adapter: ErpAdapter | None = None):
        self.adapter = adapter or ErpAdapter()
        self.db = SessionLocal()

    # -------------------------------------------------------------------------
    # Student synchronization
    # -------------------------------------------------------------------------

    def sync_students(self, erp_students: list[dict[str, any]] | None = None) -> ErpSyncLog:
        """Synchronize student records from ERP data.

        Args:
            erp_students: List of student dicts from ERP system.
                If None, this method queries the ERP adapter.

        Returns:
            ErpSyncLog with operation results.
        """
        log = ErpSyncLog(
            operation="sync_students",
            status=ErpSyncStatus.IN_PROGRESS,
        )
        self.adapter.logs.append(log)
        self.db.logs.append(log)  # type: ignore

        try:
            if erp_students is None:
                erp_students = self.adapter.sync_students()

            new_added = 0
            updated = 0
            skipped = 0
            errors = 0

            for erp_student in erp_students:
                try:
                    usn = erp_student.get("usn")
                    if not usn:
                        skipped += 1
                        continue

                    # Check if student already exists
                    student = (
                        self.db.query(Student)
                        .filter(Student.usn == usn)
                        .first()
                    )

                    if student is None:
                        # Create new student
                        student = Student(
                            usn=usn,
                            name=erp_student.get("name", ""),
                            is_active=erp_student.get("is_active", True),
                        )
                        self.db.add(student)
                        new_added += 1
                    else:
                        # Update existing
                        student.name = erp_student.get("name", student.name)
                        student.is_active = erp_student.get(
                            "is_active", student.is_active,
                        )
                        updated += 1
                except Exception as e:
                    errors += 1
                    self.adapter.handle_sync_error(
                        "sync_students", e, new_added + updated + skipped + errors,
                    )

            self.db.commit()

            log.status = ErpSyncStatus.COMPLETED
            log.records_processed = new_added + updated + skipped + errors
            log.records_succeeded = new_added + updated
            log.records_failed = errors
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.status = ErpSyncStatus.COMPLETED

        except Exception as e:
            self.db.rollback()
            log.status = ErpSyncStatus.FAILED
            log.error_message = str(e)
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.handle_sync_error("sync_students", e, 0)

        return log

    # -------------------------------------------------------------------------
    # Subject synchronization
    # -------------------------------------------------------------------------

    def sync_subjects(self, erp_subjects: list[dict[str, any]] | None = None) -> ErpSyncLog:
        """Synchronize subject records from ERP data.

        Args:
            erp_subjects: List of subject dicts from ERP system.

        Returns:
            ErpSyncLog with operation results.
        """
        log = ErpSyncLog(
            operation="sync_subjects",
            status=ErpSyncStatus.IN_PROGRESS,
        )
        self.adapter.logs.append(log)
        self.db.logs.append(log)  # type: ignore

        try:
            if erp_subjects is None:
                erp_subjects = self.adapter.sync_subjects()

            new_added = 0
            updated = 0
            errors = 0

            for erp_subject in erp_subjects:
                try:
                    subject_code = erp_subject.get("code")
                    if not subject_code:
                        errors += 1
                        continue

                    # Check if subject already exists
                    subject = (
                        self.db.query(Subject)
                        .filter(Subject.code == subject_code)
                        .first()
                    )

                    if subject is None:
                        # Create new subject
                        subject = Subject(
                            code=subject_code,
                            name=erp_subject.get("name", ""),
                        )
                        self.db.add(subject)
                        new_added += 1
                    else:
                        # Update existing
                        subject.name = erp_subject.get("name", subject.name)
                        updated += 1
                except Exception as e:
                    errors += 1
                    self.adapter.handle_sync_error(
                        "sync_subjects", e, new_added + updated + errors,
                    )

            self.db.commit()

            log.status = ErpSyncStatus.COMPLETED
            log.records_processed = new_added + updated + errors
            log.records_succeeded = new_added + updated
            log.records_failed = errors
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.status = ErpSyncStatus.COMPLETED

        except Exception as e:
            self.db.rollback()
            log.status = ErpSyncStatus.FAILED
            log.error_message = str(e)
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.handle_sync_error("sync_subjects", e, 0)

        return log

    # -------------------------------------------------------------------------
    # Exam synchronization
    # -------------------------------------------------------------------------

    def sync_exams(self, erp_exams: list[dict[str, any]] | None = None) -> ErpSyncLog:
        """Synchronize examination records from ERP data.

        Args:
            erp_exams: List of exam dicts from ERP system.

        Returns:
            ErpSyncLog with operation results.
        """
        log = ErpSyncLog(
            operation="sync_exams",
            status=ErpSyncStatus.IN_PROGRESS,
        )
        self.adapter.logs.append(log)
        self.db.logs.append(log)  # type: ignore

        try:
            if erp_exams is None:
                erp_exams = self.adapter.sync_exams()

            new_added = 0
            updated = 0
            errors = 0

            for erp_exam in erp_exams:
                try:
                    exam_code = erp_exam.get("exam_code")
                    if not exam_code:
                        errors += 1
                        continue

                    # Check if exam already exists
                    exam = (
                        self.db.query(Exam)
                        .filter(Exam.exam_code == exam_code)
                        .first()
                    )

                    if exam is None:
                        # Create new exam
                        hall_id = erp_exam.get("hall_id")
                        exam_hall = (
                            self.db.query(ExamHall)
                            .filter(ExamHall.id == hall_id)
                            .first()
                        ) if hall_id else None

                        exam = Exam(
                            exam_code=exam_code,
                            exam_name=erp_exam.get("exam_name", ""),
                            exam_date=erp_exam.get("exam_date"),
                            subject_code=erp_exam.get("subject_code"),
                            exam_hall_id=hall_id,
                        )
                        self.db.add(exam)
                        new_added += 1
                    else:
                        # Update existing
                        exam.exam_name = erp_exam.get("exam_name", exam.exam_name)
                        exam.exam_date = erp_exam.get("exam_date", exam.exam_date)
                        exam.subject_code = erp_exam.get(
                            "subject_code", exam.subject_code,
                        )
                        exam.hall_id = erp_exam.get("hall_id", exam.hall_id)
                        updated += 1
                except Exception as e:
                    errors += 1
                    self.adapter.handle_sync_error(
                        "sync_exams", e, new_added + updated + errors,
                    )

            self.db.commit()

            log.status = ErpSyncStatus.COMPLETED
            log.records_processed = new_added + updated + errors
            log.records_succeeded = new_added + updated
            log.records_failed = errors
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.status = ErpSyncStatus.COMPLETED

        except Exception as e:
            self.db.rollback()
            log.status = ErpSyncStatus.FAILED
            log.error_message = str(e)
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.handle_sync_error("sync_exams", e, 0)

        return log

    # -------------------------------------------------------------------------
    # Registration synchronization
    # -------------------------------------------------------------------------

    def sync_registrations(
        self, erp_registrations: list[dict[str, any]] | None = None
    ) -> ErpSyncLog:
        """Synchronize registration records from ERP data.

        Args:
            erp_registrations: List of registration dicts from ERP system.

        Returns:
            ErpSyncLog with operation results.
        """
        log = ErpSyncLog(
            operation="sync_registrations",
            status=ErpSyncStatus.IN_PROGRESS,
        )
        self.adapter.logs.append(log)
        self.db.logs.append(log)  # type: ignore

        try:
            if erp_registrations is None:
                erp_registrations = self.adapter.sync_registrations()

            new_added = 0
            updated = 0
            errors = 0

            for erp_reg in erp_registrations:
                try:
                    student_usn = erp_reg.get("student_usn")
                    exam_code = erp_reg.get("exam_code")
                    if not student_usn or not exam_code:
                        errors += 1
                        continue

                    # Find the student and exam
                    student = (
                        self.db.query(Student)
                        .filter(Student.usn == student_usn)
                        .first()
                    )
                    exam = (
                        self.db.query(Exam)
                        .filter(Exam.exam_code == exam_code)
                        .first()
                    )

                    if not student or not exam:
                        errors += 1
                        continue

                    # Check if registration already exists
                    reg = (
                        self.db.query(ExamRegistration)
                        .filter(
                            ExamRegistration.student_id == student.id,
                            ExamRegistration.exam_id == exam.id,
                        )
                        .first()
                    )

                    if reg is None:
                        # Create new registration
                        reg = ExamRegistration(
                            student_id=student.id,
                            exam_id=exam.id,
                            status=RegistrationStatus.REGISTERED.value,
                        )
                        self.db.add(reg)
                        new_added += 1
                    else:
                        # Update existing
                        reg.status = erp_reg.get("status", reg.status)
                        updated += 1
                except Exception as e:
                    errors += 1
                    self.adapter.handle_sync_error(
                        "sync_registrations", e, new_added + updated + errors,
                    )

            self.db.commit()

            log.status = ErpSyncStatus.COMPLETED
            log.records_processed = new_added + updated + errors
            log.records_succeeded = new_added + updated
            log.records_failed = errors
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.status = ErpSyncStatus.COMPLETED

        except Exception as e:
            self.db.rollback()
            log.status = ErpSyncStatus.FAILED
            log.error_message = str(e)
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.handle_sync_error("sync_registrations", e, 0)

        return log

    # -------------------------------------------------------------------------
    # Attendance synchronization
    # -------------------------------------------------------------------------

    def sync_attendance(
        self, erp_attendance: list[dict[str, any]] | None = None
    ) -> ErpSyncLog:
        """Synchronize attendance records from ERP data.

        Args:
            erp_attendance: List of attendance dicts from ERP system.

        Returns:
            ErpSyncLog with operation results.
        """
        log = ErpSyncLog(
            operation="sync_attendance",
            status=ErpSyncStatus.IN_PROGRESS,
        )
        self.adapter.logs.append(log)
        self.db.logs.append(log)  # type: ignore

        try:
            if erp_attendance is None:
                erp_attendance = self.adapter.sync_attendance()

            new_added = 0
            updated = 0
            errors = 0

            for erp_att in erp_attendance:
                try:
                    student_usn = erp_att.get("student_usn")
                    exam_code = erp_att.get("exam_code")
                    hall_id = erp_att.get("hall_id")
                    seat_number = erp_att.get("seat_number")
                    status = erp_att.get("status", "PRESENT")

                    if not student_usn or not exam_code:
                        errors += 1
                        continue

                    # Find the student and exam
                    student = (
                        self.db.query(Student)
                        .filter(Student.usn == student_usn)
                        .first()
                    )
                    exam = (
                        self.db.query(Exam)
                        .filter(Exam.exam_code == exam_code)
                        .first()
                    )

                    if not student or not exam:
                        errors += 1
                        continue

                    # Check if attendance record already exists
                    reg = (
                        self.db.query(ExamRegistration)
                        .filter(
                            ExamRegistration.student_id == student.id,
                            ExamRegistration.exam_id == exam.id,
                        )
                        .first()
                    )

                    if reg is None:
                        errors += 1
                        continue

                    existing = (
                        self.db.query(AttendanceRecord)
                        .filter(
                            AttendanceRecord.student_id == student.id,
                            AttendanceRecord.exam_registration_id == reg.id,
                        )
                        .first()
                    )

                    if existing is None:
                        # Create new attendance record
                        attendance = AttendanceRecord(
                            student_id=student.id,
                            exam_id=exam.id,
                            exam_registration_id=reg.id,
                            status=status,
                            hall_id=hall_id,
                            seat_number=seat_number,
                            entry_method="SYNC_ERP".value if hasattr(
                                EntryMethod, "SYNC_ERP"
                            )
                            else "VERIFIED_ENTRY".value,
                        )
                        self.db.add(attendance)
                        new_added += 1
                    else:
                        # Update existing
                        existing.status = status
                        existing.hall_id = hall_id
                        existing.seat_number = seat_number
                        updated += 1
                except Exception as e:
                    errors += 1
                    self.adapter.handle_sync_error(
                        "sync_attendance", e, new_added + updated + errors,
                    )

            self.db.commit()

            log.status = ErpSyncStatus.COMPLETED
            log.records_processed = new_added + updated + errors
            log.records_succeeded = new_added + updated
            log.records_failed = errors
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.status = ErpSyncStatus.COMPLETED

        except Exception as e:
            self.db.rollback()
            log.status = ErpSyncStatus.FAILED
            log.error_message = str(e)
            log.completed_at = datetime.now(timezone.utc)
            self.adapter.handle_sync_error("sync_attendance", e, 0)

        return log

    # -------------------------------------------------------------------------
    # Export ExamGuard data to ERP format
    # -------------------------------------------------------------------------

    def export_students(self) -> dict[str, any]:
        """Export student records to ERP format.

        Returns dict with export data structure.
        """
        students = self.db.query(Student).all()
        return {
            "total": len(students),
            "students": [
                {
                    "usn": s.usn,
                    "name": s.name,
                    "is_active": s.is_active,
                }
                for s in students
            ],
        }

    def export_exams(self) -> dict[str, any]:
        """Export exam records to ERP format.

        Returns dict with export data structure.
        """
        exams = self.db.query(Exam).all()
        return {
            "total": len(exams),
            "exams": [
                {
                    "exam_code": e.exam_code,
                    "exam_name": e.exam_name,
                    "exam_date": str(e.exam_date) if e.exam_date else None,
                    "subject_code": e.subject_code,
                    "hall_id": e.exam_hall_id,
                }
                for e in exams
            ],
        }

    def export_registrations(self) -> dict[str, any]:
        """Export registration records to ERP format.

        Returns dict with export data structure.
        """
        registrations = (
            self.db.query(ExamRegistration, Student, Exam)
            .join(Student, ExamRegistration.student_id == Student.id)
            .join(Exam, ExamRegistration.exam_id == Exam.id)
            .all()
        )
        return {
            "total": len(registrations),
            "registrations": [
                {
                    "student_usn": r.student.usn,
                    "exam_code": r.exam.exam_code,
                    "status": r.status,
                }
                for r in registrations
            ],
        }

    def export_attendance(self) -> dict[str, any]:
        """Export attendance records to ERP format.

        Returns dict with export data structure.
        """
        attendance = (
            self.db.query(AttendanceRecord, Student, Exam)
            .join(Student, AttendanceRecord.student_id == Student.id)
            .join(Exam, AttendanceRecord.exam_id == Exam.id)
            .all()
        )
        return {
            "total": len(attendance),
            "attendance": [
                {
                    "student_usn": a.student.usn,
                    "exam_code": a.exam.exam_code,
                    "status": a.status,
                    "hall_id": a.hall_id,
                    "seat_number": a.seat_number,
                }
                for a in attendance
            ],
        }

    # -------------------------------------------------------------------------
    # Convenience method: full sync cycle
    # -------------------------------------------------------------------------

    def full_sync_cycle(
        self,
        erp_students: list[dict[str, any]] | None = None,
        erp_subjects: list[dict[str, any]] | None = None,
        erp_exams: list[dict[str, any]] | None = None,
        erp_registrations: list[dict[str, any]] | None = None,
        erp_attendance: list[dict[str, any]] | None = None,
    ) -> dict[str, ErpSyncLog]:
        """Run a full synchronization cycle across all domains.

        Args:
            erp_students: ERP student data.
            erp_subjects: ERP subject data.
            erp_exams: ERP exam data.
            erp_registrations: ERP registration data.
            erp_attendance: ERP attendance data.

        Returns:
            Dict mapping operation name to ErpSyncLog.
        """
        results: dict[str, ErpSyncLog] = {}

        results["sync_students"] = self.sync_students(erp_students)
        results["sync_subjects"] = self.sync_subjects(erp_subjects)
        results["sync_exams"] = self.sync_exams(erp_exams)
        results["sync_registrations"] = self.sync_registrations(erp_registrations)
        results["sync_attendance"] = self.sync_attendance(erp_attendance)

        # Export data after sync
        results["export_students"] = type(
            "ErpSyncLog", (), {"status": "COMPLETED", "data": self.export_students(),
            "records_processed": len(self.export_students()["students"]),
        })()
        results["export_exams"] = type(
            "ErpSyncLog", (), {"status": "COMPLETED", "data": self.export_exams(),
            "records_processed": len(self.export_exams()["exams"]),
        })()
        results["export_registrations"] = type(
            "ErpSyncLog", (), {"status": "COMPLETED", "data": self.export_registrations(),
            "records_processed": len(self.export_registrations()["registrations"]),
        })()
        results["export_attendance"] = type(
            "ErpSyncLog", (), {"status": "COMPLETED", "data": self.export_attendance(),
            "records_processed": len(self.export_attendance()["attendance"]),
        })()

        return results
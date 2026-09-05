import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"


class EntryMethod(str, enum.Enum):
    VERIFIED_ENTRY = "VERIFIED_ENTRY"
    MANUAL_ENTRY = "MANUAL_ENTRY"


class AttendanceEventType(str, enum.Enum):
    ENTRY_GRANTED = "ENTRY_GRANTED"
    ENTRY_DENIED = "ENTRY_DENIED"
    ENTRY_ESCALATED = "ENTRY_ESCALATED"
    ATTENDANCE_RECORDED = "ATTENDANCE_RECORDED"
    ATTENDANCE_CORRECTED = "ATTENDANCE_CORRECTED"
    ATTENDANCE_EXCUSED = "ATTENDANCE_EXCUSED"


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "exam_registration_id",
            name="uq_attendance_record_per_registration",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
        comment="Student this attendance record is for",
    )
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False,
        index=True,
        comment="Exam this attendance record is for",
    )
    exam_registration_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_registrations.id"),
        nullable=False,
        index=True,
        comment="Exam registration this attendance record is for",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=AttendanceStatus.PRESENT.value,
        index=True,
        comment="Current attendance status",
    )
    entry_verification_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entry_verifications.id"),
        nullable=False,
        index=True,
        comment="Entry verification that established this attendance",
    )
    entry_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=EntryMethod.VERIFIED_ENTRY.value,
        comment="How attendance was recorded: VERIFIED_ENTRY or MANUAL_ENTRY",
    )
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the student entered (from EV created_at or manual override)",
    )
    hall_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=False,
        index=True,
        comment="Exam hall where student entered (snapshot at entry time)",
    )
    seat_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Seat number (snapshot from SeatAssignment at entry time)",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this attendance record was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["Student"] = relationship()  # noqa: F821
    exam: Mapped["Exam"] = relationship()  # noqa: F821
    registration: Mapped["ExamRegistration"] = relationship()  # noqa: F821
    entry_verification: Mapped["EntryVerification"] = relationship()  # noqa: F821
    hall: Mapped["ExamHall"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<AttendanceRecord id={self.id} "
            f"student_id={self.student_id} "
            f"exam_id={self.exam_id} "
            f"status={self.status!r}>"
        )


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
        comment="Student this event is for",
    )
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False,
        index=True,
        comment="Exam this event is for",
    )
    exam_registration_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_registrations.id"),
        nullable=False,
        index=True,
        comment="Exam registration this event is for",
    )
    entry_verification_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entry_verifications.id"),
        nullable=False,
        index=True,
        comment="Entry verification that triggered this event",
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of attendance event",
    )
    status_snapshot: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="AttendanceRecord.status after this event (or N/A for denied/escalated)",
    )
    recorded_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="system for automated, admin identifier for manual corrections",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for correction or excuse",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When this event was recorded",
    )

    student: Mapped["Student"] = relationship()  # noqa: F821
    exam: Mapped["Exam"] = relationship()  # noqa: F821
    registration: Mapped["ExamRegistration"] = relationship()  # noqa: F821
    entry_verification: Mapped["EntryVerification"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<AttendanceEvent id={self.id} "
            f"student_id={self.student_id} "
            f"exam_id={self.exam_id} "
            f"event_type={self.event_type!r}>"
        )

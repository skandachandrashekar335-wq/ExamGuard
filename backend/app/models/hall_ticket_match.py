import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class MatchStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NOT_FOUND = "NOT_FOUND"
    MISMATCH = "MISMATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class MatchSignalType(str, enum.Enum):
    STUDENT_USN = "student_usn"
    STUDENT_NAME = "student_name"
    EXAM_NAME = "exam_name"
    SUBJECT = "subject"
    EXAM_DATE = "exam_date"
    START_TIME = "start_time"
    EXAM_HALL = "exam_hall"
    SEAT_NUMBER = "seat_number"
    REGISTRATION = "registration"


class HallTicketMatchResult(Base):
    __tablename__ = "hall_ticket_match_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )
    extraction_result_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("extraction_results.id"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=True,
        index=True,
    )
    exam_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=True,
        index=True,
    )
    registration_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("exam_registrations.id"),
        nullable=True,
        index=True,
    )
    seat_assignment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("seat_assignments.id"),
        nullable=True,
        index=True,
    )
    overall_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    document: Mapped["Document"] = relationship()  # noqa: F821
    extraction_result: Mapped["ExtractionResult"] = relationship()  # noqa: F821
    student: Mapped["Student"] = relationship()  # noqa: F821
    exam: Mapped["Exam"] = relationship()  # noqa: F821
    registration: Mapped["ExamRegistration"] = relationship()  # noqa: F821
    seat_assignment: Mapped["SeatAssignment"] = relationship()  # noqa: F821
    signals: Mapped[list["HallTicketMatchSignal"]] = relationship(
        back_populates="match_result",
    )

    def __repr__(self) -> str:
        return (
            f"<HallTicketMatchResult id={self.id} "
            f"status={self.overall_status!r}>"
        )


class HallTicketMatchSignal(Base):
    __tablename__ = "hall_ticket_match_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_result_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hall_ticket_match_results.id"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    extracted_value: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    expected_value: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    matched: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    signal_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    match_result: Mapped["HallTicketMatchResult"] = relationship(
        back_populates="signals",
    )

    def __repr__(self) -> str:
        return (
            f"<HallTicketMatchSignal id={self.id} "
            f"field={self.field_name!r} matched={self.matched!r}>"
        )

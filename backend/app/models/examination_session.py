"""Examination session and gate event models (Phase 15).

An ExaminationSession represents a running exam in a specific hall.
It links an Exam to an ExamHall and tracks the session lifecycle
from NOT_STARTED through IN_PROGRESS to COMPLETED/CANCELLED.

GateEvent records each gate open/close transition within a session.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class SessionStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class GateStatus(str, enum.Enum):
    GATES_CLOSED = "GATES_CLOSED"
    GATES_OPEN = "GATES_OPEN"


# Allowed status transitions
SESSION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    SessionStatus.NOT_STARTED.value: {
        SessionStatus.IN_PROGRESS.value,
        SessionStatus.CANCELLED.value,
    },
    SessionStatus.IN_PROGRESS.value: {
        SessionStatus.COMPLETED.value,
        SessionStatus.CANCELLED.value,
    },
    SessionStatus.COMPLETED.value: set(),
    SessionStatus.CANCELLED.value: set(),
}


class ExaminationSession(Base):
    __tablename__ = "examination_sessions"
    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "exam_hall_id",
            name="uq_session_exam_hall",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False,
        index=True,
        comment="Exam this session is for",
    )
    exam_hall_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=False,
        index=True,
        comment="Hall where this session takes place",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=SessionStatus.NOT_STARTED.value,
        index=True,
        comment="Session lifecycle status",
    )
    gate_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=GateStatus.GATES_CLOSED.value,
        comment="Current gate status for this session",
    )
    gate_open_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When gates were opened",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the session officially started",
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the session ended",
    )
    expected_capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Expected number of students for this session",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes about this session",
    )
    created_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Who created this session",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    exam: Mapped["Exam"] = relationship()  # noqa: F821
    hall: Mapped["ExamHall"] = relationship()  # noqa: F821
    gate_events: Mapped[list["GateEvent"]] = relationship(
        back_populates="session",
        order_by="GateEvent.created_at",
    )
    entry_verifications: Mapped[list["EntryVerification"]] = relationship(  # noqa: F821
        back_populates="session",
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(  # noqa: F821
        back_populates="session",
    )

    def __repr__(self) -> str:
        return (
            f"<ExaminationSession id={self.id} "
            f"exam_id={self.exam_id} "
            f"hall_id={self.exam_hall_id} "
            f"status={self.status!r}>"
        )


class GateEvent(Base):
    __tablename__ = "gate_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("examination_sessions.id"),
        nullable=False,
        index=True,
        comment="Session this gate event belongs to",
    )
    previous_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Gate status before this change",
    )
    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Gate status after this change",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for the gate status change",
    )
    performed_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Who performed this gate operation",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    session: Mapped["ExaminationSession"] = relationship(back_populates="gate_events")

    def __repr__(self) -> str:
        return (
            f"<GateEvent id={self.id} "
            f"session_id={self.session_id} "
            f"{self.previous_status!r} → {self.new_status!r}>"
        )

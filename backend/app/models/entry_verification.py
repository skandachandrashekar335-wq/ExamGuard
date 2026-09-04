import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class EntryVerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"


class HallTicketCheckStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class IdentityCheckStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class SeatCheckStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


ENTRY_VERIFICATION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    EntryVerificationStatus.PENDING.value: {
        EntryVerificationStatus.IN_PROGRESS.value,
        EntryVerificationStatus.DENIED.value,
        EntryVerificationStatus.ESCALATED.value,
    },
    EntryVerificationStatus.IN_PROGRESS.value: {
        EntryVerificationStatus.GRANTED.value,
        EntryVerificationStatus.DENIED.value,
        EntryVerificationStatus.ESCALATED.value,
    },
    EntryVerificationStatus.ESCALATED.value: {
        EntryVerificationStatus.GRANTED.value,
        EntryVerificationStatus.DENIED.value,
    },
    EntryVerificationStatus.GRANTED.value: set(),
    EntryVerificationStatus.DENIED.value: set(),
}


class EntryVerification(Base):
    __tablename__ = "entry_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
        comment="Student attempting entry",
    )
    exam_registration_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_registrations.id"),
        nullable=False,
        index=True,
        comment="Registration this entry attempt is for",
    )
    exam_hall_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=False,
        index=True,
        comment="Exam hall the student is attempting to enter",
    )
    entry_point_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entry_points.id"),
        nullable=False,
        index=True,
        comment="Physical entry point where student arrived",
    )
    hall_ticket_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("hall_tickets.id"),
        nullable=True,
        index=True,
        comment="Hall ticket being verified (nullable until linked)",
    )
    identity_verification_attempt_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("identity_verification_attempts.id"),
        nullable=True,
        index=True,
        comment="Identity verification attempt created for this entry (nullable until linked)",
    )
    camera_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cameras.id"),
        nullable=True,
        index=True,
        comment="Camera that observed the entry (nullable if not yet linked)",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=EntryVerificationStatus.PENDING.value,
        index=True,
        comment="Lifecycle status of this entry verification",
    )
    hall_ticket_check: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=HallTicketCheckStatus.PENDING.value,
        comment="Hall ticket verification result",
    )
    identity_check: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=IdentityCheckStatus.PENDING.value,
        comment="Identity verification result",
    )
    seat_check: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=SeatCheckStatus.PENDING.value,
        comment="Seat assignment verification result",
    )
    escalation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for human review escalation",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When escalation was resolved (GRANTED or DENIED from ESCALATED)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When the entry verification was initiated",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["Student"] = relationship()  # noqa: F821
    exam_registration: Mapped["ExamRegistration"] = relationship()  # noqa: F821
    exam_hall: Mapped["ExamHall"] = relationship()  # noqa: F821
    entry_point: Mapped["EntryPoint"] = relationship()  # noqa: F821
    hall_ticket: Mapped["HallTicket | None"] = relationship()  # noqa: F821
    identity_verification_attempt: Mapped["IdentityVerificationAttempt | None"] = relationship()  # noqa: F821
    camera: Mapped["Camera | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<EntryVerification id={self.id} "
            f"student_id={self.student_id} "
            f"status={self.status!r} "
            f"entry_point_id={self.entry_point_id}>"
        )

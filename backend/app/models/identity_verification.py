import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class IdentityVerificationStatus(str, enum.Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IdentityVerificationMethod(str, enum.Enum):
    FACE = "FACE"
    MANUAL = "MANUAL"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"


class IdentityVerificationDecision(str, enum.Enum):
    PENDING = "PENDING"
    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    INCONCLUSIVE = "INCONCLUSIVE"


STATUS_TRANSITIONS: dict[str, set[str]] = {
    IdentityVerificationStatus.CREATED.value: {
        IdentityVerificationStatus.IN_PROGRESS.value,
        IdentityVerificationStatus.COMPLETED.value,
        IdentityVerificationStatus.FAILED.value,
        IdentityVerificationStatus.CANCELLED.value,
    },
    IdentityVerificationStatus.IN_PROGRESS.value: {
        IdentityVerificationStatus.COMPLETED.value,
        IdentityVerificationStatus.FAILED.value,
        IdentityVerificationStatus.CANCELLED.value,
    },
    IdentityVerificationStatus.COMPLETED.value: set(),
    IdentityVerificationStatus.FAILED.value: set(),
    IdentityVerificationStatus.CANCELLED.value: set(),
}


class IdentityVerificationAttempt(Base):
    __tablename__ = "identity_verification_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    exam_registration_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_registrations.id"),
        nullable=False,
        index=True,
    )
    hall_ticket_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("hall_tickets.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=IdentityVerificationStatus.CREATED.value,
        index=True,
    )
    verification_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=IdentityVerificationMethod.MANUAL.value,
    )
    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=IdentityVerificationDecision.PENDING.value,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    student: Mapped["Student"] = relationship()  # noqa: F821
    exam_registration: Mapped["ExamRegistration"] = relationship()  # noqa: F821
    hall_ticket: Mapped["HallTicket | None"] = relationship()  # noqa: F821
    evidence_records: Mapped[list["IdentityVerificationEvidence"]] = relationship(
        back_populates="attempt",
        order_by="IdentityVerificationEvidence.id",
    )

    def __repr__(self) -> str:
        return (
            f"<IdentityVerificationAttempt id={self.id} "
            f"student_id={self.student_id} "
            f"status={self.status!r} "
            f"decision={self.decision!r}>"
        )


class IdentityVerificationEvidence(Base):
    __tablename__ = "identity_verification_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("identity_verification_attempts.id"),
        nullable=False,
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Type of evidence signal (e.g. similarity_score, liveness, quality)",
    )
    signal_value: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Numeric or categorical value of the signal",
    )
    provider_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Name of the AI/provider that produced this evidence",
    )
    provider_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Version of the provider",
    )
    confidence: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Provider-reported confidence for this signal",
    )
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional details or metadata about this evidence",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    attempt: Mapped["IdentityVerificationAttempt"] = relationship(
        back_populates="evidence_records",
    )

    def __repr__(self) -> str:
        return (
            f"<IdentityVerificationEvidence id={self.id} "
            f"attempt_id={self.attempt_id} "
            f"signal_type={self.signal_type!r}>"
        )

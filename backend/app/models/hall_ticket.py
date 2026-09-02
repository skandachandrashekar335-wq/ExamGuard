import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class HallTicketStatus(str, enum.Enum):
    CREATED = "CREATED"
    EXTRACTED = "EXTRACTED"
    MATCHED = "MATCHED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class HallTicket(Base):
    __tablename__ = "hall_tickets"
    __table_args__ = (
        UniqueConstraint(
            "exam_registration_id",
            name="uq_hall_ticket_active_per_registration",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_registration_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_registrations.id"),
        nullable=False,
        index=True,
        comment="The exam registration this hall ticket is for",
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("documents.id"),
        nullable=True,
        index=True,
        comment="Source hall-ticket document (set after upload)",
    )
    extraction_result_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("extraction_results.id"),
        nullable=True,
        index=True,
        comment="OCR extraction result (set after processing)",
    )
    match_result_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("hall_ticket_match_results.id"),
        nullable=True,
        index=True,
        comment="Matching result against domain records (set after matching)",
    )
    verification_outcome_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("verification_outcomes.id"),
        nullable=True,
        index=True,
        comment="Final verification decision (set after verification)",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=HallTicketStatus.CREATED.value,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason if hall ticket was rejected",
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

    registration: Mapped["ExamRegistration"] = relationship(
        back_populates="hall_ticket",
    )
    document: Mapped["Document | None"] = relationship()  # noqa: F821
    extraction_result: Mapped["ExtractionResult | None"] = relationship()  # noqa: F821
    match_result: Mapped["HallTicketMatchResult | None"] = relationship()  # noqa: F821
    verification_outcome: Mapped["VerificationOutcome | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<HallTicket id={self.id} "
            f"reg_id={self.exam_registration_id} "
            f"status={self.status!r}>"
        )

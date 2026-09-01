import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class VerificationDecision(str, enum.Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INCOMPLETE = "INCOMPLETE"


class VerificationOutcome(Base):
    __tablename__ = "verification_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )
    extraction_result_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("extraction_results.id"),
        nullable=True,
        index=True,
    )
    match_result_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("hall_ticket_match_results.id"),
        nullable=True,
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
    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    extraction_check: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )
    match_check: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )
    review_check: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )
    ocr_avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["Document"] = relationship()  # noqa: F821
    extraction_result: Mapped["ExtractionResult | None"] = relationship()  # noqa: F821
    match_result: Mapped["HallTicketMatchResult | None"] = relationship()  # noqa: F821
    student: Mapped["Student | None"] = relationship()  # noqa: F821
    exam: Mapped["Exam | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<VerificationOutcome id={self.id} "
            f"decision={self.decision!r}>"
        )

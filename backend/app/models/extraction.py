import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ReviewStatus(str, enum.Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWED = "REVIEWED"


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    ocr_avg_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ExtractionStatus] = mapped_column(
        String(50),
        nullable=False,
        server_default=ExtractionStatus.PENDING.value,
        index=True,
    )
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    extraction_result_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("extraction_results.id"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extracted_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    pattern_match: Mapped[bool | None] = mapped_column(nullable=True)
    label_found: Mapped[bool | None] = mapped_column(nullable=True)
    database_match: Mapped[bool | None] = mapped_column(nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNCERTAIN")
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=ReviewStatus.REVIEW_REQUIRED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

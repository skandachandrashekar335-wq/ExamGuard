from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class KnowledgeBaseItem(Base):
    __tablename__ = "knowledge_base_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Category: COURSES, ADMISSIONS, ELIGIBILITY, FEES, DOCUMENTS, EXAMINATIONS, TIMETABLES, FACILITIES, GENERAL"
    )
    intent: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="Canonical intent identifier, e.g., fees_btech_payment"
    )
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="Comma-separated keywords and phrases for NLP matching"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true(),
        comment="True if grounded in verified college policy"
    )
    requires_admin_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
        comment="Flag indicating student should confirm specific details with admin"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true(), index=True,
        comment="Soft-delete flag"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseItem id={self.id} category={self.category!r} intent={self.intent!r}>"


class ChatQueryLog(Base):
    __tablename__ = "chat_query_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(String(500), nullable=False)
    matched_intent: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ChatQueryLog id={self.id} category={self.category!r} confidence={self.confidence:.2f}>"

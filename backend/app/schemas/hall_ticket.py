from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HallTicketCreate(BaseModel):
    """Request to create/link a hall ticket for an exam registration."""
    exam_registration_id: int = Field(
        ...,
        gt=0,
        description="Exam registration ID to create a hall ticket for",
    )
    document_id: int | None = Field(
        default=None,
        gt=0,
        description="Source hall-ticket document ID (optional at creation)",
    )


class HallTicketUpdate(BaseModel):
    """Update a hall ticket's linked resources or status."""
    document_id: int | None = Field(
        default=None,
        gt=0,
        description="Source hall-ticket document ID",
    )
    extraction_result_id: int | None = Field(
        default=None,
        gt=0,
        description="Extraction result ID from OCR processing",
    )
    match_result_id: int | None = Field(
        default=None,
        gt=0,
        description="Match result ID from domain matching",
    )
    verification_outcome_id: int | None = Field(
        default=None,
        gt=0,
        description="Verification outcome ID",
    )
    status: str | None = Field(
        default=None,
        description="New lifecycle status",
    )
    rejection_reason: str | None = Field(
        default=None,
        description="Reason if rejecting the hall ticket",
    )


class HallTicketResponse(BaseModel):
    """Response for a single hall ticket."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_registration_id: int
    document_id: int | None
    extraction_result_id: int | None
    match_result_id: int | None
    verification_outcome_id: int | None
    status: str
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class HallTicketListResponse(BaseModel):
    """Paginated list of hall tickets."""
    items: list[HallTicketResponse]
    total: int
    page: int
    page_size: int

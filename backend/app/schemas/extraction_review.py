from datetime import datetime

from pydantic import BaseModel, Field


class ReviewFieldRequest(BaseModel):
    corrected_value: str = Field(..., min_length=1, description="Corrected field value")
    review_status: str = Field(
        default="REVIEWED",
        description="Review status: REVIEWED or REVIEW_REQUIRED",
    )


class ReviewFieldResponse(BaseModel):
    id: int
    field_name: str
    extracted_value: str | None
    corrected_value: str | None
    ocr_confidence: float | None
    review_status: str
    extraction_method: str | None
    label_found: bool | None
    pattern_match: bool | None


class ReviewProgress(BaseModel):
    total_fields: int
    reviewed_count: int
    review_required_count: int


class ReviewDataResponse(BaseModel):
    extraction_result_id: int
    document_id: int
    ocr_engine: str
    ocr_avg_confidence: float
    processing_time_ms: int | None
    extraction_status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    progress: ReviewProgress
    fields: list[ReviewFieldResponse]


class CompleteReviewResponse(BaseModel):
    extraction_result_id: int
    status: str
    reviewed_at: datetime | None
    document_status: str

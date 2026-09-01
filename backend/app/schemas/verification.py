from datetime import datetime

from pydantic import BaseModel


class VerificationOutcomeResponse(BaseModel):
    id: int
    document_id: int
    extraction_result_id: int | None
    match_result_id: int | None
    student_id: int | None
    exam_id: int | None
    decision: str
    extraction_check: str
    match_check: str
    review_check: str
    ocr_avg_confidence: float | None
    match_status: str | None
    review_completed: bool
    reasoning: str | None
    created_at: datetime


class VerificationSummaryResponse(BaseModel):
    document_id: int
    has_extraction: bool
    has_match: bool
    extraction_check: str
    match_check: str
    review_check: str
    ocr_avg_confidence: float | None
    match_status: str | None
    review_completed: bool
    can_verify: bool
    blocking_reasons: list[str]

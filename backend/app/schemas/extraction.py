from datetime import datetime

from pydantic import BaseModel


class ExtractedFieldResponse(BaseModel):
    id: int
    field_name: str
    extracted_value: str | None
    corrected_value: str | None
    ocr_confidence: float | None
    pattern_match: bool | None
    label_found: bool | None
    database_match: bool | None
    extraction_method: str | None
    validation_status: str
    review_status: str


class ExtractionResultResponse(BaseModel):
    id: int
    document_id: int
    ocr_engine: str
    ocr_avg_confidence: float
    processing_time_ms: int | None
    status: str
    created_at: datetime
    fields: list[ExtractedFieldResponse] = []


class ProcessDocumentResponse(BaseModel):
    extraction_result_id: int
    status: str
    ocr_engine: str
    ocr_avg_confidence: float
    processing_time_ms: int | None
    fields_count: int
    review_required: bool

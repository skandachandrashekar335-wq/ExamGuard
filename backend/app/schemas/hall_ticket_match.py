from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HallTicketMatchSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_result_id: int
    field_name: str
    extracted_value: str | None
    expected_value: str | None
    matched: bool
    signal_type: str
    details: str | None
    created_at: datetime


class HallTicketMatchResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    extraction_result_id: int
    student_id: int | None
    exam_id: int | None
    registration_id: int | None
    seat_assignment_id: int | None
    overall_status: str
    created_at: datetime
    updated_at: datetime
    signals: list[HallTicketMatchSignalResponse] = []


class HallTicketMatchResultBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    extraction_result_id: int
    student_id: int | None
    exam_id: int | None
    registration_id: int | None
    seat_assignment_id: int | None
    overall_status: str
    created_at: datetime
    updated_at: datetime


class HallTicketMatchResultListResponse(BaseModel):
    items: list[HallTicketMatchResultBrief]
    page: int
    page_size: int
    total: int

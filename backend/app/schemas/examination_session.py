"""Examination session and gate event schemas (Phase 15)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExaminationSessionCreate(BaseModel):
    exam_id: int = Field(
        ...,
        gt=0,
        description="Exam ID",
    )
    exam_hall_id: int = Field(
        ...,
        gt=0,
        description="Exam hall ID",
    )
    expected_capacity: int | None = Field(
        default=None,
        ge=0,
        description="Expected number of students",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional session notes",
    )
    created_by: str | None = Field(
        default=None,
        max_length=100,
        description="Operator who created this session",
    )


class ExaminationSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    exam_hall_id: int
    status: str
    gate_status: str
    gate_open_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    expected_capacity: int | None
    notes: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class ExaminationSessionListResponse(BaseModel):
    items: list[ExaminationSessionResponse]
    page: int
    page_size: int
    total: int


class GateEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    previous_status: str
    new_status: str
    reason: str | None
    performed_by: str | None
    created_at: datetime


class GateEventListResponse(BaseModel):
    items: list[GateEventResponse]
    total: int


class GateOperationRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Reason for gate operation",
    )
    performed_by: str | None = Field(
        default=None,
        max_length=100,
        description="Operator performing this action",
    )


class StartSessionRequest(BaseModel):
    performed_by: str | None = Field(
        default=None,
        max_length=100,
        description="Operator starting this session",
    )


class EndSessionRequest(BaseModel):
    performed_by: str | None = Field(
        default=None,
        max_length=100,
        description="Operator ending this session",
    )


class ExaminationSessionSummary(BaseModel):
    total_sessions: int
    not_started: int
    in_progress: int
    completed: int
    cancelled: int
    total_entry_verifications: int
    total_attendance_records: int

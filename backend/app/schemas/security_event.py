from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.security_event import (
    SecurityAlertStatus,
    SecurityEventSeverity,
    SecurityEventType,
)


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    severity: str
    entity_type: str
    entity_id: int
    entry_verification_id: int | None = None
    student_id: int | None = None
    exam_id: int | None = None
    hall_id: int | None = None
    entry_point_id: int | None = None
    description: str | None = None
    metadata_json: str | None = None
    source: str
    created_at: datetime


class SecurityEventListResponse(BaseModel):
    items: list[SecurityEventResponse]
    total: int
    page: int
    page_size: int


class SecurityAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    security_event_id: int
    status: str
    severity: str
    message: str
    assigned_to: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class SecurityAlertListResponse(BaseModel):
    items: list[SecurityAlertResponse]
    total: int
    page: int
    page_size: int


class AcknowledgeAlertRequest(BaseModel):
    assigned_to: str | None = Field(
        default=None,
        description="Operator acknowledging this alert",
    )


class ResolveAlertRequest(BaseModel):
    resolution_notes: str | None = Field(
        default=None,
        description="Notes on how this alert was resolved",
    )
    assigned_to: str | None = Field(
        default=None,
        description="Operator resolving this alert",
    )


class DismissAlertRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reason for dismissing this alert",
    )
    assigned_to: str | None = Field(
        default=None,
        description="Operator dismissing this alert",
    )

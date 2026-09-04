from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EntryVerificationCreate(BaseModel):
    student_id: int = Field(
        ...,
        description="ID of the student attempting entry",
    )
    exam_registration_id: int = Field(
        ...,
        description="ID of the student's exam registration",
    )
    entry_point_id: int = Field(
        ...,
        description="ID of the physical entry point",
    )
    camera_id: int | None = Field(
        default=None,
        description="ID of the camera observing the entry (optional)",
    )
    hall_ticket_id: int | None = Field(
        default=None,
        description="ID of the hall ticket to link (optional)",
    )


class EntryVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    exam_registration_id: int
    exam_hall_id: int
    entry_point_id: int
    camera_id: int | None
    hall_ticket_id: int | None
    identity_verification_attempt_id: int | None
    status: str
    hall_ticket_check: str
    identity_check: str
    seat_check: str
    escalation_reason: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EntryVerificationListResponse(BaseModel):
    items: list[EntryVerificationResponse]
    total: int
    page: int
    page_size: int


class EscalateRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reason for escalation to human review",
    )


class ResolveRequest(BaseModel):
    granted: bool = Field(
        ...,
        description="True to GRANT, False to DENY",
    )
    reason: str | None = Field(
        default=None,
        description="Optional resolution notes",
    )

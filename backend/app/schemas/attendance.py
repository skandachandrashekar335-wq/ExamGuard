"""Schemas for attendance REST API (Phase 12.3).

Response schemas for attendance records and events.
No biometric data, face images, embeddings, or provider secrets exposed.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Attendance Record schemas
# ---------------------------------------------------------------------------


class AttendanceRecordResponse(BaseModel):
    """Attendance record response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    exam_id: int
    exam_registration_id: int
    status: str
    entry_verification_id: int | None
    entry_method: str
    entry_time: datetime
    hall_id: int
    seat_number: str | None
    recorded_at: datetime
    updated_at: datetime


class AttendanceListResponse(BaseModel):
    """Paginated list of attendance records."""

    items: list[AttendanceRecordResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Attendance Event schemas
# ---------------------------------------------------------------------------


class AttendanceEventResponse(BaseModel):
    """Attendance event response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    exam_id: int
    exam_registration_id: int
    entry_verification_id: int | None
    event_type: str
    status_snapshot: str
    recorded_by: str | None
    reason: str | None
    created_at: datetime


class AttendanceEventListResponse(BaseModel):
    """Paginated list of attendance events."""

    items: list[AttendanceEventResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Manual Correction schemas
# ---------------------------------------------------------------------------


class AttendanceCorrectionRequest(BaseModel):
    """Request body for manual attendance correction."""

    status: str = Field(
        ...,
        description="New attendance status. Allowed: PRESENT, EXCUSED.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reason for the correction.",
    )
    recorded_by: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Admin identifier performing the correction.",
    )


# ---------------------------------------------------------------------------
# Manual review (INCONCLUSIVE identity attempts) schemas
# ---------------------------------------------------------------------------


class ManualReviewRequest(BaseModel):
    """Request body for an invigilator manual review decision."""

    exam_registration_id: int = Field(
        ...,
        gt=0,
        description="Exam registration whose inconclusive attempt is reviewed.",
    )
    action: str = Field(
        ...,
        pattern="^(CHECK_IN|CHECK_OUT)$",
        description="Review decision: CHECK_IN (admit) or CHECK_OUT (do not admit).",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reason recorded with the decision (required for audit).",
    )


class ManualReviewResponse(BaseModel):
    """Result of a manual review decision."""

    exam_registration_id: int
    review_state: str = Field(
        ...,
        description="NOT_REVIEWED, CHECKED_IN, or CHECKED_OUT.",
    )
    event: AttendanceEventResponse
    attendance_record_id: int | None = None


class ManualReviewStatusResponse(BaseModel):
    """Current manual review status for a registration."""

    exam_registration_id: int
    review_state: str
    latest_attempt_id: int | None
    latest_attempt_decision: str | None
    session_status: str | None
    seat_number: str | None = None
    events: list[AttendanceEventResponse]


# ---------------------------------------------------------------------------
# Exam Summary schemas
# ---------------------------------------------------------------------------


class HallAttendanceSummary(BaseModel):
    """Per-hall attendance breakdown."""

    hall_id: int
    hall_name: str
    total: int
    present: int


class AttendanceSummaryResponse(BaseModel):
    """Exam attendance summary."""

    exam_id: int
    total_registered: int
    total_present: int
    total_absent: int
    total_excused: int
    attendance_rate: float
    by_hall: list[HallAttendanceSummary]

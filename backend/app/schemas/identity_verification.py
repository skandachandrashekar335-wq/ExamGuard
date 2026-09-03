from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IdentityVerificationCreate(BaseModel):
    """Request to create an identity verification attempt."""
    student_id: int = Field(..., gt=0, description="Student ID to verify")
    exam_registration_id: int = Field(
        ..., gt=0, description="Exam registration ID for this verification"
    )
    hall_ticket_id: int | None = Field(
        default=None, gt=0, description="Hall ticket ID (optional)"
    )
    verification_method: str = Field(
        default="MANUAL",
        description="Verification method: FACE, MANUAL, DOCUMENT, OTHER",
    )


class IdentityVerificationEvidenceCreate(BaseModel):
    """Request to record a piece of verification evidence."""
    signal_type: str = Field(
        ..., min_length=1, max_length=100,
        description="Type of evidence signal",
    )
    signal_value: str | None = Field(
        default=None, max_length=500,
        description="Value of the signal",
    )
    provider_name: str | None = Field(
        default=None, max_length=100,
        description="Provider name",
    )
    provider_version: str | None = Field(
        default=None, max_length=50,
        description="Provider version",
    )
    confidence: float | None = Field(
        default=None,
        description="Provider confidence for this signal",
    )
    details: str | None = Field(
        default=None,
        description="Additional details",
    )


class IdentityVerificationEvidenceResponse(BaseModel):
    """Response for a single evidence record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_id: int
    signal_type: str
    signal_value: str | None
    provider_name: str | None
    provider_version: str | None
    confidence: float | None
    details: str | None
    created_at: datetime


class IdentityVerificationResponse(BaseModel):
    """Response for a single identity verification attempt."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    exam_registration_id: int
    hall_ticket_id: int | None
    status: str
    verification_method: str
    decision: str
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class IdentityVerificationDetailedResponse(BaseModel):
    """Detailed response with evidence records."""
    attempt: IdentityVerificationResponse
    evidence: list[IdentityVerificationEvidenceResponse]


class IdentityVerificationListResponse(BaseModel):
    """Paginated list of identity verification attempts."""
    items: list[IdentityVerificationResponse]
    total: int
    page: int
    page_size: int


class IdentityVerificationStudentInfo(BaseModel):
    """Student summary for verification context."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    usn: str
    name: str


class IdentityVerificationExamInfo(BaseModel):
    """Exam summary for verification context."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    exam_name: str


class IdentityVerificationContextResponse(BaseModel):
    """Full context response with student and exam info."""
    attempt: IdentityVerificationResponse
    evidence: list[IdentityVerificationEvidenceResponse]
    student: IdentityVerificationStudentInfo | None = None
    exam: IdentityVerificationExamInfo | None = None


class VerifyFaceResponse(BaseModel):
    """Response for face verification: evidence records produced."""
    attempt_id: int
    evidence: list[IdentityVerificationEvidenceResponse]

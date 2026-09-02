from pydantic import BaseModel


class StudentVerificationStatus(BaseModel):
    student_id: int
    student_usn: str
    student_name: str
    registration_id: int
    registration_status: str
    seat_assignment_id: int | None = None
    seat_number: str | None = None
    hall_name: str | None = None
    verification_status: str = "NOT_UPLOADED"
    document_id: int | None = None
    extraction_check: str | None = None
    match_check: str | None = None
    review_check: str | None = None
    decision: str | None = None
    ocr_avg_confidence: float | None = None
    match_status: str | None = None
    verification_created_at: str | None = None


class ExamDashboardSummary(BaseModel):
    exam_id: int
    exam_name: str
    exam_date: str
    total_registered: int
    total_verified: int
    total_failed: int
    total_review_required: int
    total_incomplete: int
    total_not_uploaded: int
    total_seated: int
    verification_rate: float


class ExamDashboardResponse(BaseModel):
    summary: ExamDashboardSummary
    students: list[StudentVerificationStatus]

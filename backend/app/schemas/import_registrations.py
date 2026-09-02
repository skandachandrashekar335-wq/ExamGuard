from pydantic import BaseModel, Field


class BulkRegistrationRequest(BaseModel):
    exam_id: int = Field(
        ...,
        gt=0,
        description="Exam ID to register students for",
    )
    student_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of student IDs to register (max 500)",
    )


class BulkRegistrationItemResult(BaseModel):
    student_id: int
    status: str
    registration_id: int | None = None
    error: str | None = None


class BulkRegistrationResponse(BaseModel):
    total: int
    created: int
    skipped: int
    failed: int
    results: list[BulkRegistrationItemResult]


class BulkCancelRequest(BaseModel):
    registration_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of registration IDs to cancel (max 500)",
    )


class BulkCancelItemResult(BaseModel):
    registration_id: int
    status: str
    error: str | None = None


class BulkCancelResponse(BaseModel):
    total: int
    cancelled: int
    skipped: int
    failed: int
    results: list[BulkCancelItemResult]

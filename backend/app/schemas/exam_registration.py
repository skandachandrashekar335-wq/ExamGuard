from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExamRegistrationCreate(BaseModel):
    student_id: int = Field(
        ...,
        gt=0,
        description="Student ID",
        examples=[1],
    )
    exam_id: int = Field(
        ...,
        gt=0,
        description="Exam ID",
        examples=[1],
    )


class ExamRegistrationUpdate(BaseModel):
    status: str = Field(
        ...,
        description="New registration status",
        examples=["REGISTERED"],
    )


class ExamRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    exam_id: int
    status: str
    registered_at: datetime
    updated_at: datetime


class ExamRegistrationWithDetails(ExamRegistrationResponse):
    student_usn: str | None = None
    student_name: str | None = None
    exam_name: str | None = None


class ExamRegistrationListResponse(BaseModel):
    items: list[ExamRegistrationWithDetails]
    page: int
    page_size: int
    total: int

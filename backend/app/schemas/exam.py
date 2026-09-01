from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExamCreate(BaseModel):
    subject_id: int = Field(
        ...,
        gt=0,
        description="Subject ID",
        examples=[1],
    )
    exam_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Exam name (e.g. End Semester Examination)",
        examples=["End Semester Examination"],
    )
    exam_date: date = Field(
        ...,
        description="Exam date",
        examples=["2026-09-15"],
    )
    start_time: time = Field(
        ...,
        description="Exam start time",
        examples=["10:00"],
    )
    end_time: time = Field(
        ...,
        description="Exam end time",
        examples=["13:00"],
    )
    semester: int = Field(
        ...,
        ge=1,
        le=8,
        description="Semester number (1-8)",
        examples=[5],
    )
    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Department offering the exam",
        examples=["Computer Science"],
    )

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class ExamUpdate(BaseModel):
    subject_id: int | None = Field(
        default=None,
        gt=0,
        description="Subject ID",
    )
    exam_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Exam name",
    )
    exam_date: date | None = Field(
        default=None,
        description="Exam date",
    )
    start_time: time | None = Field(
        default=None,
        description="Exam start time",
    )
    end_time: time | None = Field(
        default=None,
        description="Exam end time",
    )
    semester: int | None = Field(
        default=None,
        ge=1,
        le=8,
        description="Semester number (1-8)",
    )
    department: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Department offering the exam",
    )
    is_active: bool | None = Field(
        default=None,
        description="Set to false to deactivate an exam",
    )

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class ExamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    exam_name: str
    exam_date: date
    start_time: time
    end_time: time
    semester: int
    department: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExamResponseWithSubject(ExamResponse):
    subject_code: str | None = None
    subject_name: str | None = None


class ExamListResponse(BaseModel):
    items: list[ExamResponseWithSubject]
    page: int
    page_size: int
    total: int

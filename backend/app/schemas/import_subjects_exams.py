from pydantic import BaseModel, Field, model_validator


class ImportSubjectItem(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Subject code (e.g. CS501)",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Subject name",
    )
    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Department offering the subject",
    )
    semester: int = Field(
        ...,
        ge=1,
        le=8,
        description="Semester number (1-8)",
    )
    credits: int | None = Field(
        default=None,
        gt=0,
        description="Credit hours (optional)",
    )


class ImportExamItem(BaseModel):
    subject_code: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Subject code to reference",
    )
    exam_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Exam name",
    )
    exam_date: str = Field(
        ...,
        description="Exam date (YYYY-MM-DD)",
    )
    start_time: str = Field(
        ...,
        description="Exam start time (HH:MM or HH:MM:SS)",
    )
    end_time: str = Field(
        ...,
        description="Exam end time (HH:MM or HH:MM:SS)",
    )
    semester: int = Field(
        ...,
        ge=1,
        le=8,
        description="Semester number (1-8)",
    )
    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Department offering the exam",
    )


class ImportSubjectExamRequest(BaseModel):
    subjects: list[ImportSubjectItem] = Field(
        default=[],
        max_length=200,
        description="Subject records to import (max 200)",
    )
    exams: list[ImportExamItem] = Field(
        default=[],
        max_length=500,
        description="Exam records to import (max 500)",
    )

    @model_validator(mode="after")
    def validate_at_least_one(self):
        if not self.subjects and not self.exams:
            raise ValueError("At least one of subjects or exams must be provided")
        return self


class ImportSubjectItemResult(BaseModel):
    code: str
    department: str
    status: str
    error: str | None = None


class ImportExamItemResult(BaseModel):
    subject_code: str
    exam_name: str
    status: str
    error: str | None = None


class ImportSubjectExamResponse(BaseModel):
    subject_total: int
    subject_created: int
    subject_skipped: int
    subject_failed: int
    exam_total: int
    exam_created: int
    exam_skipped: int
    exam_failed: int
    subject_results: list[ImportSubjectItemResult]
    exam_results: list[ImportExamItemResult]

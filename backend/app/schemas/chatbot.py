from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_text(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


class ChatQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User question in natural language",
        examples=["What documents are required for admission?", "When is the next exam timetable released?"]
    )
    session_id: str | None = Field(
        default=None,
        max_length=100,
        description="Client session identifier for tracking conversation context"
    )

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: object) -> object:
        return _strip_text(value)


class ChatQueryResponse(BaseModel):
    query: str
    answer: str
    category: str
    intent: str
    confidence: float
    matched: bool
    suggestions: list[str] = Field(default_factory=list)
    requires_admin_confirmation: bool = False
    is_verified: bool = True


class ChatCategory(BaseModel):
    name: str
    title: str
    description: str
    sample_questions: list[str] = Field(default_factory=list)


class ChatCategoryListResponse(BaseModel):
    categories: list[ChatCategory]


class ChatSuggestionListResponse(BaseModel):
    suggestions: list[str]


class KnowledgeBaseItemCreate(BaseModel):
    category: str = Field(..., min_length=2, max_length=50)
    intent: str = Field(..., min_length=2, max_length=100)
    question: str = Field(..., min_length=5, max_length=500)
    answer: str = Field(..., min_length=10)
    keywords: str = Field(default="", max_length=1000)
    is_verified: bool = True
    requires_admin_confirmation: bool = False

    @field_validator("category", "intent", "question", "keywords", mode="before")
    @classmethod
    def strip_fields(cls, value: object) -> object:
        return _strip_text(value)


class KnowledgeBaseItemUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=2, max_length=50)
    intent: str | None = Field(default=None, min_length=2, max_length=100)
    question: str | None = Field(default=None, min_length=5, max_length=500)
    answer: str | None = Field(default=None, min_length=10)
    keywords: str | None = Field(default=None, max_length=1000)
    is_verified: bool | None = None
    requires_admin_confirmation: bool | None = None
    is_active: bool | None = None


class KnowledgeBaseItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    intent: str
    question: str
    answer: str
    keywords: str
    is_verified: bool
    requires_admin_confirmation: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseItemListResponse(BaseModel):
    items: list[KnowledgeBaseItemResponse]
    page: int
    page_size: int
    total: int

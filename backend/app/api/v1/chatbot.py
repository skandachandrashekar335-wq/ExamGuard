from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import Role, require_role
from app.core.database import get_db
from app.schemas.chatbot import (
    ChatCategoryListResponse,
    ChatQueryRequest,
    ChatQueryResponse,
    ChatSuggestionListResponse,
    KnowledgeBaseItemCreate,
    KnowledgeBaseItemListResponse,
    KnowledgeBaseItemResponse,
    KnowledgeBaseItemUpdate,
)
from app.services import chatbot as chatbot_service

router = APIRouter(prefix="/chatbot", tags=["Admission Chatbot"])


@router.post("/query", response_model=ChatQueryResponse, summary="Query admission guidance chatbot")
def query_chatbot(
    payload: ChatQueryRequest,
    db: Session = Depends(get_db),
):
    """
    Public student-facing endpoint.
    Processes natural-language inquiries about courses, admissions, eligibility,
    fees, documents, examinations, timetables, and campus facilities.
    """
    return chatbot_service.process_chat_query(
        db, query=payload.query, session_id=payload.session_id
    )


@router.get("/categories", response_model=ChatCategoryListResponse, summary="List supported chatbot categories")
def list_categories():
    """
    Public endpoint.
    Returns all supported guidance categories, descriptions, and sample questions.
    """
    return chatbot_service.list_categories()


@router.get("/suggestions", response_model=ChatSuggestionListResponse, summary="Get suggested questions")
def get_suggestions():
    """
    Public endpoint.
    Returns suggested prompts to help students discover topics.
    """
    return ChatSuggestionListResponse(suggestions=chatbot_service.SUGGESTED_QUESTIONS)


# Admin Knowledge Base Management
@router.get("/knowledge", response_model=KnowledgeBaseItemListResponse, summary="List knowledge base entries")
def list_knowledge(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search questions or keywords"),
    include_inactive: bool = Query(False, description="Include deactivated entries"),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    items, total = chatbot_service.list_knowledge_items(
        db,
        page=page,
        page_size=page_size,
        category=category,
        search=search,
        include_inactive=include_inactive,
    )
    return KnowledgeBaseItemListResponse(
        items=[KnowledgeBaseItemResponse.model_validate(it) for it in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/knowledge", response_model=KnowledgeBaseItemResponse, status_code=201, summary="Create knowledge base item")
def create_knowledge_item(
    data: KnowledgeBaseItemCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN])),
):
    try:
        return chatbot_service.create_knowledge_item(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/knowledge/{item_id}", response_model=KnowledgeBaseItemResponse, summary="Update knowledge base item")
def update_knowledge_item(
    item_id: int,
    data: KnowledgeBaseItemUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN])),
):
    try:
        return chatbot_service.update_knowledge_item(db, item_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/knowledge/{item_id}", response_model=KnowledgeBaseItemResponse, summary="Deactivate knowledge base item")
def delete_knowledge_item(
    item_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN])),
):
    try:
        return chatbot_service.deactivate_knowledge_item(db, item_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services import document as doc_service

router = APIRouter(prefix="/documents", tags=["Documents"])

settings = get_settings()


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=201,
    summary="Upload a document",
)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Query(..., description="Document type (e.g. HALL_TICKET)"),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=422, detail="No filename provided")

    data = await file.read()

    try:
        return doc_service.upload_document(
            db,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            data=data,
            doc_type=document_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=DocumentListResponse, summary="List documents")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_type: str | None = Query(None, description="Filter by document type"),
    db: Session = Depends(get_db),
):
    documents, total = doc_service.list_documents(
        db, page=page, page_size=page_size, doc_type=document_type
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentResponse, summary="Get document metadata")
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = doc_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

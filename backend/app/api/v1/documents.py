from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.extraction import ExtractionResultResponse, ExtractedFieldResponse, ProcessDocumentResponse
from app.schemas.hall_ticket_match import HallTicketMatchResultResponse, HallTicketMatchSignalResponse
from app.services import document as doc_service
from app.services import hall_ticket_matching
from app.services import processing

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


@router.post(
    "/{document_id}/process",
    response_model=ProcessDocumentResponse,
    summary="Process a document through OCR and extraction",
)
def process_document(document_id: int, db: Session = Depends(get_db)):
    try:
        result = processing.process_document(db, document_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    fields = processing.get_extracted_fields(db, result.id)
    review_required = any(f.review_status == "REVIEW_REQUIRED" for f in fields)

    return ProcessDocumentResponse(
        extraction_result_id=result.id,
        status=result.status,
        ocr_engine=result.ocr_engine,
        ocr_avg_confidence=result.ocr_avg_confidence,
        processing_time_ms=result.processing_time_ms,
        fields_count=len(fields),
        review_required=review_required,
    )


@router.get(
    "/{document_id}/extraction",
    response_model=ExtractionResultResponse,
    summary="Get extraction results for a document",
)
def get_extraction(document_id: int, db: Session = Depends(get_db)):
    result = processing.get_extraction_result(db, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="No extraction results found for this document")

    fields = processing.get_extracted_fields(db, result.id)

    return ExtractionResultResponse(
        id=result.id,
        document_id=result.document_id,
        ocr_engine=result.ocr_engine,
        ocr_avg_confidence=result.ocr_avg_confidence,
        processing_time_ms=result.processing_time_ms,
        status=result.status,
        created_at=result.created_at,
        fields=[
            ExtractedFieldResponse(
                id=f.id,
                field_name=f.field_name,
                extracted_value=f.extracted_value,
                corrected_value=f.corrected_value,
                ocr_confidence=f.ocr_confidence,
                pattern_match=f.pattern_match,
                label_found=f.label_found,
                database_match=f.database_match,
                extraction_method=f.extraction_method,
                validation_status=f.validation_status,
                review_status=f.review_status,
            )
            for f in fields
        ],
    )


@router.post(
    "/{document_id}/match",
    response_model=HallTicketMatchResultResponse,
    status_code=201,
    summary="Match a hall ticket against domain records",
)
def match_hall_ticket(document_id: int, db: Session = Depends(get_db)):
    try:
        result = hall_ticket_matching.match_hall_ticket(db, document_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    signals = (
        db.query(hall_ticket_matching.HallTicketMatchSignal)
        .filter(
            hall_ticket_matching.HallTicketMatchSignal.match_result_id == result.id
        )
        .order_by(hall_ticket_matching.HallTicketMatchSignal.id)
        .all()
    )

    return HallTicketMatchResultResponse(
        id=result.id,
        document_id=result.document_id,
        extraction_result_id=result.extraction_result_id,
        student_id=result.student_id,
        exam_id=result.exam_id,
        registration_id=result.registration_id,
        seat_assignment_id=result.seat_assignment_id,
        overall_status=result.overall_status,
        created_at=result.created_at,
        updated_at=result.updated_at,
        signals=[
            HallTicketMatchSignalResponse(
                id=s.id,
                match_result_id=s.match_result_id,
                field_name=s.field_name,
                extracted_value=s.extracted_value,
                expected_value=s.expected_value,
                matched=s.matched,
                signal_type=s.signal_type,
                details=s.details,
                created_at=s.created_at,
            )
            for s in signals
        ],
    )


@router.get(
    "/{document_id}/match",
    response_model=HallTicketMatchResultResponse,
    summary="Get the latest matching result for a document",
)
def get_match_result(document_id: int, db: Session = Depends(get_db)):
    result = hall_ticket_matching.get_latest_match_result(db, document_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No matching results found for this document",
        )

    signals = (
        db.query(hall_ticket_matching.HallTicketMatchSignal)
        .filter(
            hall_ticket_matching.HallTicketMatchSignal.match_result_id == result.id
        )
        .order_by(hall_ticket_matching.HallTicketMatchSignal.id)
        .all()
    )

    return HallTicketMatchResultResponse(
        id=result.id,
        document_id=result.document_id,
        extraction_result_id=result.extraction_result_id,
        student_id=result.student_id,
        exam_id=result.exam_id,
        registration_id=result.registration_id,
        seat_assignment_id=result.seat_assignment_id,
        overall_status=result.overall_status,
        created_at=result.created_at,
        updated_at=result.updated_at,
        signals=[
            HallTicketMatchSignalResponse(
                id=s.id,
                match_result_id=s.match_result_id,
                field_name=s.field_name,
                extracted_value=s.extracted_value,
                expected_value=s.expected_value,
                matched=s.matched,
                signal_type=s.signal_type,
                details=s.details,
                created_at=s.created_at,
            )
            for s in signals
        ],
    )

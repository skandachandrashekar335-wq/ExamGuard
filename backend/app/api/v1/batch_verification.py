from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.batch_verification import BatchVerifyRequest, BatchVerifyResponse
from app.services import batch_verification

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/batch-verify",
    response_model=BatchVerifyResponse,
    summary="Batch verify multiple documents through the full pipeline",
)
def batch_verify(body: BatchVerifyRequest, db: Session = Depends(get_db)):
    data = batch_verification.batch_verify(db, body.document_ids)
    return BatchVerifyResponse(**data)

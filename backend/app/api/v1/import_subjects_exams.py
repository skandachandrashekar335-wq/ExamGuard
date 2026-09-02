from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.import_subjects_exams import (
    ImportSubjectExamRequest,
    ImportSubjectExamResponse,
)
from app.services import import_subjects_exams as import_service

router = APIRouter(prefix="/import", tags=["Import"])


@router.post(
    "/subjects-exams",
    response_model=ImportSubjectExamResponse,
    status_code=201,
    summary="Bulk import subjects and exams",
)
def bulk_import_subjects_exams(
    data: ImportSubjectExamRequest,
    db: Session = Depends(get_db),
):
    return import_service.import_subjects_exams(db, data.subjects, data.exams)

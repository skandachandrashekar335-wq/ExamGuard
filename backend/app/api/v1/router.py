from fastapi import APIRouter

from app.api.v1.documents import router as documents_router
from app.api.v1.exam_halls import router as exam_halls_router
from app.api.v1.exam_registrations import router as exam_registrations_router
from app.api.v1.exams import router as exams_router
from app.api.v1.students import router as students_router
from app.api.v1.subjects import router as subjects_router

router = APIRouter()

router.include_router(documents_router)
router.include_router(exam_halls_router)
router.include_router(exam_registrations_router)
router.include_router(exams_router)
router.include_router(students_router)
router.include_router(subjects_router)


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}

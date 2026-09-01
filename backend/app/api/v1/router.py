from fastapi import APIRouter

from app.api.v1.documents import router as documents_router
from app.api.v1.students import router as students_router
from app.api.v1.subjects import router as subjects_router

router = APIRouter()

router.include_router(documents_router)
router.include_router(students_router)
router.include_router(subjects_router)


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}

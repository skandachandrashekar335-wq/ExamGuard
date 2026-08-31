from fastapi import APIRouter

from app.api.v1.students import router as students_router

router = APIRouter()

router.include_router(students_router)


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}

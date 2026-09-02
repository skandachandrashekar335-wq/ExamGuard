from fastapi import APIRouter

from app.api.v1.batch_verification import router as batch_verification_router
from app.api.v1.import_audit_log import router as import_audit_log_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.documents import router as documents_router
from app.api.v1.exam_halls import router as exam_halls_router
from app.api.v1.exam_registrations import router as exam_registrations_router
from app.api.v1.exams import router as exams_router
from app.api.v1.import_registrations import router as import_registrations_router
from app.api.v1.import_seat_assignments import router as import_seat_assignments_router
from app.api.v1.import_status import router as import_status_router
from app.api.v1.import_students import router as import_students_router
from app.api.v1.import_subjects_exams import router as import_subjects_exams_router
from app.api.v1.seat_assignments import router as seat_assignments_router
from app.api.v1.students import router as students_router
from app.api.v1.subjects import router as subjects_router

router = APIRouter()

router.include_router(batch_verification_router)
router.include_router(import_audit_log_router)
router.include_router(dashboard_router)
router.include_router(documents_router)
router.include_router(exam_halls_router)
router.include_router(exam_registrations_router)
router.include_router(exams_router)
router.include_router(import_registrations_router)
router.include_router(import_seat_assignments_router)
router.include_router(import_status_router)
router.include_router(import_students_router)
router.include_router(import_subjects_exams_router)
router.include_router(seat_assignments_router)
router.include_router(students_router)
router.include_router(subjects_router)


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}

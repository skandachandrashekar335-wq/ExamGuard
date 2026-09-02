from fastapi import APIRouter

from app.schemas.import_common import ImportStatusResponse, ImportTypeLimit
from app.services.import_common import IMPORT_LIMITS

router = APIRouter(prefix="/import", tags=["Import"])


@router.get(
    "/status",
    response_model=ImportStatusResponse,
    summary="Get available import types and their limits",
)
def get_import_status() -> ImportStatusResponse:
    return ImportStatusResponse(
        import_types=[
            ImportTypeLimit(import_type=k, max_items=v)
            for k, v in IMPORT_LIMITS.items()
        ]
    )

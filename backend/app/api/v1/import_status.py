from fastapi import APIRouter, Depends

from app.auth import Role, require_role
from app.schemas.import_common import ImportStatusResponse, ImportTypeLimit
from app.services.import_common import IMPORT_LIMITS

router = APIRouter(prefix="/import", tags=["Import"])


@router.get(
    "/status",
    response_model=ImportStatusResponse,
    summary="Get available import types and their limits",
)
def get_import_status(
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.REVIEWER])),
) -> ImportStatusResponse:
    return ImportStatusResponse(
        import_types=[
            ImportTypeLimit(import_type=k, max_items=v)
            for k, v in IMPORT_LIMITS.items()
        ]
    )

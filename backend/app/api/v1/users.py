"""User management API (minimal)."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Role, require_role
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])


class UserResponse(BaseModel):
    id: int
    email: str | None
    full_name: str | None
    role: str


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users (ADMIN only)",
)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    offset = (page - 1) * page_size
    users = db.query(User).offset(offset).limit(page_size).all()
    total = db.query(User).count()
    return UserListResponse(
        items=[
            UserResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
            )
            for u in users
        ],
        total=total,
    )

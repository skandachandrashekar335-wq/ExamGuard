"""Authentication and authorization service for ExamGuard.

Provides JWT-based login, role-based access control, and protected route
utilities. All auth logic is server-side; no credentials in frontend code.

Role hierarchy:
- ADMIN: Full access to all admin operations and routes
- OPERATOR: Can operate within designated domains (exams, students, halls)
- INVIGILATOR: Assigned to specific exam/hall/entry-point, operational access
- REVIEWER: Can review and verify, but not administer

Token-based authentication using HS256 with secret from environment.
Access tokens are short-lived; refresh tokens are not supported.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import jwt

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_settings

settings = get_settings()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

_bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(
    token: str,
) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return claims
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# Role constants
class Role:
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    INVIGILATOR = "INVIGILATOR"
    REVIEWER = "REVIEWER"


ALL_ROLES = [Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER]


class InvigilatorScope:
    """Resolved scope for an INVIGILATOR's assignment.

    Contains the exam_id, hall_id, entry_point_id, and camera_id that the
    invigilator is assigned to. Used to enforce IDOR protection: endpoints
    check that requested resources belong to this scope.

    Returns None for non-INVIGILATOR roles (ADMIN/OPERATOR/REVIEWER get
    unrestricted access).
    """

    def __init__(
        self,
        exam_id: int,
        hall_id: int,
        entry_point_id: int | None = None,
        camera_id: int | None = None,
        assignment_id: int | None = None,
    ):
        self.exam_id = exam_id
        self.hall_id = hall_id
        self.entry_point_id = entry_point_id
        self.camera_id = camera_id
        self.assignment_id = assignment_id


def _get_invigilator_scope_inner(
    current_user: Dict[str, Any],
    db: Any,
) -> InvigilatorScope | None:
    """Inner function: resolve invigilator scope."""
    from app.models.invigilator_assignment import InvigilatorAssignment as _IA

    if current_user.get("role") != Role.INVIGILATOR:
        return None

    user_id = int(current_user["sub"])
    assignment = (
        db.query(_IA)
        .filter(_IA.user_id == user_id, _IA.is_active == True)
        .order_by(_IA.created_at.desc())
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active invigilator assignment found",
        )
    return InvigilatorScope(
        exam_id=assignment.exam_id,
        hall_id=assignment.exam_hall_id,
        entry_point_id=assignment.entry_point_id,
        camera_id=assignment.camera_id,
        assignment_id=assignment.id,
    )


def get_invigilator_scope(
    current_user: Dict[str, Any],
    db: Any,
) -> InvigilatorScope | None:
    """Resolve invigilator scope from JWT claims and database.

    Returns InvigilatorScope for INVIGILATOR role.
    Returns None for ADMIN/OPERATOR/REVIEWER (unrestricted access).
    Raises 403 if INVIGILATOR has no active assignment.

    Usage in endpoints:
        scope = get_invigilator_scope(_user, db)
    """
    if current_user.get("role") != Role.INVIGILATOR:
        return None
    return _get_invigilator_scope_inner(current_user, db)


def check_invigilator_scope(
    scope: InvigilatorScope | None,
    resource_exam_id: int | None = None,
    resource_hall_id: int | None = None,
) -> None:
    """Check that a resource belongs to the invigilator's scope.

    Raises 403 if the resource is outside the invigilator's assignment.
    No-op if scope is None (non-INVIGILATOR = unrestricted).
    """
    if scope is None:
        return
    if resource_exam_id is not None and resource_exam_id != scope.exam_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource outside your assigned exam",
        )
    if resource_hall_id is not None and resource_hall_id != scope.hall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource outside your assigned hall",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """FastAPI dependency: extract and validate the current user from JWT.

    Returns the decoded JWT claims dict with at least 'sub' and 'role'.
    Raises 401 if token is missing, expired, or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = decode_token(credentials.credentials)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if "role" not in claims or "sub" not in claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
        )

    return claims


def require_role(allowed_roles: List[str]):
    """Dependency factory: require the current user to have one of the given roles.

    Usage:
        @router.get("/admin-only")
        def admin_endpoint(user = Depends(require_role([Role.ADMIN]))):
            ...
    """
    def _check(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role: {user_role}. Required: {allowed_roles}",
            )
        return current_user
    return _check


def require_any_role(allowed_roles: List[str]):
    """Same as require_role — allows access if user has ANY of the given roles."""
    return require_role(allowed_roles)


# ---- Legacy compatibility (unused by routes, kept for non-route callers) ----

def get_current_user_raw(
    authorization: str | None = None,
) -> Optional[Dict[str, Any]]:
    """Legacy standalone function. Prefer get_current_user dependency."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    claims = decode_token(token)
    if claims is None:
        return None
    if "role" not in claims or "sub" not in claims:
        return None
    return claims

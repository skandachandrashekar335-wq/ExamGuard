"""Authentication and authorization service for ExamGuard.

Provides JWT-based login, role-based access control, and protected route
utilities. All auth logic is server-side; no credentials in frontend code.

Role hierarchy:
- ADMIN: Full access to all admin operations and routes
- OPERATOR: Can operate within designated domains (exams, students, halls)
- REVIEWER: Can review and verify, but not administer

Token-based authentication using HS256 with secret from environment.
Access tokens are short-lived; refresh tokens are not supported.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import jwt

from app.core.config import get_settings

settings = get_settings()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Claims to encode in the token.
        expires_delta: Optional timedelta for token expiration.
            Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
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
    """Decode and validate a JWT token.

    Args:
        token: The JWT string to decode.

    Returns:
        Dict of claims if valid, None if invalid/expired.
    """
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
    REVIEWER = "REVIEWER"


# Role permissions: which routes/resources each role can access
PERMISSIONS: Dict[str, List[str]] = {
    Role.ADMIN: [
        # Admin operations
        "api:admin:*",
        # Full access to all endpoints
        "GET,POST,PUT,DELETE",
    ],
    Role.OPERATOR: [
        # Operator can manage exams, students, halls, etc.
        "api:exams:*",
        "api:students:*",
        "api:exam_halls:*",
        "api:seat_assignments:*",
        "api:entry_verifications:*",
        "api:verification:*",
        "api:proxy_risk:*",
        # Can view but not administer
        "GET api:users:*",
        "GET api:roles:*",
        "GET api:permissions:*",
    ],
    Role.REVIEWER: [
        # Reviewer can view and verify
        "api:entry_verifications:GET",
        "api:verification:GET",
        "api:proxy_risk:GET",
        "api:attendance:GET",
        # Cannot administer
        "POST,PUT,DELETE denied",
    ],
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has the given permission.

    Args:
        role: The role string (Role.ADMIN, Role.OPERATOR, Role.REVIEWER).
        permission: The permission string to check.

    Returns:
        True if the role has the permission, False otherwise.
    """
    role_perms = PERMISSIONS.get(role, [])
    # Check if the permission matches
    if permission in role_perms:
        return True
    # Wildcard match: api:resource:action
    if permission.endswith("*"):
        prefix = permission.rstrip("*")
        return any(p.startswith(prefix) for p in role_perms)
    return False


def require_role(allowed_roles: List[str]):
    """Decorator factory for FastAPI endpoints that checks role membership.

    Args:
        allowed_roles: List of role strings that are allowed to access the endpoint.

    Returns:
        Depends function that raises HTTP 403 if the user's role is not allowed.
    """
    from fastapi import HTTPException, status

    def dependency(current_user: dict = ...):  # type: ignore
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role: {current_user.get('role')}",
            )
        return current_user

    return dependency


def require_any_role(allowed_roles: List[str]):
    """Decorator factory that allows access if the user has ANY of the given roles.

    Args:
        allowed_roles: List of role strings that are allowed.

    Returns:
        Depends function.
    """
    from fastapi import HTTPException, status

    def dependency(current_user: dict = ...):  # type: ignore
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role: {current_user.get('role')}",
            )
        return current_user

    return dependency
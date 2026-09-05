"""Security hardening and compliance module for ExamGuard.

Provides input validation, error sanitization, rate limiting,
audit integrity, and privacy controls. All functions are defensive
and designed to protect against common web vulnerabilities.

Core principles:
- Validate all input at the API boundary.
- Never expose raw database exceptions to clients.
- Sanitize all error messages of sensitive data.
- Rate-limit endpoint access to prevent abuse.
- Maintain audit trails for security-sensitive operations.
- Never log secrets, credentials, or biometric data.
"""

import re
import time
import hashlib
from functools import wraps
from typing import Callable, Any, Dict, List, Optional
from fastapi import Request, Response, HTTPException

from app.core.config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def validate_username(value: str) -> str:
    """Validate a username field.

    Rules:
    - 3-50 characters
    - Alphanumeric plus underscores and hyphens
    - Cannot start or end with a hyphen
    """
    if not value or not value.strip():
        raise ValueError("Username cannot be empty")
    value = value.strip()
    if len(value) < 3 or len(value) > 50:
        raise ValueError("Username must be 3-50 characters")
    if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9_-]*[a-zA-Z0-9])?$", value):
        raise ValueError(
            "Username must be alphanumeric with underscores and hyphens allowed"
        )
    return value


def validate_email(value: str) -> str:
    """Validate an email address field."""
    import re as re_mod
    if not value or not value.strip():
        raise ValueError("Email cannot be empty")
    value = value.strip()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re_mod.match(pattern, value):
        raise ValueError("Invalid email format")
    return value


def validate_exam_code(value: str) -> str:
    """Validate an exam code field."""
    if not value or not value.strip():
        raise ValueError("Exam code cannot be empty")
    value = value.strip()
    if not re.match(r"^[A-Z0-9_-]{3,20}$", value):
        raise ValueError(
            "Exam code must be 3-20 characters of uppercase letters, numbers, underscores, or hyphens"
        )
    return value


def validate_seat_number(value: str) -> Optional[str]:
    """Validate a seat number field.

    Rules:
    - If provided, must be numeric
    - Can be None/empty (seat not assigned)
    """
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if not re.match(r"^\d+$", value):
        raise ValueError("Seat number must be numeric if provided")
    return value


# -------------------------------------------------------------------------
# Rate limiting (in-memory, no Redis dependency)
# -------------------------------------------------------------------------

# Simple in-memory rate limiter using a dict of {client_id: [timestamps]}
# This is a basic implementation; production would use Redis with TTL.

_rate_limits: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 100  # requests per window


def _client_id(request: Request) -> str:
    """Get a unique identifier for the client making the request."""
    # Try to get real IP, fall back to proxy IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_rate_limited(client_id: str) -> bool:
    """Check if a client has exceeded the rate limit."""
    now = time.time()
    timestamps = _rate_limits.get(client_id, [])

    # Remove timestamps outside the window
    recent = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    _rate_limits[client_id] = recent

    return len(recent) >= RATE_LIMIT_MAX


def _record_rate_limit(client_id: str) -> None:
    """Record a request for rate limiting purposes."""
    now = time.time()
    if client_id not in _rate_limits:
        _rate_limits[client_id] = []
    _rate_limits[client_id].append(now)


def rate_limit_handler(request: Request, call_next) -> Response:
    """FastAPI middleware for rate limiting.

    Returns HTTP 429 if the client has exceeded the rate limit.
    """
    client_id = _client_id(request)

    if _is_rate_limited(client_id):
        _record_rate_limit(client_id)
        return Response(
            content="{\"detail\": \"Rate limit exceeded\"}",
            status_code=429,
            media_type="application/json",
        )

    _record_rate_limit(client_id)
    response = await call_next(request)
    return response


def rate_limit_middleware(func):
    """Decorator to apply rate limiting to a route handler."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        return await rate_limit_handler(request, lambda: func(request, *args, **kwargs))
    return wrapper


# -------------------------------------------------------------------------
# Error sanitization
# -------------------------------------------------------------------------

def sanitize_error(error: Exception) -> str:
    """Sanitize an error message for client response.

    Removes any sensitive information such as:
    - Stack traces
    - Database connection details
    - Credentials/API keys
    - Fileystem paths
    - Biometric data references
    """
    message = str(error)

    # Remove common sensitive patterns
    patterns = [
        (r"Password:\s*\S+", "[Redacted]"),
        (r"API Key:\s*\S+", "[Redacted]"),
        (r"Bearer\s+\S+", "[Redacted]"),
        (r"file:\/\/\S+", "[Redacted]"),
        (r"/\S+/[a-zA-Z0-9/]+", "[Redacted]"),  # filesystem paths
        (r"secret\w*\s*[:=]\s*\S+", "[Redacted]"),
    ]

    for pattern, replacement in patterns:
        message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

    # Truncate overly long messages
    if len(message) > 500:
        message = message[:500] + "..."

    return message


def http_exception_handler(exc: HTTPException) -> dict:
    """Sanitize an HTTPException for the client response.

    Returns a dict with a safe error message and status code.
    """
    return {
        "detail": sanitize_error(exc.detail),
        "status_code": exc.status_code,
    }


# -------------------------------------------------------------------------
# Audit logging (security-sensitive operations)
# -------------------------------------------------------------------------

# In-memory audit log (would be replaced with persistent storage in production)
_audit_log: List[Dict[str, Any]] = []
MAX_AUDIT_ENTRIES = 1000


def audit_log(
    operation: str,
    resource: str,
    resource_id: str,
    user_role: str,
    status: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a security-sensitive operation for audit purposes.

    Args:
        operation: The operation performed (e.g., "CREATE", "UPDATE", "DELETE")
        resource: The resource type (e.g., "user", "exam", "verification")
        resource_id: The resource identifier
        user_role: The role of the user who performed the operation
        status: The status of the operation ("SUCCESS", "FAILURE")
        details: Optional additional details (will be sanitized)
    """
    # Sanitize details before logging
    sanitized_details = {}
    if details:
        for key, value in details.items():
            # Don't log sensitive fields
            if key.lower() in {"password", "secret", "key", "token", "biometric",
                              "embedding", "credentials"}:
                sanitized_details[key] = "[Redacted]"
            else:
                sanitized_details[key] = value

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "resource": resource,
        "resource_id": resource_id,
        "user_role": user_role,
        "status": status,
        "details": sanitized_details,
    }

    _audit_log.append(entry)
    if len(_audit_log) > MAX_AUDIT_ENTRIES:
        _audit_log.pop(0)


def get_audit_log(
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    user_role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve audit log entries, optionally filtered.

    Args:
        resource: Filter by resource type
        resource_id: Filter by resource ID
        user_role: Filter by user role

    Returns:
        List of audit log entries matching the filters.
    """
    results = _audit_log
    if resource:
        results = [e for e in results if e["resource"] == resource]
    if resource_id:
        results = [e for e in results if e["resource_id"] == resource_id]
    if user_role:
        results = [e for e in results if e["user_role"] == user_role]
    return results


# -------------------------------------------------------------------------
# Privacy controls
# -------------------------------------------------------------------------

SENSITIVE_KEYS = {
    "password",
    "secret",
    "api_key",
    "secret_key",
    "private_key",
    "certificate",
    "cert",
    "fingerprint",
    "face_image",
    "face_embedding",
    "biometric_data",
    "raw_ocr",
    "database_url",
    "filesystem_path",
    "stack_trace",
    "secret_key",
    "private_key",
}


def safe_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive keys from a dictionary before rendering or logging.

    Args:
        data: The dictionary to sanitize.

    Returns:
        A new dictionary with sensitive keys removed/replaced.
    """
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        if key_lower in SENSITIVE_KEYS:
            result[key] = "[Redacted]"
        elif isinstance(value, dict):
            result[key] = safe_payload(value)
        elif isinstance(value, list):
            result[key] = [safe_payload(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result


# -------------------------------------------------------------------------
# Export


__all__ = [
    "validate_username",
    "validate_email",
    "validate_exam_code",
    "validate_seat_number",
    "rate_limit_middleware",
    "rate_limit_handler",
    "sanitize_error",
    "http_exception_handler",
    "audit_log",
    "get_audit_log",
    "safe_payload",
]
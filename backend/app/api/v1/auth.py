"""Firebase Authentication exchange endpoint for ExamGuard.

Handles the exchange of Firebase ID tokens for ExamGuard JWT/session tokens.

Architecture:
  Google Account
    ↓ Firebase Authentication (popup/signInWithPopup)
    ↓ Firebase ID Token (JWT)
    ↓ POST /auth/firebase/exchange
       ↓ Firebase ID Token Verification (server-side)
       ↓ Map Firebase identity to ExamGuard User
       ↓ Assign role (NO auto-ADMIN)
       ↓ Issue ExamGuard JWT token
    ↓ Protected APIs via existing RBAC
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services.firebase_verification import verify_firebase_id_token
from app.models import User
from app.core.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import select

from typing import Optional

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.post("/firebase/exchange", response_model=dict)
async def firebase_token_exchange(
    request: Request,
    db: Session = Depends(get_db),
):
    """Exchange a Firebase ID token for an ExamGuard user session.

    Frontend sends the Firebase ID token received from Firebase Authentication.
    Backend verifies the token, maps the Firebase identity to an ExamGuard user,
    and returns the user's session/role information.

    Request:
        Authorization: Bearer <Firebase ID token>
        OR: {"firebaseToken": "<Firebase ID token>"}

    Response:
        {
            "user": {
                "id": int,
                "email": str | None,
                "full_name": str | None,
                "role": str,
                "is_active": bool,
                "firebase_uid": str | None,
            },
            "token": "<ExamGuard JWT access token>",
            "requires_onboarding": bool,
        }

    Security:
    - Token verification is server-side; frontend token is never trusted directly
    - Role is NOT automatically granted as ADMIN
    - New Google users receive REVIEWER role by default
    - ADMIN must be explicitly provisioned
    """
    # Extract Firebase token from Authorization header or request body
    firebase_token: Optional[str] = None

    # Try Authorization header: "Bearer <token>"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 7:
        firebase_token = auth_header[7:].strip()
    else:
        # Try request body
        try:
            body = await request.json()
            firebase_token = body.get("firebaseToken") if isinstance(body, dict) else None
        except Exception:
            pass

    if not firebase_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Firebase ID token",
        )

    # Verify the Firebase ID token server-side
    claims = verify_firebase_id_token(firebase_token)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase ID token",
        )

    # Extract verified identity
    firebase_uid = claims.get("uid")
    email = claims.get("email")
    full_name = claims.get("name")

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing required UID claim",
        )

    # Step 3: Find or create the ExamGuard user
    # Logic:
    # 1. Try to find existing user by firebase_uid first
    # 2. If not found, try to find existing user by email
    # 3. If neither exists, create a new user with REVIEWER role (non-privileged)
    # 4. Link firebase_uid to the user

    user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )

    # If not found by firebase_uid, try by email
    if user is None:
        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

    # If user found (by either method), update last_login and firebase_uid
    if user:
        from sqlalchemy import func as sql_func
        user.last_login_at = sql_func.now()
        if not user.firebase_uid and firebase_uid:
            user.firebase_uid = firebase_uid
        # Update email if it changed and user didn't have one
        if not user.email and email:
            user.email = email
        if not user.full_name and full_name:
            user.full_name = full_name
    else:
        # Create new user - REVIEWER role by default (NO auto-ADMIN)
        user = User(
            email=email,
            full_name=full_name,
            firebase_uid=firebase_uid,
            role="REVIEWER",  # Default non-privileged role
            is_active=True,
        )
        db.add(user)

    # Commit changes
    db.commit()
    db.refresh(user)

    # Step 4: Check if initial admin provisioning is needed
    # Only if no ADMIN currently exists in the system
    result = db.execute(select(User).filter(User.role == "ADMIN"))
    existing_admin = result.scalar_one_or_none()

    if not existing_admin and settings.INITIAL_ADMIN_EMAILS:
        # Check if this user's email is in the initial provisioning list
        if email and email in settings.INITIAL_ADMIN_EMAILS:
            # Grant ADMIN role for initial provisioning only
            user.role = "ADMIN"
            db.commit()

    # Step 5: Issue ExamGuard JWT token
    from datetime import timedelta
    from app.auth import create_access_token

    # Token expires in 30 minutes (existing architecture)
    expires_delta = timedelta(minutes=30)
    examguard_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
            "email": user.email,
            "full_name": user.full_name,
        }
    )

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "firebase_uid": user.firebase_uid,
        },
        "token": examguard_token,
        "requires_onboarding": user.role != "ADMIN" and not existing_admin,
    }
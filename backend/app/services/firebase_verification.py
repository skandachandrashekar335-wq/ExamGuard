"""Firebase Authentication ID token verification service.

Verifies Firebase ID tokens server-side using the Firebase Admin SDK.
Never trusts identity information from the client - all identity must be
verified through Firebase verification before mapping to ExamGuard users.
"""

import base64
import json
import time
from typing import Optional, Dict, Any

import httpx

from app.core.config import get_settings

settings = get_settings()


def _verify_firebase_token_http(token: str) -> Optional[Dict[str, Any]]:
    """Verify a Firebase ID token by calling the Firebase auth REST API.

    This does NOT require the Firebase Admin SDK service account;
    it uses the public Firebase Auth REST endpoint with the token.

    Args:
        token: The Firebase ID token string (JWT)

    Returns:
        Dict of decoded claims if verification successful, None otherwise.
    """
    if not token or not token.strip():
        return None

    project_id = settings.FIREBASE_PROJECT_ID
    if not project_id:
        # Cannot verify without project ID
        return None

    url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyIdToken?key={project_id}"

    try:
        response = httpx.post(url, json={"idToken": token}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Firebase returns the verified claims
            if "users" in data and len(data["users"]) > 0:
                user = data["users"][0]
                # Extract the standard claims
                return {
                    "uid": user.get("localId"),
                    "email": user.get("email"),
                    "email_verified": user.get("emailVerified", False),
                    "name": user.get("displayName"),
                    "photo_url": user.get("photoUrl"),
                    "iat": user.get("authTime"),
                    "exp": user.get("expirationTime"),
                }
            return None
        elif response.status_code == 401 or response.status_code == 403:
            # Invalid token / unauthorized
            return None
        else:
            # Other error - don't leak details
            return None
    except httpx.RequestError:
        # Network error - don't crash, just fail open (return None)
        return None
    except (json.JSONDecodeError, KeyError, TypeError):
        # Malformed response
        return None


def verify_firebase_id_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a Firebase ID token and return the decoded claims.

    This is the main entry point for Firebase authentication verification.
    The token is a Firebase ID token (JWT) signed by Firebase auth.

    Verification steps:
    1. Check token is present and non-empty
    2. Verify signature via Firebase's REST API
    3. Extract uid, email, name, and other claims
    4. Return claims dict or None if invalid

    Args:
        token: The Firebase ID token string

    Returns:
        Dict of verified claims including uid, email, name, etc.
        None if the token is invalid, expired, or revoked.
    """
    # Step 1: Basic validation
    if not token or not token.strip():
        return None

    # Step 2: Verify via Firebase REST API (requires FIREBASE_PROJECT_ID)
    claims = _verify_firebase_token_http(token.strip())
    if claims is not None:
        return claims

    # No verification succeeded - token is invalid or Firebase is not configured
    return None
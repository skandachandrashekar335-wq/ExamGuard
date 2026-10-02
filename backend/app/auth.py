"""Authentication and authorization service for ExamGuard.



Provides JWT-based login, role-based access control, and protected route

utilities. All auth logic is server-side; no credentials in frontend code.



Permanent account roles:

- ADMIN: Full access to all admin operations and routes

- OPERATOR: Can operate within designated domains (exams, students, halls)

- REVIEWER: Can review and verify, but not administer



Exam-scoped capability:

- INVIGILATOR: derived from an active InvigilatorAssignment for the requested

  exam/hall/session; not stored as a permanent User.role.



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





# Permanent account roles only; invigilator capability is derived from active

# assignment records and must never be persisted as a permanent User.role.

ALL_ROLES = [Role.ADMIN, Role.OPERATOR, Role.REVIEWER]





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

        # Every active exam/hall pair. One user can be assigned to more than one exam.

        self.scopes: list[tuple[int, int]] = [(exam_id, hall_id)]





def _get_invigilator_scope_inner(

    current_user: Dict[str, Any],

    db: Any,

) -> InvigilatorScope | None:

    """Inner function: resolve invigilator scope from active assignments."""

    from app.models.invigilator_assignment import InvigilatorAssignment as _IA



    user_id = int(current_user["sub"])

    assignment = (

        db.query(_IA)

        .filter(_IA.user_id == user_id, _IA.is_active == True)

        .order_by(_IA.created_at.desc())

        .first()

    )

    if not assignment:

        if current_user.get("role") == Role.INVIGILATOR:

            raise HTTPException(

                status_code=status.HTTP_403_FORBIDDEN,

                detail="No active invigilator assignment found",

            )

        return None

    return InvigilatorScope(

        exam_id=assignment.exam_id,

        hall_id=assignment.exam_hall_id,

        entry_point_id=assignment.entry_point_id,

        camera_id=assignment.camera_id,

        assignment_id=assignment.id,

    )





def _scope_from_assignments(assignments: list) -> InvigilatorScope:

    """Build a scope covering every active assignment for this user."""

    primary = assignments[0]

    scope = InvigilatorScope(

        exam_id=primary.exam_id,

        hall_id=primary.exam_hall_id,

        entry_point_id=primary.entry_point_id,

        camera_id=primary.camera_id,

        assignment_id=primary.id,

    )

    scope.scopes = [(row.exam_id, row.exam_hall_id) for row in assignments]

    return scope





def get_invigilator_scope(

    current_user: Dict[str, Any],

    db: Any,

) -> InvigilatorScope | None:

    """Resolve exam-scoped invigilator capability from active assignments.



    ADMIN and OPERATOR stay unrestricted. Any user with a live

    InvigilatorAssignment gains exam/hall scope for that assignment, regardless

    of their permanent account role; legacy permanent INVIGILATOR values are

    treated as assignment-derived capability only.

    """

    role = current_user.get("role")

    if role in (Role.ADMIN, Role.OPERATOR):

        return None

    if db is None:

        if role == Role.INVIGILATOR:

            return _get_invigilator_scope_inner(current_user, db)

        return None



    from app.services import invigilator_assignment as assign_svc



    try:

        user_id = int(current_user["sub"])

    except (KeyError, TypeError, ValueError):

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="Token missing required claims",

        )

    assignments = assign_svc.get_all_assignments_for_user(db, user_id)

    if role == Role.INVIGILATOR and not assignments:

        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail="No active invigilator assignment found",

        )

    if not assignments:

        return None

    return _scope_from_assignments(assignments)





def check_invigilator_scope(

    scope: InvigilatorScope | None,

    resource_exam_id: int | None = None,

    resource_hall_id: int | None = None,

) -> None:

    """Check that a resource belongs to one of the invigilator's assignments.



    Raises 403 if the resource is outside every active assignment.

    No-op if scope is None (ADMIN/OPERATOR, or a role with no assignment).

    """

    if scope is None:

        return

    pairs = scope.scopes or [(scope.exam_id, scope.hall_id)]

    for exam_id, hall_id in pairs:

        exam_ok = resource_exam_id is None or resource_exam_id == exam_id

        hall_ok = resource_hall_id is None or resource_hall_id == hall_id

        if exam_ok and hall_ok:

            return

    exam_miss = resource_exam_id is not None and all(

        resource_exam_id != exam_id for exam_id, _hall_id in pairs

    )

    raise HTTPException(

        status_code=status.HTTP_403_FORBIDDEN,

        detail=(

            "Access denied: resource outside your assigned exam"

            if exam_miss

            else "Access denied: resource outside your assigned hall"

        ),

    )





def require_role_or_active_assignment(allowed_roles: List[str]):

    """Allow a listed permanent role, or any account with an active exam assignment.



    The assignment is the invigilator capability. The permanent account role

    is not rewritten to INVIGILATOR.

    """

    from app.core.database import get_db



    def _check(

        current_user: Dict[str, Any] = Depends(get_current_user),

        db: Any = Depends(get_db),

    ):

        if current_user.get("role") in allowed_roles:

            return current_user

        from app.services import invigilator_assignment as assign_svc



        try:

            user_id = int(current_user["sub"])

        except (KeyError, TypeError, ValueError):

            raise HTTPException(

                status_code=status.HTTP_401_UNAUTHORIZED,

                detail="Token missing required claims",

            )

        if assign_svc.get_all_assignments_for_user(db, user_id):

            return current_user

        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail=(

                f"Insufficient role: {current_user.get('role')}. "

                "An active exam assignment is required."

            ),

        )



    return _check





def assert_live_invigilator_session(db: Any, scope: InvigilatorScope, exam_id: int) -> None:

    """Invigilator operations run only while the assigned session is IN_PROGRESS."""

    from app.models.examination_session import ExaminationSession, SessionStatus



    halls = [hall_id for assigned_exam, hall_id in scope.scopes if assigned_exam == exam_id]

    query = db.query(ExaminationSession).filter(

        ExaminationSession.exam_id == exam_id,

        ExaminationSession.status == SessionStatus.IN_PROGRESS.value,

    )

    if halls:

        query = query.filter(ExaminationSession.exam_hall_id.in_(halls))

    if query.first() is None:

        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail=(

                "Invigilator actions are available only while the assigned "

                "exam session is in progress"

            ),

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



    Exam-scoped invigilator capability is granted by active assignments rather

    than a permanent User.role, so assignment-bearing reviewers/operators can

    access invigilator endpoints when the route explicitly includes the capability.



    Usage:

        @router.get("/admin-only")

        def admin_endpoint(user = Depends(require_role([Role.ADMIN]))):

            ...

    """

    from app.core.database import get_db



    def _check(

        current_user: Dict[str, Any] = Depends(get_current_user),

        db: Any = Depends(get_db),

    ):

        user_role = current_user.get("role")

        if user_role in allowed_roles and user_role != Role.INVIGILATOR:

            return current_user



        if Role.INVIGILATOR in allowed_roles:

            try:

                user_id = int(current_user["sub"])

            except (KeyError, TypeError, ValueError):

                raise HTTPException(

                    status_code=status.HTTP_401_UNAUTHORIZED,

                    detail="Token missing required claims",

                )

            from app.services import invigilator_assignment as assign_svc

            if assign_svc.get_all_assignments_for_user(db, user_id):

                return current_user

            if user_role == Role.INVIGILATOR:

                raise HTTPException(

                    status_code=status.HTTP_403_FORBIDDEN,

                    detail="No active invigilator assignment found",

                )



        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail=f"Insufficient role: {user_role}. Required: {allowed_roles}",

        )

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

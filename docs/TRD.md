# ExamGuard Technical Requirements / Technical Design Document

## Architecture

### Backend Architecture

- **Framework**: FastAPI (Python 3.14.x)
- **ORM**: SQLAlchemy 2.x
- **Migrations**: Alembic (26 migrations, head at 026)
- **Database**: PostgreSQL
- **API**: REST API under `/api/v1/` prefix
- **Auth**: Firebase ID token verification (server-side REST), ExamGuard JWT (HS256, 30 min)
- **RBAC**: Role-based access control (ADMIN > OPERATOR > REVIEWER)
- **CORS**: Configurable via `CORS_ORIGINS` env var
- **Monitoring**: In-memory event/alert buffers (Phase 19, no persistence)
- **Rate Limiting**: Per-attempt and global per-minute (configurable)
- **File Upload**: Multipart support, size limits configurable

### Frontend Architecture

- **Framework**: Next.js 16.x with App Router
- **Language**: TypeScript 5.x
- **CSS**: Tailwind CSS v4
- **Styling**: Monochrome editorial design (Playfair Display / Source Serif 4 / JetBrains Mono)
- **Auth State**: AuthContext bridging Firebase → ExamGuard session
- **API Clients**: Typed fetch clients (`iv-api.ts`, `entry-verification-api.ts`, etc.)
- **Build**: `next build` (Turbopack), typecheck via `npx tsc`

### Database Architecture

- **Migration System**: Alembic 26 migrations (001-026)
- **Head revision**: `026_create_users_table.py`
- **Models**: 29+ SQLAlchemy models
- **Soft-delete**: `is_active` field used throughout
- **Indexes**: Unique on email and firebase_uid; indexed on is_active
- **Cascade**: Standard SQLAlchemy cascade rules
- **Audit fields**: `created_by`, `recorded_by`, `created_at`, `updated_at` in models

### API Architecture

- **Router**: Single router at `backend/app/api/v1/router.py` including all v1 route modules
- **34 route modules** under `backend/app/api/v1/`
- **3 routes intentionally public**: `import_status.py`, `monitoring.py`, `ws_monitoring.py`
- **Authentication**: `POST /api/v1/auth/firebase/exchange` — Firebase token → ExamGuard user/role
- **RBAC**: `require_role()`, `require_any_role()`, `has_permission()` from `app/auth.py`
- **Role constants**: `Role.ADMIN`, `Role.OPERATOR`, `Role.REVIEWER`
- **Dependencies**: Not all routes wired with `get_current_user`; RBAC available but not uniformly enforced

### Authentication Architecture

- **Login mechanism**: Google Firebase Authentication with popup sign-in
- **Token flow**: Firebase ID token → `POST /api/v1/auth/firebase/exchange` → server verifies → maps identity → ExamGuard user → ExamGuard JWT issued
- **Role assignment**: New Google users receive REVIEWER role by default
- **Admin provisioning**: `INITIAL_ADMIN_EMAILS` env var; only when no ADMIN exists; one-time grant
- **JWT session**: HS256, 30-min expiry, claims: `sub` (user id), `role`
- **Token verification**: Server-side; frontend token never trusted directly
- **Inactive users**: `is_active` field blocks authentication/use of protected APIs
- **Invalid/expired tokens**: Return 401 without exposing sensitive details

### Firebase Flow

```
Google Account
    ↓ Firebase Authentication (popup/signInWithPopup)
    ↓ Firebase ID Token (JWT)
    ↓ POST /api/v1/auth/firebase/exchange
       ↓ Server-side Firebase ID Token Verification (REST API: identitytoolkit.googleapis.com)
       ↓ Map Firebase identity to ExamGuard User
       ↓ Assign role (REVIEWER by default; ADMIN only via INITIAL_ADMIN_EMAILS)
       ↓ Issue ExamGuard JWT token (HS256, 30 min)
    ↓ Protected APIs via existing RBAC
```

### RBAC

- **Role hierarchy**: ADMIN > OPERATOR > REVIEWER
- **Permission checks**: `require_role([roles])`, `require_any_role([roles])`, `has_permission(role, permission)`
- **Frontend**: Role-based UI visibility (UX only)
- **Backend**: Real security boundary; enforces authorization on API routes
- **User self-promotion**: Blocked (cannot change own role)
- **Google user auto-promotion**: Blocked (REVIEWER role by default)
- **Admin provisioning**: `INITIAL_ADMIN_EMAILS` only evaluated when no ADMIN exists

### Service Layer

- **Provider abstraction**: `FaceVerificationProvider` Protocol with `verify()`, `health_check()`, `get_capabilities()`
- **DeterministicProvider**: Test provider with configurable scores
- **UniFaceProvider**: Real face detection/recognition/anti-spoofing via ONNX Runtime (local, no external API)
- **Image validation**: 3-layer defense-in-depth (Pydantic schema, API endpoint, service layer)
- **Audit trail**: JSON-encoded override entries, verification event logging, safe metadata
- **Rate limiting**: Per-attempt and global per-minute (thread-safe via threading.Lock)
- **Human review/override**: `POST /{attempt_id}/review` and `POST /{attempt_id}/override`
- **Idempotency**: Repeated verify_face calls allowed (evidence accumulates by design)

### Provider Abstraction

- **Protocol**: `FaceVerificationProvider` with `verify()`, `health_check()`, `get_capabilities()`
- **Data types**: Frozen dataclasses for request/result/error
- **Provider capabilities**: Describes features and health status
- **Factory**: `get_face_verification_provider()` reads config and returns appropriate provider
- **Providers**:
  - `DeterministicProvider`: Test provider with configurable scores
  - `UniFaceProvider`: Real face detection/recognition/anti-spoofing via ONNX Runtime

### Identity Verification Decision Engine

- **Threshold configuration**: `IDENTITY_VERIFICATION_MATCH_THRESHOLD` (default 0.85)
- **Near-threshold zone**: `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR` (default 0.7)
- **Decision policy**:
  1. No evidence → INCONCLUSIVE
  2. Liveness FAIL → NO_MATCH
  3. Similarity >= threshold → MATCH (poor quality → INCONCLUSIVE)
  4. Similarity >= threshold * near_factor → INCONCLUSIVE
  5. Similarity < near zone → NO_MATCH
  6. Liveness PASS without similarity → INCONCLUSIVE
  7. Insufficient evidence → INCONCLUSIVE
- **DecisionResult**: decision, reasoning, policy_version, metadata (threshold, near_threshold, decision_reason, providers_used, similarity stats)
- **Missing evidence**: Never silently treated as PASS or NO_MATCH

### Database Schema

See BACKEND_SCHEMA.md for complete table/listing.

### API Endpoints (selected)

- `POST /api/v1/auth/firebase/exchange` — Firebase token exchange
- `GET/POST /api/v1/exams` — Exam management
- `GET/POST /api/v1/hall-tickets` — Hall ticket management
- `GET/POST /api/v1/entry-verifications` — Entry verification workflow
- `GET/POST /api/v1/identity-verifications` — Identity verification
- `GET/POST /api/v1/monitoring/events` — Monitoring events (public)
- `GET/POST /api/v1/security-events` — Security events
- `GET/POST /api/v1/attendance` — Attendance
- `GET/POST /api/v1/admin/` — Admin operations (RBAC-protected)
- `GET/POST /api/v1/import/` — Import workflows (public)

### Configuration

- **Environment variables**: `.env` file (no committed secrets)
- **Key vars**: `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `FIREBASE_PROJECT_ID`, `INITIAL_ADMIN_EMAILS`
- **Defaults**: `SECRET_KEY` = "change-me-to-a-random-secret-key" (dev), `FACE_VERIFICATION_PROVIDER` = "deterministic", `IMAGE_RETENTION_DAYS` = 0

### Testing Strategy

- **Backend**: 2466+ tests passing (verified), includes unit, service, API, and integration tests
- **Integration**: 76/76 tests in `test_phase_10_5_integration.py` pass (full workflow, hall ticket, seat, camera, identity, decision combinations, state machine hardening, human escalation, repeated operations, concurrency, data integrity, API/service/DB integration, privacy/security regression)
- **E2E**: Limited; integration tests exist for core workflow
- **No tests weakened or deleted** during implementation

### Failure Modes

- Provider unavailable → `fail_attempt()` with categorized reason
- Invalid images → validation errors (422)
- Wrong attempt status → 422 with safe error message
- Liveness fail → NO_MATCH (possible spoof)
- Near-threshold → INCONCLUSIVE (conservative evaluation)
- Client cannot submit threshold, decision, ALLOW, or DENY
- Override requires non-empty reason; only on terminal states
- Decision engine cannot be bypassed

### Deployment Considerations

- Production Firebase Console configuration required (Google provider, OAuth consent screen)
- `INITIAL_ADMIN_EMAILS` must be set for initial admin provisioning
- `SECRET_KEY` must be changed from development placeholder
- CORS origins must be configured for production domains
- No database reset; existing data untouched
- Alembic migration head at 026; new migrations only for actual schema changes

### Failure Modes

- Provider unavailable → `fail_attempt()` with categorized reason
- Invalid images → validation errors (422)
- Wrong attempt status → 422 with safe error message
- Liveness fail → NO_MATCH (possible spoof)
- Near-threshold → INCONCLUSIVE (conservative evaluation)
- Client cannot submit threshold, decision, ALLOW, or DENY
- Override requires non-empty reason; only on terminal states
- Decision engine cannot be bypassed

## Service Layer

### Face Verification Service

- **Provider factory**: `get_face_verification_provider()` reads `FACE_VERIFICATION_PROVIDER` config
- **verify_face()**: Validates attempt eligibility, obtains provider, checks health, calls `provider.verify()`, maps result → evidence records, persists via `record_evidence()`
- **Provider errors** → `fail_attempt()` (not evidence). Verification results → evidence records (decision engine decides)
- **Works on** CREATED and IN_PROGRESS attempts with FACE verification method

### Identity Verification Service

- **Service functions**: `create_attempt()`, `get_attempt()`, `list_attempts()`, `start_attempt()`, `complete_attempt()`, `fail_attempt()`, `cancel_attempt()`, `record_evidence()`, `get_attempt_with_context()`
- **Validation**: 3-layer defense-in-depth (Pydantic schema, API endpoint, service layer)
- **Rate limiting**: Per-attempt (`FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT`, default 5) and global per-minute (`FACE_VERIFICATION_MAX_CALLS_PER_MINUTE`, default 60)

### Decision Engine

- **evaluate_evidence_detailed()**: Returns `DecisionResult` with audit metadata
- **Configurable thresholds**: `IDENTITY_VERIFICATION_MATCH_THRESHOLD`, `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR`
- **Decision logic**: As defined in TRD.md PRD.md section

### Audit Trail

- **Override audit entries**: `build_override_audit_entry()`, `parse_override_audit_entry()`
- **Verification event logging**: `log_verification_event()`
- **Safe metadata**: `build_verification_audit_metadata()`
- **Uses existing `failure_reason` field** for override audit (no new DB tables)

### Rate Limiting

- **Per-attempt limit**: `FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT` (default 5), tracked in-memory
- **Global per-minute limit**: `FACE_VERIFICATION_MAX_CALLS_PER_MINUTE` (default 60), tracked in-memory
- **Thread-safe**: via `threading.Lock`
- **Bounded**: max 10,000 tracked attempt IDs with eviction
- **Zero = unlimited**: `0` means no rate limiting

### Human Review / Override

- **review_attempt()**: Marks COMPLETED/FAILED attempts as under human review; stores notes in `failure_reason`
- **override_decision()**: Overrides decision of COMPLETED/FAILED attempts; requires `new_decision` + `reason`; optional `operator_id`; full audit trail; does NOT erase original evidence

## Security Considerations

- **No secrets** hard-coded in source code or frontend bundles
- **No Firebase private credentials** in frontend code (only public web config)
- **Backend RBAC** is the real security boundary; frontend route hiding is UX only
- **Google auth does not auto-grant ADMIN**: new users receive REVIEWER role
- **User self-promotion**: blocked (cannot change own role)
- **Invalid/expired tokens**: return 401 without detail exposure
- **CORS**: configured via `CORS_ORIGINS` env var; no wildcards in production
- **Audit logging**: mutation safeguards present; no unauthorized modifications
- **Sensitive data**: no raw images, no embeddings, no biometric data in API responses or logs
- **Error sanitization**: no filesystem paths, Python tracebacks, or internal module names exposed to clients
- **Constant-time comparison**: `hmac.compare_digest` for credential comparison
- **No composite score leakage**: independent signals preserved; no composite confidence scores

## Privacy Considerations

- **No raw images stored** (retention_days = 0 by default)
- **No embeddings persisted** in database
- **No biometric data** in audit metadata
- **Transient in-memory processing only**
- **Provider errors sanitized** at API boundary
- **No secrets** in code or database
- **Override audit** contains only safe operational data
- **FACE_VERIFICATION_IMAGE_RETENTION_DAYS** = 0 maintained

## Technology Versions (from actual package files)

- **Python**: 3.14.x
- **FastAPI**: latest compatible
- **SQLAlchemy**: 2.0.x
- **Alembic**: 1.13.x
- **PostgreSQL**: compatible version
- **Next.js**: 16.3.3
- **React**: 19.2.8
- **TypeScript**: 5.x
- **Tailwind CSS**: v4
- **Pytest**: 9.1.x
- **Pydantic**: 2.5.x
- **Pydantic-Settings**: 2.15.x
- **Httpx**: 0.28.x
- **OpenCV-headless**: 5.0.x
- **NumPy**: 2.5.x
- **Pillow**: 12.3.x
- **Pytesseract**: 0.3.13
- **UniFace**: 4.0.0 (optional dependency)
- **Onnxruntime**: 1.29.0 (cp314 wheels)

## Environment Variables (from `backend/app/core/config.py`)

- `SECRET_KEY`: str = "change-me-to-a-random-secret-key" (must change for production)
- `DATABASE_URL`: str = "postgresql://user:password@localhost:5432/examguard"
- `CORS_ORIGINS`: list[str] = ["http://localhost:3000"]
- `NEXT_PUBLIC_API_URL`: str = "http://localhost:8000"
- `FIREBASE_PROJECT_ID`: str | None = None (env-driven)
- `INITIAL_ADMIN_EMAILS`: list[str] = [] (initial provisioning only)
- `FACE_VERIFICATION_PROVIDER`: str = "deterministic"
- `FACE_VERIFICATION_MAX_IMAGE_SIZE_MB`: int = 5
- `FACE_VERIFICATION_IMAGE_RETENTION_DAYS`: int = 0
- `IDENTITY_VERIFICATION_MATCH_THRESHOLD`: float = 0.85
- `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR`: float = 0.7
- `IDENTITY_VERIFICATION_POLICY_VERSION`: str = "1.0"
- `PROXY_RISK_ELEVATED_THRESHOLD`: float = 30.0
- `PROXY_RISK_HIGH_THRESHOLD`: float = 60.0
- `PROXY_RISK_CRITICAL_THRESHOLD`: float = 80.0
- `PROXY_RISK_MAX_SCORE`: float = 100.0
- `MONITORING_EVENT_BUFFER_SIZE`: int = 1000
- `MONITORING_ALERT_BUFFER_SIZE`: int = 200
- `MONITORING_MAX_CONNECTIONS`: int = 100
- `MONITORING_HEARTBEAT_INTERVAL`: int = 30
- `MONITORING_STALE_TIMEOUT`: int = 60
- `FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT`: int = 5
- `FACE_VERIFICATION_MAX_CALLS_PER_MINUTE`: int = 60

## API Architecture Summary

All API routes are under `/api/v1/` prefix. The main router at `backend/app/api/v1/router.py` includes all 34 route modules. Three routes are intentionally public (import_status, monitoring, ws_monitoring); the rest have authentication dependencies available but vary in enforcement. RBAC functions (`require_role`, `require_any_role`, `has_permission`) are defined in `app/auth.py` but not uniformly wired across all routes.

## Health Check

- `GET /health` — Returns status (healthy/degraded) and database connection
- Database connectivity verified on each health check
- CORS origins from config
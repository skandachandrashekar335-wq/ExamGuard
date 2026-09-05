# ExamGuard Master Roadmap

> This is the reconstructed master roadmap for the ExamGuard project.
> It serves as the project's authoritative planning document going forward.
> This document was created after Phase 4 completion to formalize the 23-phase architecture.

---

## Project Overview

**ExamGuard** — AI-powered Examination Entry Verification, Anti-Proxy, Security, and Attendance Management Platform.

Built with FastAPI + SQLAlchemy + PostgreSQL (backend), Next.js + TypeScript + Tailwind (frontend).

---

## Phase 0 — Architecture & Project Foundation

**Status: COMPLETE**

- Repository and monorepo foundation
- FastAPI backend
- Next.js frontend
- PostgreSQL
- SQLAlchemy
- Alembic
- Configuration and environment management
- Architecture documentation
- Git workflow

---

## Phase 1 — Database & Student Foundation

**Status: COMPLETE**

- PostgreSQL integration
- SQLAlchemy models/base
- Database dependency
- Student model
- Initial migrations
- Student persistence foundation

---

## Phase 2 — Student Management

**Status: COMPLETE**

- Student CRUD
- Pydantic schemas
- Service layer
- Search
- Pagination
- Student activation/deactivation
- Student management frontend

---

## Phase 3 — Document Ingestion & OCR Intelligence

**Status: COMPLETE**

- Document upload
- Storage abstraction
- Local storage
- Document validation
- OCR pipeline
- PDF/image preprocessing
- Tesseract integration
- Rule-based extraction
- OCR confidence signals
- Extracted fields
- Processing workflow
- Hall-ticket document support

---

## Phase 4 — Exam & Hall-Ticket Intelligence

**Status: COMPLETE**

- Subject management
- Exam management
- Exam hall management
- Exam registration
- Seat assignment
- Hall-ticket domain matching
- Extraction review/correction
- Verification decision and audit trail
- Exam verification dashboard
- Batch verification
- Admin management pages

---

## Phase 5 — Examination Operations & Data Import

**Status: COMPLETE**

Focus:
- Bulk student import (Step 1)
- Bulk subject/exam import (Step 2)
- Bulk registration management (Step 3)
- Bulk seat assignment workflows (Step 4)
- Import validation framework (Step 5)
- Excel/CSV admin import center (Step 6)
- Import audit logging (Step 7)

**Dependencies:** Phases 0–4 (student, subject, exam, registration, seat assignment models and APIs must exist).

**New models/migrations:** `ImportAuditLog` model (migration 013) with enums for import type, operation, and status. Tracks every bulk import operation with row counts, timestamps, and bounded error summaries.

**Frontend work completed:** Import hub page, 4 import pages (students, subjects-exams, registrations, seat-assignments) with Excel/CSV support, import history/audit page.

**Testing requirements:** 525 backend tests passing (38 audit-specific tests covering model, service, API, integration).

---

## Phase 6 — Hall-Ticket Lifecycle Management

**Status: COMPLETE**

### 6.1 Hall-Ticket Domain Model & Database Foundation
**Status: COMPLETE**
- `HallTicket` model with lifecycle statuses (CREATED → EXTRACTED → MATCHED → VERIFIED/REJECTED/CANCELLED)
- Links exam_registration to document, extraction, match, and verification outcomes
- Unique constraint on exam_registration_id prevents duplicate active tickets
- Alembic migration 014
- Service layer with status transition validation
- REST API: create, get by ID, get by registration, list, update
- 46 comprehensive tests (model, service, API, lifecycle, regression)

### 6.2 Hall-Ticket Upload & Ingestion
**Status: COMPLETE**
- `link_document()` service: associates a HALL_TICKET document with an existing HallTicket
- `on_extraction_complete()` hook: auto-transitions CREATED → EXTRACTED when OCR finishes
- `on_match_complete()` hook: auto-transitions EXTRACTED → MATCHED when matching finishes
- Both hooks integrated into `processing.py` and `hall_ticket_matching.py` pipelines
- API: `POST /hall-tickets/{id}/link-document`

### 6.3 Hall-Ticket ↔ Student/Exam Linking
**Status: COMPLETE**
- `get_with_context()`: returns HallTicket with linked Student, Exam, ExamRegistration, Document
- API: `GET /hall-tickets/{id}/detailed` — full context response
- Schema: `HallTicketDetailedResponse`, `HallTicketStudentInfo`, `HallTicketExamInfo`, `HallTicketDocumentInfo`

### 6.4 Hall-Ticket Lifecycle & Status Management
**Status: COMPLETE**
- `_transition()` helper: validates and applies status transitions with timestamp update
- `STATUS_TRANSITIONS` dict enforced on all status changes
- Auto-transitions via hooks (extraction/matching) + manual via PATCH

### 6.5 Hall-Ticket Review/Approval Workflow
**Status: COMPLETE**
- `approve()`: moves MATCHED → VERIFIED, optionally links verification_outcome_id
- `reject()`: moves MATCHED → REJECTED, stores rejection_reason, optionally links verification_outcome_id
- API: `POST /hall-tickets/{id}/approve`, `POST /hall-tickets/{id}/reject`

### 6.6 Hall-Ticket Admin UI
**Status: COMPLETE**
- `/hall-tickets` — list page with status filter, USN search, pagination, status-colored badges
- `/hall-tickets/[id]` — detail page with lifecycle progress, student/exam/document info, approve/reject actions
- 17 frontend pages total, all building successfully

### 6.7 Hall-Ticket Search & Operations
**Status: COMPLETE**
- `search_hall_tickets()`: filter by USN (partial match), exam_id, status, subject_code
- API: `GET /hall-tickets/search?usn=...&exam_id=...&status=...&subject_code=...`

### 6.8 Integration Tests + Phase 6 hardening
**Status: COMPLETE**
- 73 hall-ticket-specific tests: model, create, retrieve, update, list, link-document, approve, reject, context, search, API endpoints
- Fixed FK cleanup ordering in `test_verification.py`, `test_batch_verification.py`, `test_dashboard.py` (HallTicket before ExamRegistration, ExtractedField before ExtractionResult)
- 598 total backend tests passing
- Frontend: 17 pages building successfully

---

## Phase 7 — Identity Verification Foundation

**Status: COMPLETE**

### 7.1 Identity Verification Domain Model & Database Foundation
**Status: COMPLETE**
- `IdentityVerificationAttempt` model with lifecycle: CREATED → IN_PROGRESS → COMPLETED/FAILED/CANCELLED
- `IdentityVerificationEvidence` model for signal-level evidence storage
- `IdentityVerificationMethod` enum: FACE, MANUAL, DOCUMENT, OTHER
- `IdentityVerificationDecision` enum: PENDING, MATCH, NO_MATCH, INCONCLUSIVE
- Alembic migration 015
- `STATUS_TRANSITIONS` dict enforced on all status changes

### 7.2 Identity Verification Service Layer
**Status: COMPLETE**
- `create_attempt()`: validates student, registration, hall_ticket ownership
- `get_attempt()`, `list_attempts()`: retrieval with filters
- `start_attempt()`: CREATED → IN_PROGRESS
- `complete_attempt()`: → COMPLETED with decision
- `fail_attempt()`: → FAILED with reason
- `cancel_attempt()`: → CANCELLED
- `record_evidence()`: stores evidence signals
- `get_attempt_with_context()`: returns attempt + student + exam + hall_ticket

### 7.3 Identity Verification Decision Engine
**Status: COMPLETE**
- Provider-independent decision engine (`identity_verification_decision.py`)
- Configurable similarity threshold via `IDENTITY_VERIFICATION_MATCH_THRESHOLD` (default 0.85)
- Decision logic: similarity + liveness + quality checks
- No biometric data stored; no raw face images

### 7.4 Identity Verification API
**Status: COMPLETE**
- REST API at `/api/v1/identity-verifications`
- Endpoints: create, get, get-context, list, start, fail, cancel, evaluate
- Full validation on all inputs
- Read-only list with pagination

### 7.5 Identity Verification Admin UI
**Status: COMPLETE**
- `/identity-verifications` list page with status/decision filters
- `/identity-verifications/[id]` detail page with lifecycle progress, evidence, actions
- 19 frontend pages total, all building successfully

### 7.6 Identity Verification Tests
**Status: COMPLETE**
- 62 comprehensive tests: model, service create, lifecycle, evidence, context, list, decision engine, API
- 660 total backend tests passing

**Dependencies:** Phases 0–4. This is an architectural phase establishing abstractions before Phase 8 implements face verification.

**New models/migrations:** `IdentityVerificationAttempt`, `IdentityVerificationEvidence` models (migration 015).

**Frontend work completed:** Identity verification list and detail pages.

---

## Phase 8 — Face Verification / UniFace Integration

**Status: COMPLETE (Phase 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8 all complete)**

### 8.1 Face Verification Architecture & Provider Abstraction
**Status: COMPLETE**

Core architectural principle:
> AI/perception = evidence. Business logic = authority.

Face verification providers produce evidence signals. The decision engine
evaluates that evidence. Providers NEVER directly authorize or deny exam entry.

**Provider contract:**
- `FaceVerificationProvider` Protocol with `verify()`, `health_check()`, `get_capabilities()`
- `FaceVerificationRequest`: reference_image + probe_image bytes + context
- `FaceVerificationResult`: identity_match_score, liveness_score, liveness_passed, image_quality_score, evidence_metadata
- `FaceVerificationError`: typed error categories (PROVIDER_UNAVAILABLE, TIMEOUT, INVALID_INPUT, etc.)
- `ProviderCapabilities` and `ProviderStatus`: describe provider features and health
- All dataclasses are frozen (immutable)

**Provider abstraction location:** `app/services/face_verification/`

**Files created:**
- `app/services/face_verification/__init__.py` — public API
- `app/services/face_verification/types.py` — all data types
- `app/services/face_verification/protocol.py` — FaceVerificationProvider Protocol
- `app/services/face_verification/factory.py` — provider factory from config
- `app/services/face_verification/providers/__init__.py`
- `app/services/face_verification/providers/deterministic.py` — test provider

**Configuration added to `app/core/config.py`:**
- `FACE_VERIFICATION_PROVIDER: str = "deterministic"` — provider selection
- `FACE_VERIFICATION_PROVIDER_URL: str | None = None` — future provider URL
- `FACE_VERIFICATION_PROVIDER_API_KEY: str | None = None` — future API key
- `FACE_VERIFICATION_MAX_IMAGE_SIZE_MB: int = 5` — image size limit
- `FACE_VERIFICATION_IMAGE_RETENTION_DAYS: int = 0` — 0 = never store images

**Privacy decisions:**
- Raw images are NEVER stored by ExamGuard (retention_days = 0 by default)
- Biometric templates are managed by the provider, not ExamGuard
- Provider credentials are never exposed in API responses
- Evidence metadata must not contain raw images or biometric templates
- Provider errors are not logged with image content

**Security decisions:**
- All dataclasses are frozen to prevent accidental mutation
- Provider errors are typed (FaceVerificationErrorType) — not generic strings
- Provider availability is checked before verification attempts
- Image size limits enforced via configuration

**Tests added:** 28 tests
- Protocol conformance (4 tests)
- DeterministicProvider behavior (8 tests)
- Provider failure handling (3 tests)
- Sensitive data leakage prevention (3 tests)
- Evidence ≠ Decision separation (3 tests)
- Factory behavior (2 tests)
- Immutability verification (5 tests)

**Frontend changes:**
- `privacy/page.tsx`: Fixed monochrome violations (replaced accent-cyan/emerald/amber/pink with monochrome tokens)
- `terms/page.tsx`: Fixed monochrome violations (same treatment)
- No camera UI, no fake face-match percentages, no fake liveness PASS

### 8.2 Face Verification Provider Integration
**Status: COMPLETE**

Wire the face verification provider into the identity verification service.

**Service integration (`app/services/identity_verification.py`):**
- `verify_face()`: new service function that validates attempt eligibility, obtains provider via factory, checks provider health, calls `provider.verify()`, converts `FaceVerificationResult` → multiple `IdentityVerificationEvidence` records, persists via existing `record_evidence()`
- Provider errors → `fail_attempt()` (not evidence). Verification results → evidence records (decision engine decides).
- Works on CREATED and IN_PROGRESS attempts with FACE verification method

**Evidence mapping (provider result → evidence records):**
- `identity_match_score` → `signal_type="similarity_score"`, `confidence=score`
- `liveness_score` → `signal_type="liveness_score"`, `confidence=score`
- `liveness_passed` → `signal_type="liveness"`, `signal_value="PASS"/"FAIL"`
- `image_quality_score` → `signal_type="image_quality"`, `signal_value="GOOD"/"POOR"`
- All evidence details are JSON with `source: "face_verification_provider"`

**API endpoint (`app/api/v1/identity_verification.py`):**
- `POST /{attempt_id}/verify-face`: accepts base64-encoded reference_image and probe_image, returns `VerifyFaceResponse` with evidence records
- Validates base64 encoding, attempt eligibility, and provider availability

**Schema additions (`app/schemas/identity_verification.py`):**
- `VerifyFaceRequest`: reference_image, probe_image, image format fields
- `VerifyFaceResponse`: attempt_id + evidence list

**Tests added:** 35 tests (`test_verify_face_integration.py`)
- Happy path (5 tests): evidence records returned, persisted, attempt stays in progress, provider info present, works on CREATED attempts
- Evidence mapping (8 tests): similarity_score, liveness_score, liveness PASS/FAIL, image_quality GOOD/POOR, none scores → no evidence, JSON details
- Failure semantics (9 tests): attempt not found, wrong status, wrong method, empty images, provider unavailable fails attempt, provider error fails attempt
- Sensitive data (2 tests): no raw images in evidence, no raw images in provider result
- Evidence ≠ decision (3 tests): verify_face does not complete attempt, continuous values, decision engine processes evidence
- Multiple calls (1 test): evidence accumulates
- API happy path (2 tests): returns 201, correct response fields
- API errors (5 tests): invalid base64, not found, wrong status, wrong method, provider unavailable

**Test count:** 832 passing (750 existing + 82 new)

### 8.3 UniFace Integration
**Status: COMPLETE**

UniFace (yakhyo/uniface v4.0.0) for real face detection, recognition, and anti-spoofing via ONNX Runtime — fully local, no external API calls.

**Provider (`app/services/face_verification/providers/uniface_provider.py`):**
- `UniFaceProvider` implementing `FaceVerificationProvider` Protocol
- Lazy initialization: models downloaded on first `verify()` call (~30 MB total)
- `_load_uniface_modules()` method for clean testability
- Pipeline: decode → RetinaFace detection → ArcFace recognition → MiniFASNet anti-spoof → evidence
- Anti-spoofing failure is non-fatal: identity match still returned
- Models: RetinaFace, ArcFace, MiniFASNet — all via ONNX Runtime

**Config:**
- `FACE_VERIFICATION_PROVIDER="uniface"` activates the real provider
- Default remains `"deterministic"` for development/testing

**Dependency:**
- `uniface[cpu]>=4.0.0` added as optional dependency in `pyproject.toml`
- Onnxruntime 1.29.0 with cp314 wheels for Python 3.14 on Windows x86-64

**Tests:** 27 tests (`test_uniface_provider.py`) with mocked UniFace — no model downloads required

### 8.4 Real Face Verification Pipeline
**Status: COMPLETE**

End-to-end face verification pipeline with robust input validation, real provider-derived evidence, and comprehensive privacy/security controls.

**Input Validation (3-layer defense-in-depth):**
1. Pydantic `model_validator` on `VerifyFaceRequest`: base64 validation, format validation
2. API endpoint: strict `base64.b64decode(validate=True)`, image validation via `validate_image_bytes()`
3. Service layer: defense-in-depth validation before provider call

**Image Validation (`app/services/face_verification/validation.py`):**
- Magic byte detection (JPEG `\xff\xd8\xff`, PNG `\x89PNG`)
- Configurable size limits (default 5MB via `FACE_VERIFICATION_MAX_IMAGE_SIZE_MB`)
- Dimension limits (min 16px, max 16384px per side)
- Decompression bomb protection (max total pixels)
- Corrupted image detection via OpenCV decode

**Face Detection:**
- 0 faces → `NO_FACE_DETECTED` error
- 1 face → proceed
- >1 faces → `MULTIPLE_FACES_DETECTED` error
- Never silently selects first/largest face

**Face Recognition:**
- ArcFace embeddings → cosine similarity → `similarity_score` evidence
- No composite confidence scores; independent signals preserved

**Liveness/Anti-Spoofing:**
- MiniFASNet single-image classification (real/fake + confidence)
- Non-fatal: identity match still returned on anti-spoofing failure
- When disabled: liveness signals are None (not fabricated)

**Privacy:**
- No raw images stored/logged/returned
- No embeddings stored/logged/returned
- Transient in-memory processing only
- Provider errors sanitized at API boundary

**Tests:** 82 tests (`test_face_verification_pipeline.py`) — image validation, API validation, service validation, detection, recognition, liveness, evidence mapping, privacy, lifecycle, provider abstraction, decision separation, error types

### 8.5 Threshold + Decision Integration
**Status: COMPLETE**

Enhanced the decision engine with configurable thresholds, near-threshold zone, and decision metadata for audit trail.

**Configuration (`app/core/config.py`):**
- `IDENTITY_VERIFICATION_MATCH_THRESHOLD: float = 0.85` — similarity score threshold
- `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR: float = 0.7` — near-zone factor
- `IDENTITY_VERIFICATION_POLICY_VERSION: str = "1.0"` — policy version for audit
- `model_validator` enforces valid ranges: both in (0.0, 1.0]

**Decision Engine (`app/services/identity_verification_decision.py`):**
- `evaluate_evidence_detailed()` returns `DecisionResult` with audit metadata
- Metadata: threshold, near_threshold, decision_reason, providers_used, similarity stats
- Near-threshold zone uses average similarity (conservative evaluation)
- Missing evidence never silently treated as PASS or NO_MATCH

**Decision Policy:**
1. No evidence → INCONCLUSIVE
2. Liveness FAIL → NO_MATCH
3. Similarity >= threshold → MATCH (poor quality → INCONCLUSIVE)
4. Similarity >= threshold * near_factor → INCONCLUSIVE
5. Similarity < near zone → NO_MATCH
6. Liveness PASS without similarity → INCONCLUSIVE

**Tests:** 87 tests (`test_decision_engine.py`) — boundary, near-zone, missing evidence, liveness, provider failure, quality, metadata, security invariants, config validation, edge cases, regression

### 8.6 Failure/Security/Review Hardening
**Status: COMPLETE**

Hardened the complete verification pipeline with typed failure categories, provider failure handling, rate limiting, idempotency awareness, human review/override, audit trail, API error sanitization, and security invariants.

**Failure Categories (`app/services/face_verification/failure_categories.py`):**
- 20+ typed failure categories: INVALID_INPUT, PROVIDER_UNAVAILABLE, PROVIDER_TIMEOUT, NO_FACE_DETECTED, MULTIPLE_FACES, RECOGNITION_FAILED, LIVENESS_SPOOF_DETECTED, IDENTITY_MISMATCH, HUMAN_OVERRIDE, etc.
- Clear separation: provider failures ≠ identity mismatch ≠ input validation

**Audit Trail (`app/services/face_verification/audit.py`):**
- `build_override_audit_entry()` / `parse_override_audit_entry()` — JSON-encoded human override records
- `log_verification_event()` — safe verification event logging
- No new DB tables — uses existing `failure_reason` field for override audit

**Human Review (`POST /{attempt_id}/review`):**
- Marks COMPLETED/FAILED attempts as under human review
- Lightweight marker — does NOT change the decision

**Human Override (`POST /{attempt_id}/override`):**
- Overrides decision of COMPLETED/FAILED attempts
- Requires: new_decision + reason; optional: operator_id
- Records full audit; does NOT erase original evidence

**Rate Limiting:**
- Per-attempt: configurable via `FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT` (default 5)
- Global per-minute: configurable via `FACE_VERIFICATION_MAX_CALLS_PER_MINUTE` (default 60)
- Thread-safe via threading.Lock; bounded with eviction

**Security Invariants:**
- Client cannot submit threshold, decision, ALLOW, or DENY
- Override requires non-empty reason; only on terminal states
- Decision engine cannot be bypassed; no composite score leakage
- Provider never directly authorizes

**API Error Sanitization:**
- 404 for not-found, 422 for validation errors
- No filesystem paths, Python tracebacks, or internal module names exposed

**Tests:** 77 tests (`test_phase_8_6_hardening.py`) — failure categories, audit trail, rate limiter, idempotency, human review, human override, security invariants, API sanitization, privacy, config, regression

### 8.7 Admin Face Verification UI
**Status: COMPLETE**

Built the real Admin Face Verification interface with camera capture, real API integration, evidence display, review/override, and audit trail.

**Components:**
- `CameraCapture` — real browser camera via `getUserMedia()`, permission handling, frame capture, retake, cleanup
- `ImageUpload` — file upload for reference/enrollment images, JPEG/PNG only
- `EvidenceDisplay` — signal labels, percentage bars, provider info
- `DecisionDisplay` — exact domain vocabulary, failure reason
- `OverrideDialog` — three-way decision selector, required reason, confirmation
- `VerificationState` — state progress indicator (READY → CAPTURING → SUBMITTING → VERIFYING → EVALUATING → COMPLETED)
- `AuditTimeline` — chronological timeline from attempt timestamps + evidence

**API Client (`lib/iv-api.ts`):**
- Centralized functions: listAttempts, getAttemptContext, startAttempt, verifyFace, evaluateEvidence, reviewAttempt, overrideDecision, cancelAttempt
- Typed errors via `ApiError` class

**Verification Flow:**
1. Upload reference image (enrollment photo)
2. Capture probe image (live camera)
3. Click "Verify Identity"
4. Both images base64-encoded → `POST /{attempt_id}/verify-face`
5. Evidence evaluated → `POST /{attempt_id}/evaluate`
6. UI displays evidence and decision
7. No fake delay, no fake progress, no fake results

**Human Review:** `POST /{attempt_id}/review` with optional notes
**Human Override:** `POST /{attempt_id}/override` with new_decision + reason + audit trail notice

**Privacy:** No persistent image storage, camera tracks cleaned up on unmount, no localStorage/sessionStorage/indexedDB, no console.log

**Tests:** 1103 backend tests passing, 0 failures, 0 errors; 20 frontend routes building

### 8.8 Integration Testing + Final Hardening
**Status: COMPLETE**

Comprehensive integration tests verifying the complete Phase 8 system as ONE integrated system.

**Integration Test Coverage (107 new tests in `test_phase_8_8_integration.py`):**
- Full pipeline E2E (5): service and API flows, MATCH/NO_MATCH/INCONCLUSIVE/liveness
- Provider abstraction (5): deterministic, stub, failure, exception, authorization isolation
- Decision engine (7): boundary values, near-zone, missing evidence, quality, metadata
- Lifecycle state machine (12): all transitions, terminal states, invalid transitions
- Evidence consistency (5): correct attempt, accumulation, sanitization, manual recording
- Repeated verification (3): accumulation, lifecycle intact, decision correctness
- Concurrency (4): verify/review/override race conditions
- Human review (4): flow, evidence preservation, state requirements
- Human override (7): all transitions, audit, evidence, chaining, API
- Audit trail (5): JSON structures, metadata safety, flow audit
- Failure matrix (9): provider failures, validation, wrong method, not found
- Security invariants (7): no client threshold, no provider authorization, no bypass
- Rate limiting (8): attempt/global limits, independent, reset
- API contracts (8): response shapes, errors, filters
- Configuration (9): defaults, validation, retention
- Error sanitization (3): no tracebacks, no paths, safe errors
- Privacy (3): no raw images, no embeddings, retention=0
- Provider failure ≠ false decision (3): unavailable ≠ NO_MATCH, exception ≠ mismatch

**Results:** 1103 tests passing, 0 failures, 0 errors (two runs stable)

### 9.5 Secure Device Communication Foundation
**Status: COMPLETE**

Secure credential provisioning, authentication, and revocation for physical camera devices.

**Credential Design:**
- High-entropy 256-bit secrets via `secrets.token_hex(32)`
- SHA-256 hashed before storage (appropriate for high-entropy bearer tokens)
- Constant-time comparison via `hmac.compare_digest`
- Raw secret returned ONCE at provisioning; never stored/logged/returned again
- Camera identity derived from authenticated credential (no user-supplied camera_id on health endpoint)

**Security Properties:**
- Raw credentials never stored
- Raw credentials never logged
- Hashes never exposed in API responses
- Revoked credentials immediately rejected
- Inactive cameras cannot authenticate
- Credential cannot target another camera
- Errors do not leak secrets
- No biometric/video/student data in device layer
- Status changes only through `record_health_observation()`

**Tests:** 54 tests (38 service + 16 API)

### 9.6 Integration & Hardening
**Status: COMPLETE**

Cross-component integration tests and comprehensive domain audit.

**Audit Verified:**
- All FKs, relationships, cascades, unique constraints, indexes correct
- Camera state invariants: is_active ≠ status, health observation is only path
- Mapping: duplicate prevention, deactivation preserves history
- Credential binding: camera identity derived from credential, no IDOR
- Device health chain: auth → camera → observation → status, future timestamps rejected
- API consistency: correct HTTP codes, thin routes, no secrets in errors
- Security: no hard-coded credentials, no hash leakage, no mass assignment
- Privacy: no biometric/student/video data in Phase 9
- Migrations 016→017→018 correct with downgrades
- Frontend: real API data only, no fake monitoring

**Tests:** 44 cross-component integration tests

---

## Phase 9 — Camera & Entry Point Management

**Status: COMPLETE**

- **9.1** Domain foundation: Camera, EntryPoint, CameraEntryPointMapping models + migration 016 + 53 model tests — COMPLETE
- **9.2** CRUD API: 15 REST endpoints (cameras, entry-points, camera-entry-points) + 42 API integration tests + FK cleanup fixes — COMPLETE
- **9.3** Admin UI: Camera list/create/edit, entry point list/create/edit, mapping list/create/disable, API client, 23 frontend routes — COMPLETE
- **9.4** Device health/status: Health observation boundary, last_seen_at/last_health_check_at/health_reason fields, health API endpoints, 53 tests — COMPLETE
- **9.5** Secure communication: Device credential provisioning, authentication, revocation, SHA-256 hashing, device health API (authenticated), 54 tests, security audit — COMPLETE
- **9.6** Integration/hardening: Cross-component integration tests (44 tests), full domain audit, security/privacy audit — COMPLETE

---

## Phase 10 — Real-Time Examination Entry Verification

**Status: COMPLETE**

- **10.1** Domain model: EntryVerification model, EntryVerificationStatus/HallTicketCheckStatus/IdentityCheckStatus/SeatCheckStatus enums, migration 019, 49 model tests — COMPLETE
- **10.2** Service layer: entry verification service (create, begin_processing, process_hall_ticket_check, process_seat_check, process_identity_check, evaluate_entry, escalate_for_review, resolve_escalation), 71 service tests — COMPLETE
- **10.3** API layer: 10 REST endpoints, 56 API tests — COMPLETE
- **10.4** Admin UI: list page, detail page, create form, workflow actions, escalation/resolve UI — COMPLETE
- **10.5** Integration tests & hardening: 76 cross-component integration tests, state machine hardening, concurrency, data integrity, privacy/security — COMPLETE

---

## Phase 11 — Anti-Proxy Detection

**Status: COMPLETE**

- **11.1** Domain foundation: SecuritySignal + ProxyRiskAssessment models, 3 enums (SecuritySignalType, SignalStrength, RiskLevel), SIGNAL_STRENGTH_DEFAULTS, 6 config settings with validation, migration 020, 47 model tests — COMPLETE
- **11.2** Deterministic signal detection: 14 signal detectors, idempotent detection service, 72 tests, migration 021 — COMPLETE
- **11.3** Risk scoring engine: COMPLETE
- **11.4** API layer: COMPLETE — 5 endpoints, 40 tests
- **11.5** Admin UI: COMPLETE — proxy-risk-api.ts client, risk panel on EV detail page (signals table, assessment summary/history, detect/assess buttons)
- **11.6** Integration tests & hardening: COMPLETE — 86 tests, 2 full suite runs, security/privacy audit passed

---

## Phase 12 — Attendance Management

**Status: IN PROGRESS**

- **12.1** Domain foundation: AttendanceRecord + AttendanceEvent models, 3 enums, migration 022, 42 model tests — COMPLETE
- **12.2** Service layer: 7 service functions (record, get, list, events, manual, summary, history), 55 service tests — COMPLETE
- **12.3** API layer: PLANNED
- **12.4** Admin UI: PLANNED
- **12.5** Integration tests & hardening: PLANNED

---

## Phase 13 — Real-Time Monitoring

**Status: PLANNED**

Focus:
- WebSocket architecture
- Live verification events
- Live entry monitoring
- Dashboard updates
- Real-time operational status

**Dependencies:** Phases 10, 12 (entry events and attendance data must exist to stream).

**New models/migrations likely required:** WebSocket connection management (likely in-memory, not DB). `backend/app/api/v1/ws/` implementation.

**Frontend work expected:** Real-time dashboard components, live status indicators, WebSocket client integration.

**Testing requirements:** Unit tests for WebSocket message handling, connection management. Integration tests for live event streaming.

---

## Phase 14 — Security Event Management

**Status: COMPLETE**

Focus:
- Security event models
- Suspicious activity logging
- Security alerts
- Severity levels
- Investigation workflow
- Immutable audit history

**Dependencies:** Phases 10, 11 (entry verification and anti-proxy systems generate security events).

**New models/migrations likely required:** `SecurityEvent` model with severity enum, immutable append-only design. `SecurityAlert` model.

**Frontend work expected:** Security event dashboard, alert management, investigation workflow pages.

**Testing requirements:** Unit tests for event classification, severity assignment. API tests for security event endpoints.

---

## Phase 15 — Examination Session Management

**Status: COMPLETE**

Focus:
- Examination session lifecycle
- Session start/end
- Gate opening/closing workflow
- Active hall monitoring
- Session-level operational controls
- Session audit trail

**Dependencies:** Phases 9, 10 (cameras and entry verification must exist for session context).

**New models/migrations likely required:** `ExaminationSession` model with lifecycle states. Gate status tracking.

**Frontend work expected:** Session management dashboard, gate control UI, active hall monitoring.

**Testing requirements:** Unit tests for session lifecycle, gate workflow. API tests for session endpoints.

---

## Phase 16 — Attendance & Examination Analytics

**Status: PLANNED**

Focus:
- Attendance analytics
- Verification analytics
- Proxy-risk analytics
- Hall utilization
- Examination statistics
- Admin reporting dashboards

**Dependencies:** Phases 12, 14 (attendance and security event data must exist for analytics).

**New models/migrations likely required:** Possibly materialized views or analytics aggregation tables. No core domain models expected.

**Frontend work expected:** Analytics dashboard pages, charts, export functionality.

**Testing requirements:** Unit tests for aggregation logic. API tests for analytics endpoints.

---

## Phase 17 — ERP Integration

**Status: PLANNED**

Focus:
- ERP adapter abstraction
- Student synchronization
- Subject synchronization
- Examination synchronization
- Registration synchronization
- Attendance export/synchronization
- Retry/error handling

**Dependencies:** Phases 0–4 (all core domain models must exist for sync targets).

**New models/migrations likely required:** `ErpSyncLog` or `ErpSyncJob` model for tracking sync operations. `backend/app/services/erp/adapter.py` implementation.

**Frontend work expected:** ERP sync status dashboard, sync configuration, error review pages.

**Testing requirements:** Unit tests for adapter abstraction, sync logic, error handling. Integration tests with mock ERP responses.

---

## Phase 18 — Cloud Storage & Deployment Storage

**Status: PLANNED**

Focus:
- Cloudinary/storage abstraction
- Production document storage
- Secure file access
- Storage lifecycle
- Local/cloud backend switching
- Migration strategy

**Dependencies:** Phase 3 (storage abstraction ABC must exist).

**New models/migrations likely required:** `backend/app/storage/cloudinary.py` implementation. No new DB models expected.

**Frontend work expected:** None expected — storage is backend infrastructure.

**Testing requirements:** Unit tests for cloud storage backend, switching logic. Integration tests with mock cloud storage.

---

## Phase 19 — Advanced Administration & Access Control

**Status: PLANNED**

Focus:
- Authentication
- Authorization
- Admin roles
- Operator roles
- Reviewer roles
- Permission management
- Protected APIs and frontend routes

**Dependencies:** All prior phases (auth must wrap existing endpoints and pages).

**New models/migrations likely required:** `User`, `Role`, `Permission` models. Session/token management. JWT or session-based auth.

**Frontend work expected:** Login page, role-based navigation, protected route wrappers, user management pages.

**Testing requirements:** Unit tests for auth logic, permission checks. API tests for protected endpoints. Frontend auth flow verification.

---

## Phase 20 — Security Hardening & Compliance

**Status: PLANNED**

Focus:
- API security
- Input validation
- Rate limiting
- Secret management
- Secure file handling
- Audit integrity
- Privacy controls
- Data retention policies
- Security testing

**Dependencies:** Phase 19 (auth must exist before security hardening).

**New models/migrations likely required:** Data retention policy models, rate limit tracking (possibly Redis-backed, not DB).

**Frontend work expected:** Privacy consent flows, data retention configuration UI.

**Testing requirements:** Security-focused unit tests, penetration testing preparation, input validation tests.

---

## Phase 21 — Reliability, Performance & Scale

**Status: PLANNED**

Focus:
- Background processing
- Queue architecture
- Concurrent verification
- Database optimization
- Caching where appropriate
- Large examination batch handling
- Performance testing
- Failure recovery

**Dependencies:** Phases 10–15 (real-time systems must exist to optimize).

**New models/migrations likely required:** Queue/job tracking models. Possibly Redis or Celery integration.

**Frontend work expected:** Performance monitoring dashboard, queue status views.

**Testing requirements:** Load tests, concurrent access tests, failure recovery tests.

---

## Phase 22 — Production Deployment & Observability

**Status: PLANNED**

Focus:
- Production deployment
- Environment configuration
- Logging
- Metrics
- Health checks
- Monitoring
- Error tracking
- Backup/recovery
- CI/CD

**Dependencies:** All prior phases (production deployment wraps the complete system).

**New models/migrations likely required:** None expected — observability is infrastructure, not domain.

**Frontend work expected:** Health check endpoints, monitoring dashboards.

**Testing requirements:** Deployment tests, health check verification, backup/recovery drills.

---

## Phase 23 — Final ExamGuard Platform Integration

**Status: PLANNED**

Focus:
- End-to-end integration
- Complete examination workflow
- Entry verification
- Anti-proxy
- Attendance
- Security monitoring
- ERP integration
- Production readiness
- End-to-end testing
- Final documentation

**Dependencies:** All prior phases (this is the integration and finalization phase).

**New models/migrations likely required:** None expected — integration phase.

**Frontend work expected:** End-to-end workflow testing, final UI polish.

**Testing requirements:** Full end-to-end test suite, production readiness verification, final documentation review.

---

## Roadmap Rules

1. Phases 0–15 are COMPLETE.
2. Phases 16–23 are PLANNED.
4. Do not mark future phases complete.
5. Do not implement future phases.
6. Each future phase should eventually be broken into smaller implementation steps before coding begins.
7. Future implementation must proceed sequentially unless the architecture explicitly justifies another order.
8. AI systems provide evidence/perception; business logic makes authorization and operational decisions.
9. Never hard-code production data or thresholds.
10. Database changes require Alembic migrations.
11. Preserve auditability and security throughout the project.
12. Do not introduce paid/cloud AI services unless explicitly planned and approved.
13. Face/biometric functionality must have privacy, security, fallback, and human-review considerations.
14. Never destructively reset production-style databases.
15. Never weaken or delete tests to make a feature pass.

---

## Current Project State

- **Current phase:** Phase 16 — Attendance & Examination Analytics (COMPLETE)
- **Completed phases:** 0–16
- **Current tests:** 2466 passing, 0 failures, 0 errors
- **Frontend pages:** 32 (all building successfully)
- **Design system:** Minimalist monochrome (Playfair Display / Source Serif 4 / JetBrains Mono), zero border-radius, no neon colors
- **Next step:** Phase 17 — ERP Integration
- **Provider architecture:** `app/services/face_verification/` with Protocol, DeterministicProvider, factory
- **Identity verification API:** `POST /{attempt_id}/verify-face` endpoint for face verification trigger
- **Camera infrastructure:** Complete — Camera, EntryPoint, Mapping, Credential, Health Observation, Device Auth API

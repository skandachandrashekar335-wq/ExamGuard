# ExamGuard Progress

## Current State

- **Phase:** 8 IN PROGRESS (8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7 complete, 8.8 future)
- **Tests:** 996 passing, 0 failures, 0 errors
- **Frontend:** 20 pages building successfully
- **Design system:** Minimalist monochrome (Playfair Display / Source Serif 4 / JetBrains Mono)

---

## Phase 8.1 — Face Verification Architecture & Provider Abstraction

**Status: COMPLETE**

- `FaceVerificationProvider` Protocol with `verify()`, `health_check()`, `get_capabilities()`
- Types: `FaceVerificationRequest`, `FaceVerificationResult`, `FaceVerificationError`, frozen dataclasses
- `DeterministicProvider` for testing
- Factory: `get_face_verification_provider()` reads config
- Config: `FACE_VERIFICATION_PROVIDER`, retention days = 0
- 28 tests
- Privacy/terms pages fixed for monochrome

## Phase 8.2 — Wire Face Verification Provider Into Identity Verification Service

**Status: COMPLETE**

### Implementation

- `verify_face()` service function in `app/services/identity_verification.py`
  - Validates attempt eligibility (CREATED/IN_PROGRESS + FACE method)
  - Gets provider via factory, checks health
  - Calls `provider.verify()`, maps result → evidence records
  - Provider errors → `fail_attempt()` (not evidence)
  - Persists evidence via existing `record_evidence()`
- `POST /{attempt_id}/verify-face` API endpoint in `app/api/v1/identity_verification.py`
  - Accepts base64-encoded reference/probe images
  - Returns `VerifyFaceResponse` (attempt_id + evidence list)
- `VerifyFaceRequest` and `VerifyFaceResponse` schemas

### Evidence Mapping

| Provider Result | Evidence Signal Type | Evidence Signal Value | Confidence |
|---|---|---|---|
| `identity_match_score` | `similarity_score` | str(score) | score |
| `liveness_score` | `liveness_score` | str(score) | score |
| `liveness_passed` | `liveness` | `PASS`/`FAIL` | — |
| `image_quality_score` | `image_quality` | `GOOD`/`POOR` | score |

### Architecture

```
FACE INPUT
    ↓
FaceVerificationProvider (Protocol)
    ↓
FaceVerificationResult (evidence signals)
    ↓
IdentityVerificationEvidence (persisted)
    ↓
Existing Decision Engine (evaluate_evidence)
```

Provider NEVER directly authorizes/denies. Evidence ≠ Decision.

### Tests

35 integration tests (`test_verify_face_integration.py`):
- Happy path (5): evidence records returned, persisted, attempt stays in progress, provider info present, works on CREATED attempts
- Evidence mapping (8): similarity_score, liveness_score, liveness PASS/FAIL, image_quality GOOD/POOR, none scores → no evidence, JSON details
- Failure semantics (9): attempt not found, wrong status, wrong method, empty images, provider unavailable fails attempt, provider error fails attempt
- Sensitive data (2): no raw images in evidence, no raw images in provider result
- Evidence ≠ decision (3): verify_face does not complete attempt, continuous values, decision engine processes evidence
- Multiple calls (1): evidence accumulates
- API happy path (2): returns 201, correct response fields
- API errors (5): invalid base64, not found, wrong status, wrong method, provider unavailable

## Phase 8.2 Hardening — Test Cleanup Fix

**Status: COMPLETE**

### Root Cause

FK ordering issue in test cleanup fixtures. `IdentityVerificationAttempt` has a foreign key to `ExamRegistration`:

```
IdentityVerificationEvidence → IdentityVerificationAttempt → ExamRegistration
```

`test_batch_verification.py` and `test_dashboard.py` cleanup fixtures deleted `ExamRegistration` before `IdentityVerificationAttempt`, causing FK violations (23 errors).

### Fix

Added `IdentityVerificationEvidence` and `IdentityVerificationAttempt` cleanup **before** `ExamRegistration` deletion in:

- `tests/test_batch_verification.py`: added imports + 2 cleanup lines
- `tests/test_dashboard.py`: added imports + 2 cleanup lines

### Result

750 passed, 0 failures, 0 errors (full backend suite).

---

## Phase 8.3 — UniFace Provider Integration

**Status: COMPLETE**

### Implementation

UniFace (yakhyo/uniface v4.0.0) provides real face detection, recognition, and anti-spoofing via ONNX Runtime — fully local, no external API calls.

**Provider** (`backend/app/services/face_verification/providers/uniface_provider.py`):
- `UniFaceProvider` class implementing `FaceVerificationProvider` Protocol
- Lazy initialization: models downloaded on first `verify()` call (~30 MB total)
- `_load_uniface_modules()` method for clean testability
- Pipeline: decode → detect (RetinaFace) → recognize (ArcFace) → anti-spoof (MiniFASNet) → evidence
- Anti-spoofing failure is non-fatal: identity match still returned
- Models: RetinaFace detection, ArcFace recognition, MiniFASNet anti-spoofing
- All processing local via ONNX Runtime

**Config**:
- `FACE_VERIFICATION_PROVIDER="uniface"` activates the real provider
- Default remains `"deterministic"` for development/testing

**Dependency**:
- `uniface[cpu]>=4.0.0` added as optional dependency in `pyproject.toml`
- Onnxruntime 1.29.0 with cp314 wheels for Python 3.14 on Windows x86-64

### Architecture

```
FaceVerificationRequest (image bytes)
    ↓
UniFaceProvider._load_uniface_modules() → RetinaFace, ArcFace, MiniFASNet
    ↓
RetinaFace.detect() → face bounding boxes
    ↓
ArcFace.get_normalized_embedding() → L2-normalized embeddings
    ↓
np.dot(ref_emb, probe_emb) → identity_match_score
    ↓
MiniFASNet.predict() → liveness evidence
    ↓
FaceVerificationResult (evidence signals)
```

### Tests

27 tests (`test_uniface_provider.py`):
- Provider instantiation (3): import, capabilities, anti_spoofing disabled
- Verification happy path (6): evidence result, cosine similarity, liveness, spoof detection, disabled anti-spoofing, metadata
- Detection errors (4): no face in reference/probe, multiple faces in reference/probe
- Invalid input (2): invalid reference/probe images
- Privacy (3): no raw images in result/error, no embeddings in metadata
- No decisions (2): no decision field, continuous scores
- Health check (2): unavailable without init, success
- Factory selection (2): creates uniface, still creates deterministic
- Deterministic backward compat (2): configured scores, capabilities
- Anti-spoofing non-fatal (1): exception still returns identity match

### Files Changed in Phase 8.3

| File | Change |
|---|---|
| `backend/app/services/face_verification/providers/uniface_provider.py` | New UniFace provider implementation |
| `backend/app/services/face_verification/factory.py` | Added "uniface" case to factory |
| `backend/pyproject.toml` | Added `uniface[cpu]>=4.0.0` optional dependency |
| `backend/tests/test_uniface_provider.py` | 27 new tests with mocked UniFace |
| `docs/progress.md` | Updated |

---

## Phase 8.4 — Real Face Verification Pipeline

**Status: COMPLETE**

### Implementation

End-to-end face verification pipeline with robust input validation, real provider-derived evidence, and comprehensive privacy/security controls.

**Input Validation (defense-in-depth at 3 layers):**

1. **Pydantic schema** (`VerifyFaceRequest`):
   - `model_validator` enforces valid base64 encoding at schema level
   - Validates decoded bytes are non-empty
   - Validates format fields against allowed values (image/jpeg, image/png)

2. **API endpoint** (`POST /{attempt_id}/verify-face`):
   - `base64.b64decode(..., validate=True)` for strict base64 validation
   - Separate validation for reference and probe images (clear error messages)
   - Image validation via `validate_image_bytes()` before calling service

3. **Service layer** (`verify_face()`):
   - Defense-in-depth: validates image bytes even though API already validated
   - Catches `ImageValidationError` and wraps in `ValueError`

**Image Validation Helpers** (`app/services/face_verification/validation.py`):
- `validate_image_bytes()`: Full validation pipeline
- `detect_image_format()`: Magic byte detection (JPEG/PNG)
- `decode_image_safely()`: Validated decode with dimension checks
- Magic bytes: JPEG (`\xff\xd8\xff`), PNG (`\x89PNG`)
- Size limits: configurable via `FACE_VERIFICATION_MAX_IMAGE_SIZE_MB` (default 5MB)
- Dimension limits: min 16px, max 16384px per side
- Decompression bomb protection: max total pixels
- Corrupted image detection via OpenCV decode

**Face Detection Behavior:**
- 0 faces → `NO_FACE_DETECTED` (typed error, provider fails)
- 1 face → proceed with recognition
- >1 faces → `MULTIPLE_FACES_DETECTED` (typed error, provider fails)
- Never silently selects first/ largest face
- Ambiguity remains explicit

**Face Recognition Behavior:**
- ArcFace embeddings via UniFace
- Cosine similarity computed from L2-normalized embeddings
- Result mapped to `similarity_score` evidence signal
- No composite confidence scores
- Independent signals preserved

**Liveness/Anti-Spoofing Behavior:**
- MiniFASNet anti-spoofing on probe image
- Single-image classification (real/fake + confidence)
- Failure is non-fatal: identity match still returned
- When disabled: liveness signals are None (not fabricated)
- Limitation: single-image anti-spoofing is not true liveness detection

**Privacy Decisions:**
- `FACE_VERIFICATION_IMAGE_RETENTION_DAYS = 0` (default)
- No raw images stored, logged, or returned
- No embeddings stored, logged, or returned
- No biometric data in evidence metadata
- Transient in-memory processing only
- Provider errors sanitized at API boundary

**Security Decisions:**
- Typed error categories (no raw exception leakage to API)
- Image size limits enforced (configurable)
- Decompression bomb protection (max dimensions/pixels)
- Corrupted image detection (OpenCV decode validation)
- No model weights committed to Git
- No secrets in code

**Resource/Model Handling:**
- UniFace models lazily initialized on first `verify()` call
- Models cached in provider instance (not per-request)
- Initialization failure captured and re-raised
- No unbounded caches
- CPU-only operation (no CUDA dependency)

**Reference/Probe Semantics:**
- Reference image = enrolled/reference identity (provided by caller)
- Probe image = current verification input (provided by caller)
- Both images validated independently
- Provider compares reference vs probe explicitly

### Files Changed in Phase 8.4

| File | Change |
|---|---|
| `backend/app/services/face_verification/validation.py` | New image validation helpers (magic bytes, size, dimensions, corruption) |
| `backend/app/api/v1/identity_verification.py` | Strengthened verify-face endpoint (Pydantic validator, base64 validation, image validation) |
| `backend/app/services/identity_verification.py` | Added defense-in-depth image validation in verify_face() |
| `backend/tests/test_face_verification_pipeline.py` | 82 new comprehensive pipeline tests |
| `backend/tests/test_verify_face_integration.py` | Updated test images to valid JPEGs |
| `docs/progress.md` | Updated |

### Tests

82 tests (`test_face_verification_pipeline.py`):
- Image validation helpers (15): valid JPEG/PNG, empty, oversized, custom size, unsupported format, corrupted, too small, format detection, decode safety
- API input validation (20): missing fields, invalid base64, empty base64, corrupted, oversized, unsupported format, wrong status, wrong method, valid JPEG/PNG
- Service-level validation (9): empty images, corrupted, wrong status, wrong method
- Face detection (5): no face reference/probe, multiple faces reference/probe, exactly one face
- Face recognition (3): cosine similarity, recognition failure, exception sanitization
- Liveness (4): anti-spoofing, spoof detected, disabled, failure non-fatal
- Evidence mapping (7): similarity_score, liveness_score, liveness PASS/FAIL, none scores, independent signals, no composite
- Privacy (5): no raw images, no embeddings, provider result safe, error safe, metadata safe
- Lifecycle (4): does not complete attempt, multiple calls accumulate, provider failure, provider error
- Provider abstraction (4): deterministic works, uniface selected, deterministic default, capabilities
- Decision separation (3): no decision field, decision engine processes evidence, continuous signals
- Error types (3): all types exist, frozen, wrapping
- API happy path (2): returns 201, correct fields

---

## Phase 8.5 — Threshold + Decision Integration

**Status: COMPLETE**

### Implementation

Enhanced the decision engine with configurable thresholds, near-threshold zone, decision metadata for audit trail, and comprehensive configuration validation.

**Configuration (`app/core/config.py`):**
- `IDENTITY_VERIFICATION_MATCH_THRESHOLD: float = 0.85` — similarity score threshold
- `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR: float = 0.7` — near-zone factor (threshold * factor = near-zone lower bound)
- `IDENTITY_VERIFICATION_POLICY_VERSION: str = "1.0"` — policy version for audit trail
- `model_validator` enforces valid ranges: both must be in (0.0, 1.0]

**Decision Engine (`app/services/identity_verification_decision.py`):**
- Refactored `evaluate_evidence()` to use configurable thresholds from settings
- New `evaluate_evidence_detailed()` returns `DecisionResult` with audit metadata
- `DecisionResult` dataclass: decision, reasoning, policy_version, metadata
- Metadata includes: threshold, near_threshold, decision_reason, providers_used, similarity counts/stats
- Decision logic preserved: liveness fail → NO_MATCH, high similarity → MATCH, near zone → INCONCLUSIVE, low similarity → NO_MATCH
- Near-threshold zone uses average similarity (not max) for more conservative evaluation
- Missing evidence never silently treated as PASS or NO_MATCH

**Decision Policy:**
1. No evidence → INCONCLUSIVE
2. Liveness FAIL → NO_MATCH (possible spoof)
3. Similarity >= threshold → MATCH (unless poor quality → INCONCLUSIVE)
4. Similarity >= threshold * near_factor → INCONCLUSIVE (near zone)
5. Similarity < near zone → NO_MATCH
6. Liveness PASS without similarity → INCONCLUSIVE
7. Insufficient evidence → INCONCLUSIVE

### Tests

87 tests (`test_decision_engine.py`):
- Boundary testing (11): exact threshold, just above, just below, zero, one, half-threshold
- Near-threshold zone (9): default factor, below zone, at boundary, configurable factor, average similarity
- Missing evidence (10): no evidence, similarity only, liveness only, quality only, combinations
- Liveness policy (7): fail overrides all similarities, spoof_detected, lowercase, false
- Provider failure mapping (3): provider names in metadata, multiple providers, failure not silently converted
- Quality policy (5): poor+high sim, poor+low sim, good+high sim, unacceptable, low quality
- Decision metadata (13): threshold, near_threshold, policy_version, counts, max/avg similarity, decision_reason, providers_used
- Security invariants (5): client cannot submit threshold, no evidence → INCONCLUSIVE, liveness fail → NO_MATCH, no composite score leakage, provider never directly authorizes
- Config validation (11): valid defaults, zero/negative/above-one raise errors, boundary values valid
- Evidence edge cases (6): confidence preferred over signal_value, fallback, invalid/out-of-range values
- Regression (7): all existing decision engine behavior preserved

### Files Changed in Phase 8.5

| File | Change |
|---|---|
| `backend/app/core/config.py` | Added `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR`, `IDENTITY_VERIFICATION_POLICY_VERSION`, `model_validator` for threshold validation |
| `backend/app/services/identity_verification_decision.py` | Enhanced with configurable thresholds, `DecisionResult` dataclass, `evaluate_evidence_detailed()`, audit metadata |
| `backend/tests/test_decision_engine.py` | New comprehensive test suite (87 tests) |

---

## Phase 8.6 — Failure/Security/Review Hardening

**Status: COMPLETE**

### Implementation

Hardened the complete verification pipeline with typed failure categories, provider failure handling, rate limiting, idempotency awareness, human review/override, audit trail, API error sanitization, and security invariants.

**Failure Categories (`app/services/face_verification/failure_categories.py`):**
- 20+ typed failure categories: INVALID_INPUT, PROVIDER_UNAVAILABLE, PROVIDER_TIMEOUT, NO_FACE_DETECTED, MULTIPLE_FACES, RECOGNITION_FAILED, LIVENESS_SPOOF_DETECTED, IDENTITY_MISMATCH, HUMAN_OVERRIDE, etc.
- Categorization functions: `is_provider_failure()`, `is_input_validation()`, `is_face_detection()`
- Provider error mapping: `categorize_provider_error()` maps FaceVerificationErrorType → FailureCategory
- Clear separation: provider failures ≠ identity mismatch ≠ input validation

**Audit Trail (`app/services/face_verification/audit.py`):**
- `build_override_audit_entry()`: JSON-encoded audit entries for human overrides
- `parse_override_audit_entry()`: Parse override entries from failure_reason field
- `build_verification_audit_metadata()`: Safe audit metadata for structured logging
- `log_verification_event()`: Safe verification event logging
- No new DB tables — uses existing `failure_reason` field for override audit

**Human Review (`POST /{attempt_id}/review`):**
- Marks COMPLETED/FAILED attempts as under human review
- Lightweight marker — does NOT change the decision
- Stores review notes and timestamp in failure_reason field

**Human Override (`POST /{attempt_id}/override`):**
- Overrides decision of COMPLETED/FAILED attempts
- Requires: new_decision (MATCH/NO_MATCH/INCONCLUSIVE) + reason
- Optional: operator_id for audit trail
- Records full audit: original_decision → override_decision → reason → timestamp
- Does NOT erase original evidence
- Original automated result preserved in audit trail

**Rate Limiting (`_RateLimiter` in identity_verification.py):**
- Per-attempt limit: configurable via `FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT` (default 5)
- Global per-minute limit: configurable via `FACE_VERIFICATION_MAX_CALLS_PER_MINUTE` (default 60)
- Thread-safe via threading.Lock
- Bounded: max 10,000 tracked attempt IDs with eviction
- Rate limit exceeded → clear error message

**Provider Failure Handling:**
- Provider errors now categorized with FailureCategory
- Audit events logged for all provider failures
- Unexpected exceptions caught and sanitized (no stack traces to clients)
- Provider failure → fail_attempt() with categorized reason

**Idempotency:**
- Repeated verify_face calls on same attempt: ALLOWED (evidence accumulates by design)
- Status checks prevent calls on completed/failed/cancelled attempts
- Decision engine processes ALL evidence — no contradictory records possible

**Security Invariants:**
- Client cannot submit threshold, decision, ALLOW, or DENY
- Override requires non-empty reason
- Override only on terminal states (COMPLETED/FAILED)
- Decision engine cannot be bypassed
- Liveness failure always produces NO_MATCH
- No composite score leakage
- Provider never directly authorizes

**API Error Sanitization:**
- 404 for not-found attempts
- 422 for validation errors, wrong status, wrong method, invalid decisions
- No filesystem paths, Python tracebacks, or internal module names exposed
- Safe error categories preserved for legitimate clients

**Privacy:**
- No raw images stored/logged/returned
- No embeddings stored/logged
- No biometric data in audit metadata
- `FACE_VERIFICATION_IMAGE_RETENTION_DAYS = 0` maintained
- Override audit contains only safe operational data

**Config (`app/core/config.py`):**
- `FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT: int = 5`
- `FACE_VERIFICATION_MAX_CALLS_PER_MINUTE: int = 60`

### Files Changed in Phase 8.6

| File | Change |
|---|---|
| `backend/app/services/face_verification/failure_categories.py` | New: typed failure category enum and classification functions |
| `backend/app/services/face_verification/audit.py` | New: audit trail helpers (override entries, event logging, safe metadata) |
| `backend/app/services/identity_verification.py` | Added: review_attempt(), override_decision(), rate limiter, idempotency awareness, typed provider error handling |
| `backend/app/api/v1/identity_verification.py` | Added: POST /review, POST /override endpoints, ReviewRequest/OverrideRequest schemas |
| `backend/app/core/config.py` | Added: rate limiting config settings |
| `backend/tests/test_phase_8_6_hardening.py` | New: 77 comprehensive tests |
| `backend/tests/test_verification.py` | Fixed: FK ordering in cleanup fixture (added IdentityVerificationEvidence/Attempt cleanup) |

### Tests

77 tests (`test_phase_8_6_hardening.py`):
- Failure categories (10): all categories exist, provider/input/detection classification, error mapping
- Audit trail (10): build/parse override entries, audit metadata, edge cases
- Rate limiter (9): attempt limits, global limits, unlimited, independent, eviction, reset
- Idempotency (4): no evidence, existing similarity/liveness, non-face evidence
- Human review (6): completed/failed review, wrong status rejection, nonexistent, notes
- Human override (12): match→no_match, no_match→match, inconclusive, preserves evidence, wrong status, invalid decision, empty reason, nonexistent, failed attempt, multiple overrides
- Security invariants (8): no threshold submission, requires reason, no ALLOW/DENY, engine not bypassed, liveness always NO_MATCH, no composite leakage, provider never authorizes
- API sanitization (3): 404 for not found, 422 for invalid decision, 404 for review
- Privacy (4): no raw images, no embeddings, no biometric data, retention=0
- Config (2): default rate limits, zero means unlimited
- Regression (10): all existing decision engine and lifecycle behavior preserved

---

## Phase 8.7 — Admin Face Verification UI

**Status: COMPLETE**

Built the real Admin Face Verification interface — camera capture, real API integration, evidence display, review/override, and audit trail.

**Architecture:**
- Centralized API client (`lib/iv-api.ts`) with typed functions for all endpoints
- Shared TypeScript types (`lib/types.ts`) matching backend schemas exactly
- Component-based UI: CameraCapture, ImageUpload, EvidenceDisplay, DecisionDisplay, OverrideDialog, VerificationState, AuditTimeline

**Camera Capture (`components/CameraCapture.tsx`):**
- Real browser camera via `navigator.mediaDevices.getUserMedia()`
- States: idle → requesting → active → captured
- Permission handling: denied, unavailable, unsupported browser
- Frame capture via canvas API
- Retake support
- Proper cleanup: tracks stopped on unmount, on retake, on completion
- No persistent image storage

**Image Upload (`components/ImageUpload.tsx`):**
- File upload for reference/enrollment image
- Accepts JPEG/PNG only
- Preview via URL.createObjectURL (revoked on clear)
- No persistent storage

**Verification Flow:**
1. Operator uploads reference image (enrollment photo)
2. Operator captures probe image (live camera)
3. Operator clicks "Verify Identity"
4. Both images base64-encoded and sent to `POST /{attempt_id}/verify-face`
5. Evidence evaluated via `POST /{attempt_id}/evaluate`
6. UI displays evidence and decision
7. No fake delay, no fake progress, no fake results

**List Page (`identity-verifications/page.tsx`):**
- Upgraded with shared API client
- Filters: status, decision, student ID
- Loading state, error state, empty state
- Monochrome design tokens (no colored badges)
- Paginated results

**Detail Workspace (`identity-verifications/[id]/page.tsx`):**
- Left column: Camera, Reference Image, Verification State, Evidence, Decision
- Right column: Candidate context, Exam context, Attempt details, Actions, Audit Trail
- All data from backend API — no fabricated fields
- "NOT AVAILABLE" for missing context

**Human Review UI:**
- "Request Review" button on terminal states (COMPLETED/FAILED)
- Optional notes textarea
- Calls `POST /{attempt_id}/review`
- Refreshes attempt state after review

**Human Override UI:**
- "Override Decision" button on terminal states
- Three-way decision selector: MATCH, NO_MATCH, INCONCLUSIVE
- Required reason textarea
- Confirmation dialog with audit trail notice
- Calls `POST /{attempt_id}/override`
- Refreshes attempt state after override

**Audit Trail:**
- Timeline display from attempt timestamps + evidence records
- Override entries parsed from failure_reason JSON
- Chronological ordering
- No raw images, embeddings, or biometric data displayed

**Evidence Display:**
- Signal types with labels: similarity_score, liveness_score, liveness_signal, image_quality
- Percentage bars for numeric scores
- Provider info and confidence values
- Details text when available

**Decision Display:**
- Exact domain vocabulary: MATCH, NO_MATCH, INCONCLUSIVE, PENDING
- Failure reason displayed when present
- No frontend-computed confidence scores

**Security/Privacy:**
- No localStorage/sessionStorage/indexedDB usage
- No console.log/debug/error
- No persistent image storage
- Camera streams properly cleaned up on unmount
- No hard-coded thresholds used as authority
- Base64 usage transient for API requests only
- All decisions from backend

### Files Changed in Phase 8.7

| File | Change |
|---|---|
| `frontend/src/lib/types.ts` | New: shared TypeScript types for API responses |
| `frontend/src/lib/iv-api.ts` | New: centralized API client for identity verification |
| `frontend/src/components/CameraCapture.tsx` | New: real browser camera capture component |
| `frontend/src/components/ImageUpload.tsx` | New: file upload for reference images |
| `frontend/src/components/EvidenceDisplay.tsx` | New: evidence signals display |
| `frontend/src/components/DecisionDisplay.tsx` | New: decision display |
| `frontend/src/components/OverrideDialog.tsx` | New: override confirmation dialog |
| `frontend/src/components/VerificationState.tsx` | New: verification state progress indicator |
| `frontend/src/components/AuditTimeline.tsx` | New: audit trail timeline |
| `frontend/src/app/identity-verifications/page.tsx` | Upgraded: shared API, monochrome design, empty/loading states |
| `frontend/src/app/identity-verifications/[id]/page.tsx` | Rebuilt: full verification workspace with camera, review, override |

---

## Remaining Phase 8 Work

- **8.8 Integration testing/hardening** (FUTURE): End-to-end testing, production readiness

## Files Changed in Phase 8.2

| File | Change |
|---|---|
| `backend/app/services/identity_verification.py` | Added `verify_face()` function |
| `backend/app/api/v1/identity_verification.py` | Added `POST /{attempt_id}/verify-face` endpoint, `VerifyFaceRequest` |
| `backend/app/schemas/identity_verification.py` | Added `VerifyFaceRequest`, `VerifyFaceResponse` |
| `backend/tests/test_verify_face_integration.py` | 35 new integration tests |
| `backend/tests/test_batch_verification.py` | Fixed FK cleanup ordering |
| `backend/tests/test_dashboard.py` | Fixed FK cleanup ordering |
| `docs/roadmap.md` | Updated Phase 8.2 status |
| `docs/progress.md` | Created |

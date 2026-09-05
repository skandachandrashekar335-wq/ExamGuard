# ExamGuard Progress

## Current State

- **Phase:** 8 COMPLETE, 9 COMPLETE, 10 COMPLETE, 11 COMPLETE, 12 COMPLETE, **13.1 COMPLETE, 13.2 COMPLETE, 13.3 COMPLETE, 13.4 COMPLETE, 13.5 COMPLETE, 13.6 COMPLETE, 13.7 IN PROGRESS**
- **Tests:** 2346 passing, 0 failures, 0 errors
- **Frontend:** 28 pages building successfully
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

## Phase 8.8 — Integration Testing + Final Hardening

**Status: COMPLETE**

Comprehensive integration tests verifying the complete Phase 8 system works correctly as ONE integrated system.

**Integration Test Coverage (`test_phase_8_8_integration.py` — 107 new tests):**

1. **Full Pipeline E2E** (5 tests): Complete flow from creation through face verification to decision, via both service layer and HTTP API. Tests MATCH, NO_MATCH, INCONCLUSIVE, and liveness failure paths.

2. **Provider Abstraction** (5 tests): DeterministicProvider through API, custom stub provider through service, provider failure/exception handling, authorization field isolation.

3. **Decision Engine Integration** (7 tests): High/low/near-threshold similarity, missing evidence, liveness fail override, poor quality, detailed metadata.

4. **Lifecycle State Machine** (12 tests): All valid transitions, cancel/fail from CREATED, cannot start/complete/fail/cancel twice, cannot verify after terminal states, cannot review/override from non-terminal states, completed_at verification.

5. **Evidence Consistency** (5 tests): Evidence belongs to correct attempt, accumulates across multiple calls, metadata sanitized, manual recording, cannot record on completed.

6. **Repeated Verification** (3 tests): Three calls accumulate, lifecycle intact, decision correct after accumulation.

7. **Concurrency** (4 tests): Concurrent verify calls, concurrent review requests, concurrent overrides, verify-then-cancel.

8. **Human Review** (4 tests): Review flow, evidence preservation, review on failed attempts, review without notes.

9. **Human Override** (7 tests): All 6 transition directions, audit entry creation, evidence preservation, reason requirement, terminal state requirement, multiple override chaining, API integration.

10. **Audit Trail** (5 tests): Override JSON structure, review JSON structure, metadata safety, non-override parsing, full flow audit.

11. **Failure Matrix** (9 tests): Provider unavailable/exception, empty images, wrong method, attempt not found, invalid decision, empty failure reason, provider failure ≠ identity mismatch, insufficient evidence ≠ MATCH.

12. **Security Invariants** (7 tests): Client cannot set threshold, cannot force decision via evidence, provider cannot authorize, VerifyFaceRequest schema validation, decision engine cannot be bypassed, liveness fail always NO_MATCH, no composite score leakage.

13. **Rate Limiting** (8 tests): Attempt limits within/at/over, global limits within/at, zero means unlimited, independent attempts, reset.

14. **API Contract** (8 tests): List, context, verify-face, complete, override response shapes, 404, 422, filter parameters.

15. **Configuration** (9 tests): Default values, retention zero, rate limits, invalid threshold/factor rejection.

16. **Error Sanitization** (3 tests): No filesystem paths, no tracebacks, safe validation errors.

17. **Privacy** (3 tests): No raw images in API responses, no images in context, config retention zero.

18. **Provider Failure ≠ False Decision** (3 tests): Unavailable not NO_MATCH, exception not mismatch, empty evidence not MATCH.

**Issues Found and Verified:**
- Rate limiter is a module-level singleton (in-memory) — appropriate for single-process, would need shared limiter for multi-worker deployment
- `review_attempt` overwrites `failure_reason` (review/override audit are sequential, not cumulative)
- Double validation in verify-face endpoint (defense-in-depth by design)
- Image quality threshold hardcoded at 0.5 (not configurable)

**Tests:** 1103 total (996 previous + 107 new), 0 failures, 0 errors
**Frontend:** 20 routes building successfully
**Repeatability:** Two full suite runs, both 1103 passed

### Files Changed in Phase 8.8

| File | Change |
|---|---|
| `backend/tests/test_phase_8_8_integration.py` | New: 107 integration tests covering full pipeline, providers, decision engine, lifecycle, evidence, concurrency, review, override, audit, failures, security, rate limiting, API contracts, config, privacy |

---

## Phase 8 — COMPLETE

All sub-phases complete:
- 8.1 Provider Architecture ✅
- 8.2 Service Integration ✅
- 8.3 UniFace Provider ✅
- 8.4 Real Face Verification Pipeline ✅
- 8.5 Threshold + Decision Integration ✅
- 8.6 Failure/Security/Review Hardening ✅
- 8.7 Admin Face Verification UI ✅
- 8.8 Integration Testing + Final Hardening ✅

**Total Phase 8 Tests:** 1103 backend + 20 frontend routes

---

## Phase 9.1 — Camera & Entry Point Domain Foundation

**Status: COMPLETE**

Established the physical infrastructure domain with Camera, EntryPoint, and CameraEntryPointMapping models.

**Models:**
- `Camera` — physical/institutional camera device (name, device_identifier, camera_type, manufacturer, model_name, resolution, exam_hall FK, status, connection_info, is_active)
- `EntryPoint` — physical examination entry gate (name, code, description, location_detail, exam_hall FK, is_active)
- `CameraEntryPointMapping` — camera↔entry point relationship (camera FK, entry point FK, is_enabled)

**Design Decisions:**
- Camera ↔ ExamHall: many-to-one (many cameras per hall, hall FK on camera)
- EntryPoint ↔ ExamHall: many-to-one (many entry points per hall, hall FK on entry point)
- Camera ↔ EntryPoint: many-to-many via mapping table (unique constraint prevents duplicate active mappings)
- Deactivation: `is_active` soft-delete pattern (consistent with existing models)
- Status: `CameraStatus` enum (ONLINE, OFFLINE, UNKNOWN, DISABLED)
- No biometric data, no credentials, no secrets in any model
- Connection metadata stored as plain text (IP/URL only, no credentials)

**Migration:** 016 (`016_create_camera_entry_point_tables.py`)

**Files:**
- `backend/app/models/camera.py` — Camera model + CameraStatus enum
- `backend/app/models/entry_point.py` — EntryPoint model
- `backend/app/models/camera_entry_point.py` — CameraEntryPointMapping model
- `backend/app/models/exam_hall.py` — Added cameras and entry_points relationships
- `backend/app/models/__init__.py` — Registered new models
- `backend/alembic/versions/016_create_camera_entry_point_tables.py` — Migration
- `backend/tests/test_phase_9_1_models.py` — 53 model tests

**Tests:** 1156 total (1103 previous + 53 new), 0 failures, 0 errors

---

## Phase 9.2 — Camera & Entry Point CRUD API

**Status: COMPLETE**

Full REST API for managing cameras, entry points, and camera-to-entry-point mappings.

**New Files:**
- `backend/app/schemas/camera.py` — CameraCreate, CameraUpdate, CameraResponse, CameraListResponse
- `backend/app/schemas/entry_point.py` — EntryPointCreate, EntryPointUpdate, EntryPointResponse, EntryPointListResponse
- `backend/app/schemas/camera_entry_point.py` — CameraEntryPointMappingCreate, CameraEntryPointMappingUpdate, CameraEntryPointMappingResponse, CameraEntryPointMappingListResponse
- `backend/app/services/camera.py` — CRUD operations with duplicate detection, search, pagination
- `backend/app/services/entry_point.py` — CRUD operations with code normalization, search, pagination
- `backend/app/services/camera_entry_point.py` — CRUD operations with duplicate mapping prevention
- `backend/app/api/v1/cameras.py` — REST endpoints (POST, GET list, GET one, PATCH, DELETE)
- `backend/app/api/v1/entry_points.py` — REST endpoints (POST, GET list, GET one, PATCH, DELETE)
- `backend/app/api/v1/camera_entry_points.py` — REST endpoints (POST, GET list, GET one, PATCH, DELETE)
- `backend/tests/test_phase_9_2_api.py` — 42 API integration tests

**API Endpoints:**
- `POST /api/v1/cameras` — Create camera (201)
- `GET /api/v1/cameras` — List cameras (paginated, searchable, filterable by hall/status)
- `GET /api/v1/cameras/{id}` — Get camera (404 if not found)
- `PATCH /api/v1/cameras/{id}` — Update camera (404/409)
- `DELETE /api/v1/cameras/{id}` — Soft-delete camera (404)
- `POST /api/v1/entry-points` — Create entry point (201, code auto-uppercased)
- `GET /api/v1/entry-points` — List entry points (paginated, searchable)
- `GET /api/v1/entry-points/{id}` — Get entry point (404)
- `PATCH /api/v1/entry-points/{id}` — Update entry point (404/409)
- `DELETE /api/v1/entry-points/{id}` — Soft-delete entry point (404)
- `POST /api/v1/camera-entry-points` — Create mapping (201)
- `GET /api/v1/camera-entry-points` — List mappings (paginated, filterable)
- `GET /api/v1/camera-entry-points/{id}` — Get mapping (404)
- `PATCH /api/v1/camera-entry-points/{id}` — Update mapping (404)
- `DELETE /api/v1/camera-entry-points/{id}` — Disable mapping (404)

**Fixes to Existing Tests:**
- `test_verification.py` — Added Camera/EntryPoint/CameraEntryPointMapping cleanup before ExamHall delete
- `test_dashboard.py` — Same FK ordering fix

**Tests:** 1198 total (1156 previous + 42 new), 0 failures, 0 errors

---

## Phase 9.3 — Camera & Entry Point Admin UI

**Status: COMPLETE**

Full frontend management UI for cameras, entry points, and camera↔entry point mappings.

**New Files:**
- `frontend/src/lib/camera-api.ts` — TypeScript API client for cameras, entry points, mappings, and exam halls
- `frontend/src/app/cameras/page.tsx` — Camera management page (list, create, edit, deactivate, filters, pagination)
- `frontend/src/app/entry-points/page.tsx` — Entry point management page (list, create, edit, deactivate, code auto-uppercasing)
- `frontend/src/app/camera-entry-mappings/page.tsx` — Mapping management page (list, create, disable, camera↔entry-point pairing)

**UI Features:**
- Camera list with device identifier, type, manufacturer, status, connection info, and exam hall association
- Entry point list with code, location detail, hall association
- Mapping list showing camera and entry point pairing with enabled/disabled state
- Create/edit modals for cameras (all fields including resolution/position) and entry points (name, code, description, location, hall)
- Mapping creation via dropdowns (select active camera + active entry point)
- Soft-delete via deactivate/disable with confirmation modal
- Search, pagination, show-inactive/disabled toggle filters
- Reference data pre-loading (exam halls for hall assignment dropdowns)
- Graceful handling when no active cameras or entry points exist
- Monochrome design system, consistent with existing admin pages

**Tests:** 1198 total (no new backend tests — UI only), 0 failures, 0 errors

---

## Phase 9.4 — Device Health & Status Foundation

**Status: COMPLETE**

Real device health/status foundation for physical Camera infrastructure. Separates administrative state (`is_active`) from observed operational state (`status`).

**Key Design Decisions:**
- `is_active` = administrative availability; `status` = observed operational state
- Status can only change via `record_health_observation()` — not via PATCH camera
- Initial camera status is `UNKNOWN` (not `ONLINE`) — no observation = unknown
- `ONLINE` only set when device actually responds; `OFFLINE` when unreachable
- `DISABLED` set automatically when camera is deactivated (`is_active=false`)
- Health observation endpoint is unauthenticated (Phase 19 will add auth)

**New Model Fields (Camera):**
- `last_seen_at` — when device was last observed responding (set on ONLINE observation)
- `last_health_check_at` — when health status was last evaluated
- `health_reason` — reason category for current status

**HealthReason Enum:** `DEVICE_RESPONDED`, `DEVICE_UNREACHABLE`, `DEVICE_DISABLED`, `NO_OBSERVATION`

**New Files:**
- `backend/app/schemas/camera_health.py` — HealthObservationCreate, HealthResponse schemas
- `backend/app/services/camera_health.py` — record_health_observation(), get_camera_health()
- `backend/app/api/v1/camera_health.py` — GET /cameras/{id}/health, POST /cameras/{id}/health-observations
- `backend/alembic/versions/017_add_camera_health_fields.py` — Migration
- `backend/tests/test_phase_9_4_health.py` — 31 unit tests (SQLite in-memory)
- `backend/tests/test_phase_9_4_api.py` — 22 API integration tests (real PostgreSQL)

**Modified Files:**
- `backend/app/models/camera.py` — Added HealthReason enum, last_seen_at, last_health_check_at, health_reason fields
- `backend/app/schemas/camera.py` — Removed `status` from CameraUpdate, added health fields to CameraResponse
- `backend/app/services/camera.py` — deactivate_camera() now sets status=DISABLED
- `backend/app/api/v1/router.py` — Registered camera_health router
- `backend/tests/test_phase_9_2_api.py` — Fixed test_update_camera (status no longer settable via PATCH)
- `frontend/src/lib/camera-api.ts` — Added health fields to Camera interface, health API functions
- `frontend/src/app/cameras/page.tsx` — Shows last_seen_at, health_reason in table

**API Endpoints:**
- `GET /api/v1/cameras/{id}/health` — Returns current health state
- `POST /api/v1/cameras/{id}/health-observations` — Records a health observation

**Security:** Status cannot be faked via camera CRUD. Health observations are the only path to change status. No credential/secret/biometric leakage.

**Tests:** 1251 total (1198 previous + 53 new), 0 failures, 0 errors

---

## Phase 9.5 — Secure Device Communication Foundation

**Status: COMPLETE**

Secure credential provisioning, authentication, and revocation for physical camera devices. Device health endpoint authenticated via credential-based identity.

**Key Design Decisions:**
- Credentials are high-entropy 256-bit secrets (`secrets.token_hex(32)`)
- SHA-256 hashing is appropriate for high-entropy bearer tokens (preimage-resistant; bcrypt adds zero security benefit against 256-bit random secrets)
- Constant-time comparison via `hmac.compare_digest` prevents timing attacks
- Raw secret returned ONCE at provisioning; never stored, logged, or returned again
- Camera identity derived from authenticated credential — caller cannot override camera_id
- Admin CRUD cannot change camera status; only `record_health_observation()` changes status
- Revoked credentials immediately rejected
- Inactive cameras cannot authenticate

**New Files:**
- `backend/app/models/camera_device_credential.py` — CameraDeviceCredential model (secret_hash, secret_prefix, status, camera_id FK)
- `backend/app/schemas/device_credential.py` — DeviceCredentialCreate, DeviceCredentialResponse, DeviceCredentialProvisionResponse, DeviceHealthRequest, DeviceHealthResponse
- `backend/app/services/device_credential.py` — create_device_credential(), authenticate_device(), revoke_device_credential(), list_device_credentials(), get_device_credential()
- `backend/app/api/v1/device.py` — 5 endpoints: provision credential, list credentials, get credential, revoke credential, device health
- `backend/alembic/versions/018_create_camera_device_credentials_table.py` — Migration
- `backend/tests/test_phase_9_5_device_comm.py` — 38 service-level tests
- `backend/tests/test_phase_9_5_device_api.py` — 16 API integration tests

**Modified Files:**
- `backend/app/models/camera.py` — Added device_credentials relationship with cascade delete
- `backend/app/models/__init__.py` — Registered CameraDeviceCredential model
- `backend/app/api/v1/router.py` — Registered device router

**API Endpoints:**
- `POST /api/v1/device/credentials` — Provision new credential (returns raw secret once)
- `GET /api/v1/device/credentials?camera_id=` — List credentials (no secrets)
- `GET /api/v1/device/credentials/{id}` — Get credential (no secret)
- `POST /api/v1/device/credentials/{id}/revoke` — Revoke credential
- `POST /api/v1/device/health` — Device health heartbeat (authenticated via X-Device-Credential header)

**Security Audit:** Passed — no secrets in code, no leaks, no biometric data in device layer, constant-time comparison, identity binding correct.

**Tests:** 1305 total (1251 previous + 54 new), 0 failures, 0 errors

---

## Phase 9.6 — Camera Infrastructure Integration & Hardening

**Status: COMPLETE**

Cross-component integration tests and comprehensive audit verifying the complete Phase 9 camera infrastructure works correctly as one domain.

**Audit Results (all passed):**
- Domain Integration: All FKs correct, relationships registered, cascade intentional, unique constraints correct, indexes appropriate
- Camera State Invariants: is_active ≠ status, deactivate sets DISABLED, health observation only path to change status, admin PATCH cannot set status
- Mapping Integration: Duplicate prevention works, deactivation preserves history, camera deactivation does not break mappings
- Exam Hall Integration: No cascade delete of exam data, camera/entry point can exist without hall
- Device Credential Integration: SHA-256 + constant-time comparison, raw secret never stored, credential-camera binding correct
- Device Health Integration: Full chain verified (auth → camera identity → observation → status update), future timestamps rejected
- API Consistency: All endpoints use correct HTTP codes, thin routes, no secrets in errors
- Security: No hard-coded credentials, no hash leakage, no IDOR, no mass assignment, no biometric data
- Privacy: No face images, embeddings, student data, or video in Phase 9
- Migrations: 016→017→018 chain correct, all have downgrades, no destructive ops
- Frontend: Real API data only, no fake monitoring, honest states

**New Files:**
- `backend/tests/test_phase_9_6_integration.py` — 44 cross-component integration tests

**Test Coverage Added:**
- Camera lifecycle: create → UNKNOWN → deactivate → DISABLED → reactivate → UNKNOWN
- Mapping lifecycle: create → duplicate rejection → disable preserves history → camera deactivation doesn't break mapping
- Credential binding: exact camera binding, multi-camera independence, revocation, cascade delete
- Device auth → health chain: full ONLINE/OFFLINE chain, deactivated camera breaks chain
- Hall integration: camera/entry point in hall, without hall, cascade delete safety
- Security invariants: secret never stored, hash never exposed, constant-time comparison, empty/whitespace rejection, error sanitization, no biometric data
- API integration: camera CRUD lifecycle, status immutability via PATCH, health observation via API, device health auth, mapping CRUD, duplicate mapping rejection
- Cross-component state: deactivated camera rejected by credential and health services, health observation updates admin view

**Tests:** 1349 total (1305 previous + 44 new), 0 failures, 0 errors

---

## Phase 9 — COMPLETE

All sub-phases complete:
- 9.1 Camera & Entry Point Domain Foundation ✅
- 9.2 Camera/Entry Point/Mapping CRUD APIs ✅
- 9.3 Camera Infrastructure Admin UI ✅
- 9.4 Device Health & Status ✅
- 9.5 Secure Device Communication Foundation ✅
- 9.6 Integration & Hardening ✅

**Total Phase 9 Tests:** 44 integration + 54 device comm + 53 health + 42 API + 53 model = 246 Phase 9-specific tests
**Total Backend Tests:** 1349 passing, 0 failures, 0 errors
**Total Frontend Pages:** 23 routes building successfully

---

## Phase 10.1 — Entry Verification Domain Model

**Status: COMPLETE**

Entry verification domain model with 4 enums, state machine, and migration.

**New Files:**
- `backend/app/models/entry_verification.py` — EntryVerification model + 4 enums + state machine
- `backend/alembic/versions/019_create_entry_verifications_table.py` — Migration
- `backend/tests/test_phase_10_1_models.py` — 49 model tests

**Tests:** 1398 total (1349 previous + 49 new), 0 failures, 0 errors

---

## Phase 10.2 — Entry Verification Service Layer

**Status: COMPLETE**

Entry verification service with 10 functions orchestrating Student, ExamRegistration, HallTicket, SeatAssignment, EntryPoint, Camera, IdentityVerificationAttempt.

**New Files:**
- `backend/app/services/entry_verification.py` — 10 service functions (719 lines)
- `backend/tests/test_phase_10_2_service.py` — 71 service tests

**Tests:** 1469 total (1398 previous + 71 new), 0 failures, 0 errors

---

## Phase 10.3 — Entry Verification API

**Status: COMPLETE**

REST API layer exposing entry verification service through 10 endpoints.

**New Files:**
- `backend/app/schemas/entry_verification.py` — Request/response schemas (EntryVerificationCreate, EntryVerificationResponse, EntryVerificationListResponse, EscalateRequest, ResolveRequest)
- `backend/app/api/v1/entry_verification.py` — 10 API endpoints (245 lines)
- `backend/tests/test_phase_10_3_api.py` — 56 API tests

**Modified Files:**
- `backend/app/api/v1/router.py` — Registered entry_verification router
- `backend/tests/test_verification.py` — Added EntryVerification to cleanup fixture
- `backend/tests/test_batch_verification.py` — Added EntryVerification to cleanup fixture
- `backend/tests/test_dashboard.py` — Added EntryVerification to cleanup fixture

**API Endpoints:**
- `POST /api/v1/entry-verifications` — Create entry verification (201)
- `GET /api/v1/entry-verifications` — List with pagination + filters (status, entry_point_id, student_id)
- `GET /api/v1/entry-verifications/{id}` — Get by ID (200/404)
- `POST /api/v1/entry-verifications/{id}/begin` — Begin processing (PENDING → IN_PROGRESS)
- `POST /api/v1/entry-verifications/{id}/hall-ticket-check` — Run hall ticket validation
- `POST /api/v1/entry-verifications/{id}/seat-check` — Run seat assignment validation
- `POST /api/v1/entry-verifications/{id}/identity-check` — Run identity verification orchestration
- `POST /api/v1/entry-verifications/{id}/evaluate` — Evaluate entry authorization (GRANTED/DENIED/ESCALATED)
- `POST /api/v1/entry-verifications/{id}/escalate` — Escalate for human review
- `POST /api/v1/entry-verifications/{id}/resolve` — Resolve escalation (GRANTED/DENIED)

**Security Audit:** Passed — client cannot set status/check states/resolved_at, no reviewer identity accepted, no biometric data exposed, no credential leakage, service remains authority.

**Tests:** 1525 total (1469 previous + 56 new), 0 failures, 0 errors

---

## Phase 10.4 — Entry Verification Admin UI

**Status: COMPLETE**

Administrative UI for the entry verification workflow — list, create, inspect, progress, escalate, resolve.

**New Files:**
- `frontend/src/lib/entry-verification-api.ts` — API client (typed functions for all 10 endpoints)
- `frontend/src/app/entry-verifications/page.tsx` — List page with filters (status, entry_point_id, student_id), pagination, create form
- `frontend/src/app/entry-verifications/[id]/page.tsx` — Detail page with workflow actions, check status display, escalation UI, resolution UI

**Features:**
- List page: table with ID, student, registration, entry point, exam hall, status, ticket/identity/seat checks, created timestamp
- Filters: status dropdown, student ID input, entry point ID input — server-side filtering via API
- Create form: student_id, exam_registration_id, entry_point_id (required), camera_id, hall_ticket_id (optional)
- Detail page: lifecycle status, all references, check states, timestamps
- Workflow actions: begin, hall-ticket-check, seat-check, identity-check, evaluate (PENDING/IN_PROGRESS)
- Escalation: reason textarea, confirm/cancel
- Resolution: grant/deny buttons, optional reason, shows escalation reason
- Error handling: inline errors from API, safe human-readable messages
- Loading states, empty states, disabled buttons during requests
- Responsive, accessible, monochrome design system

**Routes:**
- `/entry-verifications` — List + create (static)
- `/entry-verifications/[id]` — Detail + actions (dynamic)

**Tests:** 1525 total (unchanged), 0 failures, 0 errors
**Frontend:** 24 pages building successfully (was 23)

---

## Phase 10.5 — Entry Verification Integration & Hardening

**Status: COMPLETE**

Cross-component integration tests verifying the complete entry verification workflow behaves consistently across all related domains.

**Integration Test Coverage (`test_phase_10_5_integration.py` — 76 new tests):**

1. **Full Workflow E2E** (2 tests): Complete flow from creation through all checks to GRANTED, with and without optional fields.

2. **Hall Ticket Integration** (7 tests): Verified ticket passes, auto-link from registration, no ticket fails, unverified ticket fails, matched-not-verified fails, hall ticket not mutated by entry verification, repeated check consistent.

3. **Seat/Hall Integration** (5 tests): Correct hall passes, wrong hall fails, no seat fails, seat not mutated, cancelled seat fails.

4. **Camera/Entry Point Integration** (7 tests): Camera mapped to entry point, not mapped rejected, inactive camera rejected, disabled camera → identity skipped, offline camera → identity skipped, unknown camera → identity pending, online camera without attempt → identity pending.

5. **Identity Verification Integration** (4 tests): Match attempt passes, no match fails, pending attempt → pending, no biometric data in entry verification.

6. **Decision Combinations** (8 tests): All pass-pass-pass → GRANTED, any fail → DENIED, pending → ESCALATED, skipped → ESCALATED.

7. **State Machine Hardening** (11 tests): PENDING→IN_PROGRESS, PENDING→ESCALATED, terminal states cannot restart/escalate/evaluate, ESCALATED cannot begin, ESCALATED can resolve, resolve on non-escalated raises, exhaustive transition coverage.

8. **Human Escalation** (4 tests): Reason persisted, check states preserved after escalation, resolve records timestamp, escalation requires reason.

9. **Repeated Operations** (7 tests): Repeated begin, evaluate, escalation, hall ticket check, seat check, identity check, resolve — all idempotent.

10. **Concurrency** (2 tests): Concurrent begin attempts — state machine prevents corruption; escalate-then-evaluate — state machine enforces valid transitions.

11. **Data Integrity** (5 tests): Entry verification does not mutate Student, ExamRegistration, HallTicket, SeatAssignment; foreign keys valid after full workflow.

12. **API/Service/DB Integration** (3 tests): Create via API persists to DB, list filter consistency, get returns None for missing.

13. **Privacy/Security** (4 tests): No secrets in model, no biometric data persisted, no authentication introduced, escalation has no reviewer field.

14. **List/Filter Integration** (5 tests): List returns created records, filter by status/student/entry_point, pagination works.

15. **Edge Cases** (2 tests): Cancelled registration rejected, inactive entry point rejected.

**Tests:** 1601 total (1525 previous + 76 new), 0 failures, 0 errors

---

## Phase 10 — COMPLETE

All sub-phases complete:
- 10.1 Entry Verification Domain Model ✅
- 10.2 Entry Verification Service Layer ✅
- 10.3 Entry Verification REST API ✅
- 10.4 Entry Verification Admin UI ✅
- 10.5 Integration & Hardening ✅

**Total Phase 10 Tests:** 76 integration + 56 API + 71 service + 49 model = 252 Phase 10-specific tests
**Total Backend Tests:** 1601 passing, 0 failures, 0 errors
**Total Frontend Pages:** 24 routes building successfully

---

## Phase 11.1 — Anti-Proxy Domain & Database Foundation

**Status: COMPLETE**

Established the anti-proxy domain with SecuritySignal and ProxyRiskAssessment models, enums, risk scoring configuration, and database migration.

**Models:**
- `SecuritySignal` — immutable, append-only signal record (entry_verification FK, signal_type, strength, source, description, evidence_json, created_at)
- `ProxyRiskAssessment` — historical risk assessment (entry_verification FK, risk_level, risk_score, signals_summary_json, assessed_at, policy_version)

**Enums:**
- `SecuritySignalType` — 10 types: DUPLICATE_ENTRY, UNUSUAL_ENTRY_POINT, UNUSUAL_TIME, SEAT_MISMATCH, MULTIPLE_REGISTRATIONS, RAPID_ENTRY, DOCUMENT_ANOMALY, BEHAVIORAL_ANOMALY, IDENTITY_MISMATCH, MANUAL_FLAG
- `SignalStrength` — 4 levels: STRONG, MODERATE, WEAK, INFORMATIONAL
- `RiskLevel` — 4 levels: LOW, ELEVATED, HIGH, CRITICAL
- `SIGNAL_STRENGTH_DEFAULTS` — predefined strength defaults per signal type

**Configuration (`app/core/config.py`):**
- `PROXY_RISK_WEIGHTS` — comma-separated signal type:weight pairs (default: DUPLICATE_ENTRY:30, UNUSUAL_ENTRY_POINT:15, etc.)
- `PROXY_RISK_ELEVATED_THRESHOLD: float = 30.0`
- `PROXY_RISK_HIGH_THRESHOLD: float = 60.0`
- `PROXY_RISK_CRITICAL_THRESHOLD: float = 80.0`
- `PROXY_RISK_MAX_SCORE: float = 100.0`
- `PROXY_RISK_POLICY_VERSION: str = "1.0"`
- `model_validator` enforces threshold ordering: 0 <= ELEVATED < HIGH < CRITICAL <= MAX_SCORE

**Migration:** 020 (`020_create_proxy_risk_tables.py`)

**New Files:**
- `backend/app/models/proxy_risk.py` — SecuritySignal + ProxyRiskAssessment models + 3 enums + defaults dict
- `backend/alembic/versions/020_create_proxy_risk_tables.py` — Migration
- `backend/tests/test_phase_11_1_models.py` — 47 model tests

**Modified Files:**
- `backend/app/core/config.py` — Added 6 proxy risk config settings + validator
- `backend/app/models/__init__.py` — Registered SecuritySignal, ProxyRiskAssessment

**Tests:** 1648 total (1601 previous + 47 new), 0 failures, 0 errors
**Frontend:** 24 pages building successfully

---

## Phase 11.2 — Deterministic Anti-Proxy Signal Detection

**Status: COMPLETE**

Deterministic signal detection service that examines EntryVerification and related domain data to produce SecuritySignal records.

**Service:** `backend/app/services/signal_detection.py`
- `detect_signals(db, entry_verification_id) -> list[SecuritySignal]`
- 14 private detector functions, one per signal type
- Idempotent: deduplication via `(signal_type, dedup_key)` in evidence_json
- Single transaction boundary with `db.flush()`
- Exception-safe: individual detector failures logged but don't abort others

**Signal Types Implemented (14):**

| Signal | Strength | Condition |
|---|---|---|
| IDENTITY_MISMATCH | STRONG | Identity attempt decision = NO_MATCH |
| LIVENESS_SPOOF_DETECTED | STRONG | Evidence signal_type="liveness", signal_value="FAIL" |
| WRONG_HALL_DETECTED | STRONG | SeatAssignment hall ≠ EntryVerification exam_hall |
| IDENTITY_INCONCLUSIVE | MODERATE | Identity attempt decision = INCONCLUSIVE |
| DUPLICATE_ENTRY_SAME_EXAM | MODERATE | Other EntryVerification for same student + exam |
| REPEATED_FAILED_IDENTITY | MODERATE | >1 NO_MATCH attempts for same exam_registration |
| HALL_TICKET_FIELD_MISMATCH | MODERATE | HallTicketMatchSignal has matched=False fields |
| WRONG_ENTRY_POINT | MODERATE | EntryPoint exam_hall ≠ SeatAssignment exam_hall |
| MISSING_IDENTITY_CHECK | INFORMATIONAL | identity_check=SKIPPED with active camera mapped |
| NO_SEAT_ASSIGNMENT | WEAK | No ASSIGNED SeatAssignment for registration |
| NO_HALL_TICKET | WEAK | No VERIFIED/MATCHED HallTicket for registration |
| CAMERA_OFFLINE_AT_ENTRY | WEAK | Camera status is OFFLINE or DISABLED |
| LATE_ENTRY | WEAK | EntryVerification created after Exam.start_time |
| RAPID_SEQUENTIAL_ENTRY | WEAK | Multiple entries within configurable window |

**Configuration Added:**
- `PROXY_RISK_RAPID_ENTRY_WINDOW_SECONDS: int = 300` — configurable window for rapid entry detection

**SecuritySignalType Enum Expanded:** 10 → 23 values (13 new types added)

**Migration:** 021 (`021_expand_security_signal_type_enum.py`) — documentation-only, SQLite accepts strings without ALTER TYPE

**New Files:**
- `backend/app/services/signal_detection.py` — signal detection service
- `backend/tests/test_signal_detection.py` — 72 tests
- `backend/alembic/versions/021_expand_security_signal_type_enum.py` — migration

**Modified Files:**
- `backend/app/models/proxy_risk.py` — expanded SecuritySignalType (10→23), SIGNAL_STRENGTH_DEFAULTS (10→23)
- `backend/app/core/config.py` — added PROXY_RISK_RAPID_ENTRY_WINDOW_SECONDS
- `backend/tests/test_phase_11_1_models.py` — updated enum count assertion (10→23)

**Tests:** 1720 total (1648 previous + 72 new), 0 failures, 0 errors
**Frontend:** 24 pages building successfully

**What Phase 11.2 does NOT do:**
- Does NOT calculate risk scores (Phase 11.3)
- Does NOT create ProxyRiskAssessment records
- Does NOT modify EntryVerification status
- Does NOT authorize or deny entry
- Does NOT create API endpoints (Phase 11.4)
- Does NOT create frontend UI (Phase 11.5)
- Does NOT implement review workflow (Phase 11.6)

---

## Phase 11.3 — Proxy Risk Scoring & Assessment

**Status: COMPLETE**

Pure, deterministic risk-scoring engine that evaluates security signals and produces risk assessments. No biometric data. No AI claims.

**Service:** `backend/app/services/proxy_risk.py`

**Pure Scoring Engine:**
- `compute_risk_score(signals) -> RiskAssessmentResult` — no DB side effects
- `_parse_weights(raw) -> dict[str, float]` — parse config weight string
- `_classify_risk_level(score, settings) -> str` — threshold-based classification
- `_build_explanation(...)` — deterministic, reproducible explanation
- `_build_signals_summary(result)` — JSON summary for ProxyRiskAssessment

**DB Assessment:**
- `assess_entry_verification(db, entry_verification_id) -> ProxyRiskAssessment` — loads signals, computes score, persists assessment

**Scoring Algorithm:**
1. Look up each signal's weight from configured `PROXY_RISK_WEIGHTS`
2. Unknown signal types default to weight 0 (informational only)
3. Sum all weights, cap at `PROXY_RISK_MAX_SCORE`
4. Classify score into risk level via configured thresholds
5. Build deterministic explanation from signal types and strengths

**Risk Classification:**
- LOW: score < ELEVATED_THRESHOLD (30.0)
- ELEVATED: ELEVATED_THRESHOLD <= score < HIGH_THRESHOLD (60.0)
- HIGH: HIGH_THRESHOLD <= score < CRITICAL_THRESHOLD (80.0)
- CRITICAL: score >= CRITICAL_THRESHOLD (80.0)

**Dataclass:**
- `RiskAssessmentResult` — frozen, with risk_score, risk_level, signal_count, strong_signal_count, explanation, signals_detail

**Design Decisions:**
- Pure scoring separated from DB persistence
- Unknown signal types gracefully handled (weight = 0)
- Score capped at PROXY_RISK_MAX_SCORE
- Historical assessments preserved (append-only, multiple per EntryVerification)
- No biometric data in explanations or summaries
- No AI claims in explanations
- EntryVerification not mutated by assessment
- Policy version tracked for audit trail

**Files:**
- `backend/app/services/proxy_risk.py` — risk scoring and assessment service
- `backend/tests/test_proxy_risk.py` — 43 tests

**Modified Files:**
- None (no existing files changed)

**Tests:** 1763 total (1720 previous + 43 new), 0 failures, 0 errors
**Frontend:** 24 pages building successfully

---

## Phase 11.4 — Proxy Risk REST API

**Status: COMPLETE**

Thin REST API layer exposing signal detection and risk assessment through existing service functions.

**Endpoints (5):**

| Method | Path | Description |
|---|---|---|
| POST | `/entry-verifications/{id}/risk/signals/detect` | Detect security signals (idempotent) |
| GET | `/entry-verifications/{id}/risk/signals` | List security signals (paginated) |
| POST | `/entry-verifications/{id}/risk/assess` | Assess proxy risk (historical) |
| GET | `/entry-verifications/{id}/risk/assessments` | List historical risk assessments (paginated) |
| GET | `/entry-verifications/{id}/risk` | Get latest risk assessment |

**Schemas:** `backend/app/schemas/proxy_risk.py`
- `SecuritySignalResponse` — signal record with type, strength, source, description, created_at
- `SecuritySignalListResponse` — paginated signals
- `ProxyRiskAssessmentResponse` — assessment with audit fields (signal_count, strong_signal_count, explanation from signals_summary_json)
- `ProxyRiskAssessmentListResponse` — paginated assessments

**Router:** `backend/app/api/v1/proxy_risk.py`
- Registered in `app/api/v1/router.py`
- Prefix: `/entry-verifications`, tags: `["Proxy Risk Assessment"]`
- Thin routes: validates, calls services, translates errors, returns schemas
- No scoring or detection logic in router

**Design Decisions:**
- Phase 11 remains ADVISORY — no EntryVerification mutation
- detect endpoint commits signals (service only flushes)
- Assessment fields (signal_count, strong_signal_count, explanation) extracted from signals_summary_json
- 404 for nonexistent entry verification or missing assessment
- No 404 manufacture of LOW-risk result
- Error sanitization: no tracebacks, no database info

**Files:**
- `backend/app/schemas/proxy_risk.py` — response schemas
- `backend/app/api/v1/proxy_risk.py` — API router (5 endpoints)
- `backend/tests/test_phase_11_4_api.py` — 40 tests

**Modified Files:**
- `backend/app/api/v1/router.py` — registered proxy_risk router

**Tests:** 1803 total (1763 previous + 40 new), 0 failures, 0 errors
**Frontend:** 24 pages building successfully

---

## Phase 11.5 — Admin Risk UI

**Status: COMPLETE**

Frontend integration for the proxy risk detection and assessment system. Provides admin visibility into security signals and risk assessments through the existing entry verification detail page.

### Implementation

**API Client (`frontend/src/lib/proxy-risk-api.ts`):**
- TypeScript API client with typed interfaces matching backend schemas: `SecuritySignal`, `SecuritySignalListResponse`, `ProxyRiskAssessment`, `ProxyRiskAssessmentListResponse`
- 5 functions: `detectSignals()`, `listSignals()`, `assessRisk()`, `listAssessments()`, `getLatestAssessment()`
- Shared `ApiError` class for typed error handling
- Uses same `request()` pattern as existing API clients

**Risk Panel on Entry Verification Detail Page (`frontend/src/app/entry-verifications/[id]/page.tsx`):**
- New "Proxy Risk Assessment" section appended after existing content
- Risk summary grid: risk level badge, score, signal count (with strong count), assessed timestamp
- Deterministic explanation text displayed when available
- Signals table: type, strength badge, source, description — paginated (100 items per load)
- Assessment history timeline (most recent 50) — shown when multiple assessments exist
- "Detect Signals" and "Assess Risk" buttons — advisory actions that call backend endpoints
- Empty state when no risk data exists yet
- Loading/error states with inline error display

**Security/Privacy Audit Passed:**
- Renders only deterministic labels, numeric scores, and text explanations
- No biometric data, face images, embeddings, similarity scores, or provider secrets displayed
- All endpoints are advisory-only (no EntryVerification status mutation)
- Risk level badges use monochrome design tokens only

**Files Changed:**

| File | Change |
|---|---|
| `frontend/src/lib/proxy-risk-api.ts` | New: TypeScript API client for Phase 11.4 proxy risk endpoints |
| `frontend/src/app/entry-verifications/[id]/page.tsx` | Extended: added risk panel with signals, assessments, detect/assess buttons |

**Tests:** 1803 total (unchanged), 0 failures, 0 errors
**Frontend:** 24 pages building successfully

---

## Phase 11.6 — Integration & Hardening

**Status: COMPLETE**

Comprehensive integration, correctness, security, privacy, data-integrity, API, migration, concurrency, and regression audit of the COMPLETE Phase 11 implementation (11.1–11.5).

### Audit Results (all passed)

- **Signal Detection Correctness:** All 14 detectors verified — produce correct signal types, correct strengths from SIGNAL_STRENGTH_DEFAULTS, correct sources. No unintended signal types produced.
- **Enum Audit:** 23 SecuritySignalType values exist. 14 are implemented (produced by detectors). 9 are planned/future (no detectors). All planned types have zero weight in scoring — no accidental contribution.
- **Deduplication/Idempotency:** Triple call produces no duplicates. Existing signals preserved. Unrelated EVs unaffected. Multiple signal types dedup independently.
- **Risk Scoring:** Weights from configuration. Unknown signal types → weight 0. Score capped by MAX_SCORE. Thresholds from configuration. Deterministic. Policy version persisted. No probability/confidence terminology.
- **Historical Assessment Integrity:** Multiple assessments create distinct rows. No overwrite. No unique constraint blocking history. Chronological ordering preserved. Each retains own score and policy version.
- **API Integration:** All 5 endpoints tested together. Correct HTTP codes. Correct schemas. Ownership by EntryVerification. Pagination. 404 handling. No accidental implicit assessment.
- **API Security/Privacy:** No face images, embeddings, biometric data, provider credentials, API keys, or secrets in responses. Error responses sanitized — no tracebacks, no database info.
- **EntryVerification Isolation:** ALL Phase 11 operations (detect, assess) preserve all EV authorization fields. Status, check states, escalation fields unchanged.
- **Concurrency:** Interleaved detect/assess operations produce correct results. Idempotency maintained. Historical assessments distinct.
- **Configuration Audit:** All settings validated, typed, loaded via get_settings(). Not duplicated in service code. Thresholds ordered correctly.
- **Code Quality:** No bare exceptions. Routers thin. Scoring pure (no DB side effects). Detection deterministic (no random/sleep/uuid). No dead code. No unused imports.
- **Migration Audit:** 020 creates tables with String(50) columns (not native ENUM). 021 is a no-op by design — correct for String columns. Downgrades drop tables. Indexes and foreign keys correct.
- **Frontend Audit:** No fake data, no hardcoded signal arrays, no fake timestamps, no fake charts. All data from real API. No console.log/debug. No localStorage/sessionStorage. Monochrome design tokens.
- **Security/Privacy Audit:** No passwords, API keys, tokens, embeddings, base64 face data, raw OCR payloads, TODO claims, or unsupported AI claims in Phase 11 code.

### Bugs/Issues Discovered

None. All implementation is correct as designed.

### Files Changed

| File | Change |
|---|---|
| `backend/tests/test_phase_11_6_integration.py` | New: 86 integration/hardening tests |

### Tests

86 new tests (`test_phase_11_6_integration.py`):
- End-to-end integration (12): clean entry, identity mismatch (4), liveness spoof (2), wrong hall (2), multiple signals (1), inconclusive identity (2), missing evidence (3)
- Signal detection correctness (17): all 14 detector names, 14 strength assertions, no EV mutation, detector failure isolation, no unintended types
- Enum audit (5): all values exist, all have strength defaults, used vs planned types, weights verification
- Deduplication/idempotency (4): triple call, preserved signals, unrelated EVs, multiple signal types
- Risk scoring boundary (11): all boundary values, MAX_SCORE, config weights, config ordering, config types
- Historical assessment integrity (7): three rows, no overwrite, chronological, own score, policy version, unchanged previous, no unique constraint
- API integration (3): full flow, no EV mutation, repeated assessment history
- API security/privacy (4): no biometric data in explanations/descriptions/evidence, no API keys in config
- EntryVerification isolation (3): all fields preserved, assess preserves, granted status preserved
- Concurrency (3): sequential detect idempotent, sequential assess distinct, interleaved detect+assess
- Configuration audit (4): settings loaded, not None, not duplicated, uses get_settings
- Code quality (7): no bare exceptions, thin routers, pure scoring, deterministic detection, no unused imports, no DB commits in scoring

**Total tests:** 1889 (1803 previous + 86 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 1889 passed)
**Frontend:** 24 pages building successfully

---

## Phase 11 — COMPLETE

All sub-phases complete:
- 11.1 Domain foundation ✅ (47 tests)
- 11.2 Signal detection ✅ (72 tests)
- 11.3 Risk scoring ✅ (43 tests)
- 11.4 REST API ✅ (40 tests)
- 11.5 Admin UI ✅ (frontend)
- 11.6 Integration & hardening ✅ (86 tests)

**Total Phase 11 backend tests:** 288 (47 + 72 + 43 + 40 + 86)
**Total backend tests:** 1889 passing, 0 failures, 0 errors
**Frontend:** 24 pages, all building successfully

### Limitations

Phase 11 is advisory-only by design. It does NOT:
- Grant or deny exam entry (Phase 10 owns authorization)
- Automatically escalate entry verifications
- Perform 1:N face identification
- Confirm proxy fraud (it produces evidence signals, not decisions)
- Real-time stream monitoring (Phase 13)
- Authentication/authorization (Phase 19)
- Store biometric data or face images

### SecuritySignalType Enum — Planned vs Implemented

**Implemented (14 — produced by detectors):**
IDENTITY_MISMATCH, LIVENESS_SPOOF_DETECTED, WRONG_HALL_DETECTED, IDENTITY_INCONCLUSIVE, DUPLICATE_ENTRY_SAME_EXAM, REPEATED_FAILED_IDENTITY, HALL_TICKET_FIELD_MISMATCH, WRONG_ENTRY_POINT, MISSING_IDENTITY_CHECK, NO_SEAT_ASSIGNMENT, NO_HALL_TICKET, CAMERA_OFFLINE_AT_ENTRY, LATE_ENTRY, RAPID_SEQUENTIAL_ENTRY

**Planned (9 — no detectors, zero weight, future implementation):**
DUPLICATE_ENTRY, UNUSUAL_ENTRY_POINT, UNUSUAL_TIME, SEAT_MISMATCH, MULTIPLE_REGISTRATIONS, RAPID_ENTRY, DOCUMENT_ANOMALY, BEHAVIORAL_ANOMALY, MANUAL_FLAG

---

## Phase 12.1 — Attendance Domain Models & Database

**Status: COMPLETE**

Domain foundation for attendance tracking. Creates two models:
- `AttendanceRecord` — current attendance state per ExamRegistration (one record per registration)
- `AttendanceEvent` — append-only event history (idempotent per EntryVerification)

### Models Created

- `AttendanceRecord` — current attendance state per ExamRegistration
  - `student_id`, `exam_id`, `exam_registration_id`, `status`, `entry_verification_id`, `entry_method`, `entry_time`, `hall_id`, `seat_number` (nullable)
  - UniqueConstraint on `exam_registration_id` — exactly one current record per registration
  - Relationships: student, exam, registration, entry_verification, hall

- `AttendanceEvent` — append-only event history
  - `student_id`, `exam_id`, `exam_registration_id`, `entry_verification_id`, `event_type`, `status_snapshot`, `recorded_by` (nullable), `reason` (nullable)
  - UniqueConstraint on `entry_verification_id` — idempotent, no duplicate events per EV
  - Relationships: student, exam, registration, entry_verification

### Enums

- `AttendanceStatus`: PRESENT, ABSENT, EXCUSED
- `EntryMethod`: VERIFIED_ENTRY, MANUAL_ENTRY
- `AttendanceEventType`: ENTRY_GRANTED, ENTRY_DENIED, ENTRY_ESCALATED, ATTENDANCE_RECORDED, ATTENDANCE_CORRECTED, ATTENDANCE_EXCUSED

### Migration

- `022_create_attendance_tables.py` — creates `attendance_records` and `attendance_events` tables

### Files Changed

| File | Change |
|---|---|
| `backend/app/models/attendance.py` | New: AttendanceRecord, AttendanceEvent models, 3 enums |
| `backend/app/models/__init__.py` | Modified: registered AttendanceRecord, AttendanceEvent |
| `backend/alembic/versions/022_create_attendance_tables.py` | New: creates both tables |
| `backend/tests/test_phase_12_1_models.py` | New: 42 model tests |

### Tests

42 tests covering:
- Enum value persistence (3 enums, 10 values)
- AttendanceRecord creation, defaults, timestamps, repr
- AttendanceRecord relationships (5 FK relationships)
- AttendanceRecord uniqueness (one per registration, different registrations valid)
- AttendanceRecord status values
- AttendanceRecord snapshot semantics
- AttendanceEvent creation, defaults, timestamps, repr, nullable fields
- AttendanceEvent relationships (4 FK relationships)
- AttendanceEvent idempotency (one per EV, different EVs valid)
- AttendanceEvent type values (6 event types)
- Multiple events across registrations
- Privacy (no biometric/credential fields)
- Model registration (2 tables, correct columns)
- Index verification (6 record indexes, 6 event indexes)
- Constraint verification (2 unique constraints)
- History preservation (multiple EVs same registration)

**Total tests:** 1931 (1889 previous + 42 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 1931 passed)

---

## Phase 12.2 — Attendance Service Layer

**Status: COMPLETE**

Service layer implementing all attendance business logic. 7 functions covering recording, querying, manual correction, and summaries.

### Service Functions

| Function | Purpose |
|---|---|
| `record_attendance(db, entry_verification_id)` | Record attendance from resolved EV (GRANTED→PRESENT, DENIED→event only, ESCALATED/PENDING→reject) |
| `get_attendance(db, exam_id, student_id)` | Get current attendance for a student in an exam |
| `list_attendance(db, exam_id, *, hall_id, status, page, page_size)` | List attendance records with filters |
| `get_entry_events(db, entry_verification_id, *, page, page_size)` | Get attendance events for an EV |
| `mark_manual_attendance(db, exam_registration_id, *, status, reason, recorded_by)` | Manual attendance correction (PRESENT/EXCUSED only) |
| `get_exam_summary(db, exam_id)` | Attendance summary with counts and by-hall breakdown |
| `list_student_attendance_history(db, student_id, *, page, page_size)` | Student attendance across exams |

### Business Rules Implemented

- EntryVerification is the sole source of authorization — Phase 12 does NOT independently authorize entry
- GRANTED EVs create/update AttendanceRecord → PRESENT + ENTRY_GRANTED event
- DENIED EVs create ENTRY_DENIED event only, no AttendanceRecord
- ESCALATED/PENDING/IN_PROGRESS EVs rejected with ValueError
- Idempotent: same EV processed twice returns existing state, no duplicate events
- Re-entry: multiple GRANTED EVs for same registration update existing record, create separate events
- Hall/seat snapshot from SeatAssignment at entry time (nullable seat_number if missing)
- Manual correction: PRESENT/EXCUSED only, validates registration not cancelled, requires reason/recorded_by
- Manual correction uses latest EV for registration as FK reference
- Absent is computed (registered - present - excused), never stored as record
- Exam summary includes by-hall breakdown with building+room names
- Deterministic ordering: by ID for records/events, desc by ID for student history

### Schema Limitation Handled

The `attendance_events.entry_verification_id` UNIQUE constraint means each EV can produce only ONE event. When `mark_manual_attendance` is called after `record_attendance` for the same EV, the service skips event creation (the EV already has an event) and updates only the AttendanceRecord. This is a graceful degradation, not data corruption.

### Files Changed

| File | Change |
|---|---|
| `backend/app/services/attendance/service.py` | New: 7 service functions with validation, idempotency, snapshot semantics |
| `backend/tests/test_phase_12_2_service.py` | New: 55 service tests |

### Tests

55 tests covering:
- record_attendance: GRANTED (7 tests), DENIED (3 tests), invalid status (3 tests), missing EV (1 test), idempotency (4 tests), re-entry (1 test)
- get_attendance (2 tests)
- list_attendance (6 tests)
- get_entry_events (3 tests)
- mark_manual_attendance (9 tests): PRESENT, EXCUSED, event creation, invalid status, cancelled registration, empty reason, empty recorded_by, no EV, update existing record
- get_exam_summary (5 tests): empty exam, present, absent computation, by-hall, missing exam
- list_student_attendance_history (4 tests)
- concurrency (1 test)
- architectural safety (4 tests): no EV status mutation, no biometric data
- privacy (2 tests): no credentials

**Total tests:** 1986 (1931 previous + 55 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 1986 passed)

---

## Phase 12.4 — Attendance Admin UI

**Status: COMPLETE**

### Implementation

- `frontend/src/lib/attendance-api.ts` — API client for all 7 attendance endpoints
- `frontend/src/app/attendance/page.tsx` — Exam list page with per-exam attendance summary (registered, present, rate)
- `frontend/src/app/attendance/[examId]/page.tsx` — Per-exam attendance view:
  - Summary stats (registered, present, absent, excused, rate)
  - Per-hall breakdown
  - Filterable attendance records table (by hall, status)
  - Inline manual correction form (status, reason, recorded_by)
  - Inline event history viewer per entry verification
- `frontend/src/app/attendance/events/[entryVerificationId]/page.tsx` — Full event history for an entry verification

### Files Changed

| File | Change |
|---|---|
| `frontend/src/lib/attendance-api.ts` | New: API client with types and functions for all attendance endpoints |
| `frontend/src/app/attendance/page.tsx` | New: Exam list with attendance summaries |
| `frontend/src/app/attendance/[examId]/page.tsx` | New: Per-exam attendance view with correction + event history |
| `frontend/src/app/attendance/events/[entryVerificationId]/page.tsx` | New: Full event history page |

### Tests

- Frontend build: 27 routes clean (24 existing + 3 new attendance routes)
- Backend: 2048 passing, 0 failures, 0 errors
- No new backend tests — Phase 12.4 is frontend only

**Total tests:** 2048 (unchanged), 0 failures, 0 errors
**Consecutive full-suite runs:** 3 (all 2048 passed)

---

## Phase 12.5 — Integration & Hardening

**Status: COMPLETE**

### Bugs Discovered & Fixed

1. **Frontend `attendance_rate` double-multiply** — Backend returns 0-100 percentage, frontend multiplied by 100 again (showing 5000% instead of 50%). Fixed in both `/attendance/page.tsx` and `/attendance/[examId]/page.tsx`.

2. **`attendance_events.entry_verification_id` UNIQUE constraint** — Prevented creation of correction events when an EV already had an auto-recorded event. Manual correction audit trail was silently lost. Fixed by dropping the constraint (migration 023) and updating service to always create correction events.

3. **React Fragment keys** — `/attendance/[examId]/page.tsx` used `<>` fragments in `.map()` without keys. Fixed by using `<Fragment key={r.id}>`.

### Migration 023

- Drops `uq_attendance_event_per_entry_verification` UNIQUE constraint from `attendance_events`
- Allows multiple events per entry verification for complete audit trail
- Preserves all existing data
- Downgrade recreates the constraint

### Service Changes

- `record_attendance`: Idempotency check now only matches ENTRY_GRANTED and ENTRY_DENIED events (not ATTENDANCE_CORRECTED)
- `mark_manual_attendance`: Always creates ATTENDANCE_CORRECTED event (removed silent skip when EV already had an event)

### Tests Added

45 integration/hardening tests in `test_phase_12_5_integration.py`:
- End-to-end workflows (GRANTED, DENIED, ESCALATED→GRANTED, ESCALATED→DENIED, RE-ENTRY)
- Idempotency (record_attendance called twice)
- Concurrency (same EV twice, different EVs same registration)
- Event history audit (correction events always created, original events preserved)
- State machine (PRESENT↔EXCUSED, invalid transitions rejected)
- Summary correctness (empty exam, absent computation, by_hall, rate range, no negative counts)
- Snapshot integrity (seat/hall preserved after source changes)
- API integration (list filters, pagination, student history)
- Privacy (no biometric fields in record/event)
- Architectural safety (attendance never mutates EntryVerification)
- Edge cases (missing EV, empty reason, empty recorded_by, cancelled registration, PENDING/IN_PROGRESS EVs)

### Model Test Updates

- `TestAttendanceEventMultiEvent`: Replaced `TestAttendanceEventIdempotency` — verifies multiple events per EV are now allowed
- `test_event_no_unique_constraint_on_ev_id`: Replaced `test_event_unique_constraint_exists` — verifies constraint was dropped

### Files Changed

| File | Change |
|---|---|
| `backend/alembic/versions/023_drop_attendance_event_ev_unique.py` | New: drops UNIQUE constraint |
| `backend/app/models/attendance.py` | Removed UniqueConstraint from AttendanceEvent |
| `backend/app/services/attendance/service.py` | Updated idempotency check + always create correction events |
| `backend/tests/test_phase_12_5_integration.py` | New: 45 integration/hardening tests |
| `backend/tests/test_phase_12_1_models.py` | Updated 2 tests for new constraint behavior |
| `frontend/src/app/attendance/page.tsx` | Fixed attendance_rate display |
| `frontend/src/app/attendance/[examId]/page.tsx` | Fixed attendance_rate display + Fragment keys |

### Verification

- Backend: **2093 passed**, 0 failures, 0 errors
- Full-suite run #1: 2093 passed
- Full-suite run #2: 2093 passed
- Frontend build: **27 routes** clean
- Migration 023: Applied and validated
- Privacy/security audit: No sensitive data exposed
- No fake data, no dead buttons, no hardcoded secrets

**Total tests:** 2093 (2048 previous + 45 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 2093 passed)

---

## Phase 13.1 — Real-Time Event Domain

**Status: COMPLETE**

### Implementation

Pure event-domain foundation for real-time monitoring. No database persistence, no WebSocket, no alerts, no frontend.

- `backend/app/services/monitoring/__init__.py` — Public API exports
- `backend/app/services/monitoring/events.py` — MonitoringEvent (frozen dataclass), enums, severity mapping, filter matching, payload safety validation
- `backend/app/schemas/monitoring.py` — Pydantic schemas for WebSocket/REST serialization

### Event Taxonomy

**16 event types** across 5 categories:
- ENTRY: ENTRY_CREATED, ENTRY_BEGAN, ENTRY_GRANTED, ENTRY_DENIED, ENTRY_ESCALATED, ENTRY_RESOLVED
- RISK: SIGNAL_DETECTED, RISK_ASSESSED, RISK_ELEVATED, RISK_HIGH, RISK_CRITICAL
- ATTENDANCE: ATTENDANCE_RECORDED, ATTENDANCE_CORRECTED
- CAMERA: CAMERA_OFFLINE, CAMERA_ONLINE
- SYSTEM: HEARTBEAT

### Severity Mapping

- INFO: All normal/informational events (11 types)
- WARNING: ENTRY_ESCALATED, RISK_ELEVATED, RISK_HIGH, CAMERA_OFFLINE
- CRITICAL: RISK_CRITICAL

### Design

- **Immutable**: MonitoringEvent is a frozen dataclass
- **Ephemeral**: No database persistence; delivery vehicles, not audit records
- **Independent**: No FastAPI, SQLAlchemy, PostgreSQL, or WebSocket dependencies
- **Safe**: Payload validation rejects sensitive keys (face images, embeddings, credentials, secrets, etc.)
- **Filterable**: MonitoringFilter supports exam_id, hall_id, category, event_type, min_severity

### Files Changed

| File | Change |
|---|---|
| `backend/app/services/monitoring/__init__.py` | New: public API exports |
| `backend/app/services/monitoring/events.py` | New: MonitoringEvent, enums, severity, filters, payload safety |
| `backend/app/schemas/monitoring.py` | New: Pydantic schemas for events, filters, status, alerts |
| `backend/tests/test_phase_13_1_events.py` | New: 40 tests |

### Tests

40 tests covering:
- Event creation, UUID uniqueness, immutability
- Enum validation (EventType, EventCategory, EventSeverity)
- Severity ordering and deterministic mapping
- Auto-derived category and severity from event_type
- Serialization (to_dict): minimal, full, UUID, datetime
- Payload safety: rejects 8+ sensitive key types
- Filter matching: exam_id, hall_id, category, event_type, min_severity, combined, boundary
- Pydantic schema validation: event, filter, status, alert

**Total tests:** 2133 (2093 previous + 40 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 2133 passed)

---

## Phase 13.2 — Connection Manager + Event Publisher

**Status: COMPLETE**

### Implementation

In-process real-time infrastructure: bounded buffers, connection management, event publishing.

- `backend/app/services/monitoring/event_buffer.py` — Bounded ring buffer for MonitoringEvents (default 1000 capacity)
- `backend/app/services/monitoring/alert_buffer.py` — Bounded buffer for alerts (default 200 capacity) + Alert dataclass
- `backend/app/services/monitoring/connection_manager.py` — ConnectionManager with transport-agnostic MessageTransport protocol
- `backend/app/services/monitoring/event_publisher.py` — EventPublisher: event→buffer→alert→broadcast pipeline
- `backend/app/core/config.py` — Added MONITORING_EVENT_BUFFER_SIZE, MONITORING_ALERT_BUFFER_SIZE, MONITORING_MAX_CONNECTIONS with validation

### Design

- **EventBuffer**: Thread-safe deque with maxlen. FIFO eviction. Query by MonitoringFilter.
- **AlertBuffer**: Thread-safe deque with maxlen. Alert links to event via event_id.
- **ConnectionManager**: Thread-safe dict. Transport-agnostic (MessageTransport protocol). Failed clients silently removed.
- **EventPublisher**: Idempotent by event_id. Generates alerts for WARNING/CRITICAL. Broadcasts to matching clients.

### Alert Behavior

- INFO events: stored in event buffer only, no alert
- WARNING events: stored + alert generated
- CRITICAL events: stored + alert generated
- Deduplication: by event_id (idempotent publication)

### Configuration

| Setting | Default | Description |
|---|---|---|
| `MONITORING_EVENT_BUFFER_SIZE` | 1000 | Max events in ring buffer |
| `MONITORING_ALERT_BUFFER_SIZE` | 200 | Max alerts in buffer |
| `MONITORING_MAX_CONNECTIONS` | 100 | Max concurrent WebSocket connections |

### Files Changed

| File | Change |
|---|---|
| `backend/app/services/monitoring/event_buffer.py` | New: bounded ring buffer for events |
| `backend/app/services/monitoring/alert_buffer.py` | New: bounded alert buffer + Alert dataclass |
| `backend/app/services/monitoring/connection_manager.py` | New: ConnectionManager + MessageTransport protocol |
| `backend/app/services/monitoring/event_publisher.py` | New: EventPublisher pipeline |
| `backend/app/services/monitoring/__init__.py` | Updated: exports new components |
| `backend/app/core/config.py` | Updated: 3 monitoring config settings + validator |
| `backend/tests/test_phase_13_2_infra.py` | New: 34 tests |

### Tests

34 tests covering:
- EventBuffer: append, recent, FIFO eviction, capacity, query, limit, invalid capacity, empty
- AlertBuffer: append, recent, FIFO eviction, event linkage, serialization, invalid capacity
- ConnectionManager: register, unregister, duplicate handling, max connections, broadcast filtering, cross-filter leakage, failed client removal, no-filter matches all
- EventPublisher: event storage, total_published counter, idempotency, INFO/WARNING/CRITICAL alert behavior, alert message content, no domain mutation, status method
- Configuration: default values, validation

**Total tests:** 2167 (2133 previous + 34 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 2167 passed)

---

## Phase 13.3 — WebSocket API

**Status: COMPLETE**

### Implementation

FastAPI WebSocket endpoint for real-time monitoring connections.

- `backend/app/api/v1/ws_monitoring.py` — WebSocket endpoint at `/ws/monitoring`
- `backend/app/api/v1/router.py` — Registered WebSocket router
- `backend/app/core/config.py` — Added MONITORING_HEARTBEAT_INTERVAL, MONITORING_STALE_TIMEOUT

### Design

- **Endpoint:** `WS /api/v1/ws/monitoring`
- **Filter parsing:** Query parameters validated on connect (exam_id, hall_id, category, event_type, min_severity)
- **Subscription updates:** Client sends `{"type": "subscribe", ...}` to dynamically change filters
- **Heartbeat:** Server pings every 30s, expects pong, disconnects stale clients after 60s
- **Connection manager:** Uses shared Phase 13.2 ConnectionManager (no duplicate)
- **Authentication:** NOT implemented (Phase 19); endpoint accepts unauthenticated connections
- **Error handling:** No stack traces, no secrets, no credentials, safe protocol messages only

### Connection Lifecycle

```
CONNECT → VALIDATE FILTER → REGISTER → CONNECTED → HEARTBEAT/RECEIVE → DISCONNECT → UNREGISTER
```

Cleanup on: normal disconnect, network failure, timeout, heartbeat failure, protocol errors, unexpected exceptions.

### Client Messages

| Type | Direction | Description |
|---|---|---|
| `connected` | Server→Client | Welcome message with client_id and filters |
| `ping` | Either | Heartbeat ping |
| `pong` | Either | Heartbeat response |
| `subscribe` | Client→Server | Dynamic filter update |
| `subscribed` | Server→Client | Filter update confirmation |
| `error` | Server→Client | Safe error message |

### Configuration

| Setting | Default | Description |
|---|---|---|
| `MONITORING_HEARTBEAT_INTERVAL` | 30 | Seconds between pings |
| `MONITORING_STALE_TIMEOUT` | 60 | Seconds before stale disconnect |

### Files Changed

| File | Change |
|---|---|
| `backend/app/api/v1/ws_monitoring.py` | New: WebSocket endpoint + filter parsing + heartbeat |
| `backend/app/api/v1/router.py` | Updated: registered ws_monitoring_router |
| `backend/app/core/config.py` | Updated: 2 heartbeat config settings + validator |
| `backend/tests/test_phase_13_3_websocket.py` | New: 37 tests |

### Tests

37 tests covering:
- Filter parsing: no filters, exam_id, hall_id, category, event_type, severity, combined, invalid category/event_type/severity, negative IDs
- Client message parsing: valid JSON, malformed JSON, non-object, array, None
- Connection: successful, valid filters, invalid filter rejection
- Registration: manager registration, disconnect unregisters
- Client messages: ping/pong, subscribe update, malformed JSON response, unknown message type, invalid subscribe data
- Security: no stack traces, no secrets, no database paths
- Heartbeat config: reasonable intervals

**Total tests:** 2204 (2167 previous + 37 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 2204 passed)

---

## Phase 13.4 — Event Publication Wiring

**Status: COMPLETE**

### Implementation

Connected existing domain operations (Phases 9-12) to the EventPublisher.
Events are published AFTER successful database commit in each router.

### Architecture Decision: Post-Commit Publication

All service functions commit internally (service commits, router does not).
Therefore publication happens in routers AFTER the service call returns.

```
Router endpoint
    ↓
Service call (commits internally)
    ↓
Service returns committed ORM object
    ↓
Router publishes monitoring event
    ↓
EventPublisher → EventBuffer → AlertBuffer → ConnectionManager
```

Exception: `detect_security_signals` in `proxy_risk.py` — the service flushes only, the router commits. Publication happens after router commit.

### Domain → Event Mappings

| Domain Operation | Event Type | Severity | Alert |
|---|---|---|---|
| `create_entry_verification` | ENTRY_CREATED | INFO | No |
| `begin_processing` | ENTRY_BEGAN | INFO | No |
| `evaluate_entry` (GRANTED) | ENTRY_GRANTED | INFO | No |
| `evaluate_entry` (DENIED) | ENTRY_DENIED | INFO | No |
| `evaluate_entry` (ESCALATED) | ENTRY_ESCALATED | WARNING | Yes |
| `escalate_for_review` | ENTRY_ESCALATED | WARNING | Yes |
| `resolve_escalation` | ENTRY_RESOLVED | INFO | No |
| `detect_signals` | SIGNAL_DETECTED | INFO | No |
| `assess_risk` | RISK_ASSESSED | INFO | No |
| `assess_risk` (ELEVATED) | RISK_ELEVATED | WARNING | Yes |
| `assess_risk` (HIGH) | RISK_HIGH | WARNING | Yes |
| `assess_risk` (CRITICAL) | RISK_CRITICAL | CRITICAL | Yes |
| `record_attendance` | ATTENDANCE_RECORDED | INFO | No |
| `mark_manual_attendance` | ATTENDANCE_CORRECTED | INFO | No |
| `record_health_observation` (ONLINE) | CAMERA_ONLINE | INFO | No |
| `record_health_observation` (OFFLINE) | CAMERA_OFFLINE | WARNING | Yes |

### Event Payloads

All events use operational, non-sensitive payloads:
- entity_id, student_id, exam_id, hall_id, entry_point_id
- status, decision, risk_level, risk_score, signal_type, strength
- reason, escalation_reason, resolution
- No biometric data, no credentials, no raw OCR, no filesystem paths

### Files Changed

| File | Change |
|---|---|
| `backend/app/services/monitoring/publisher.py` | **New:** 17 publication helper functions |
| `backend/app/api/v1/entry_verification.py` | **Modified:** publishes ENTRY_CREATED, ENTRY_BEGAN, ENTRY_GRANTED, ENTRY_DENIED, ENTRY_ESCALATED, ENTRY_RESOLVED |
| `backend/app/api/v1/proxy_risk.py` | **Modified:** publishes SIGNAL_DETECTED, RISK_ASSESSED, RISK_ELEVATED, RISK_HIGH, RISK_CRITICAL |
| `backend/app/api/v1/attendance.py` | **Modified:** publishes ATTENDANCE_RECORDED, ATTENDANCE_CORRECTED |
| `backend/app/api/v1/camera_health.py` | **Modified:** publishes CAMERA_ONLINE, CAMERA_OFFLINE |
| `backend/app/main.py` | **Modified:** initializes EventPublisher at app startup |
| `backend/app/services/monitoring/__init__.py` | **Modified:** exports publisher module |
| `backend/tests/test_phase_13_4_wiring.py` | **New:** 31 tests |

### Tests

31 tests covering:
- Entry verification: ENTRY_CREATED, ENTRY_BEGAN, ENTRY_GRANTED, ENTRY_DENIED, ENTRY_ESCALATED, ENTRY_RESOLVED
- Risk: SIGNAL_DETECTED, RISK_ASSESSED, RISK_ELEVATED, RISK_HIGH, RISK_CRITICAL
- Attendance: ATTENDANCE_RECORDED, ATTENDANCE_CORRECTED
- Camera: CAMERA_ONLINE, CAMERA_OFFLINE
- Publication safety: no publish when publisher is None, sensitive payload rejection (biometrics, credentials, stack traces)
- Idempotency: duplicate event_id skipped
- Alert generation: INFO no alert, WARNING generates alert, CRITICAL generates alert
- WebSocket integration: event reaches ConnectionManager, filtered client receives, non-matching rejected, multiple clients, failed client isolation
- Publisher initialization and reset

**Total tests:** 2235 (2204 previous + 31 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 2235 passed)

---

## Phase 13.5 — Alerting

**Status: COMPLETE**

### Implementation

Hardened and completed the alerting layer with deterministic classification,
safe messages, and AlertBuffer filtering.

- `backend/app/services/monitoring/alerting.py` — **New:** Deterministic alert classification module
- `backend/app/services/monitoring/alert_buffer.py` — **Modified:** Added AlertFilter, query(), by_severity(), by_event_type()
- `backend/app/services/monitoring/event_publisher.py` — **Modified:** Uses alerting module for classification and messages
- `backend/app/services/monitoring/__init__.py` — **Modified:** Exports alerting module
- `backend/tests/test_phase_13_5_alerting.py` — **New:** 52 tests
- `backend/tests/test_phase_13_2_infra.py` — **Modified:** Updated alert message test for new format

### Alert Classification (alerting.py)

Deterministic, stateless module that answers:
- `should_alert(event)` — True if event should create an alert
- `alert_message(event)` — Safe, concise operational summary
- `alert_payload(event)` — Minimal operational payload

Alert-worthy event types (5 total):
- ENTRY_ESCALATED → WARNING
- RISK_ELEVATED → WARNING
- RISK_HIGH → WARNING
- RISK_CRITICAL → CRITICAL
- CAMERA_OFFLINE → WARNING

### Alert Messages

| Event Type | Message |
|---|---|
| ENTRY_ESCALATED | Entry verification requires review. |
| RISK_ELEVATED | Elevated proxy-risk assessment detected. |
| RISK_HIGH | High proxy-risk assessment detected. |
| RISK_CRITICAL | Critical proxy-risk assessment detected. |
| CAMERA_OFFLINE | Camera reported offline. |

Messages are deterministic, safe, and contain no sensitive data.

### AlertBuffer Enhancements

- `AlertFilter` class for multi-criteria filtering (severity, event_type, exam_id, hall_id)
- `query(filter, limit)` — Filtered retrieval
- `by_severity(severity, limit)` — Severity-based retrieval
- `by_event_type(event_type, limit)` — Type-based retrieval

### Deduplication

EventPublisher deduplicates by event_id (existing Phase 13.2 behavior).
Different event_ids always create separate alerts.

### Lifecycle

```
EVENT → MonitoringEvent → should_alert() → Alert → AlertBuffer → WebSocket
```

NO: acknowledgement, resolution, dismissal, assignment, persistence.

### Files Changed

| File | Change |
|---|---|
| `backend/app/services/monitoring/alerting.py` | **New:** Alert classification module |
| `backend/app/services/monitoring/alert_buffer.py` | **Modified:** Added AlertFilter, query, by_severity, by_event_type |
| `backend/app/services/monitoring/event_publisher.py` | **Modified:** Uses alerting module |
| `backend/app/services/monitoring/__init__.py` | **Modified:** Exports alerting module |
| `backend/tests/test_phase_13_5_alerting.py` | **New:** 52 tests |
| `backend/tests/test_phase_13_2_infra.py` | **Modified:** Updated alert message test |

### Tests

52 tests covering:
- Classification (19): INFO no alert, WARNING/CRITICAL alert, each alert-worthy event type, alert-worthy set completeness
- Messages (7): Deterministic messages for all alert types, safe summaries, no sensitive data
- Identity (3): Unique alert_id, event_id linkage, serialization
- Buffer filtering (5): by_severity, by_event_type, AlertFilter query, no match, limit
- Buffer FIFO (3): Eviction, capacity, invalid capacity
- Publisher integration (9): WARNING/CRITICAL creates alert, INFO no alert, deduplication, separate events, camera_offline, risk_elevated, risk_high, context preservation
- Security (6): MonitoringEvent rejects biometrics/credentials/stack_traces/raw_ocr at creation, no filesystem paths in messages, no database URLs

**Total tests:** 2287 (2235 previous + 52 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 2287 passed)

---

## Phase 13.6 — Monitoring REST API

**Status: COMPLETE**

### Implementation

Exposed the in-memory monitoring system through 4 REST endpoints.
READ-ONLY access to EventBuffer, AlertBuffer, ConnectionManager.
No database dependency. No authentication. No persistence.

- `backend/app/api/v1/monitoring.py` — **New:** 4 REST endpoints
- `backend/app/api/v1/router.py` — **Modified:** Registered monitoring_router
- `backend/app/schemas/monitoring.py` — **Modified:** Extended with REST response models
- `backend/tests/test_phase_13_6_api.py` — **New:** 59 tests
- `backend/tests/test_phase_13_1_events.py` — **Modified:** Updated schema tests for new fields

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/monitoring/status` | Publisher status (connections, buffer counts, capacities) |
| `GET` | `/monitoring/events` | Recent events from ring buffer with filtering |
| `GET` | `/monitoring/alerts` | Recent alerts from ring buffer with filtering |
| `GET` | `/monitoring/connections` | WebSocket connection count and max |

### Events Query Parameters

- `limit` (1-200, default 50) — Max events to return
- `category` (EventCategory) — Filter by category
- `event_type` (EventType) — Filter by event type
- `min_severity` (EventSeverity) — Minimum severity level
- `exam_id` (int) — Filter by exam ID
- `hall_id` (int) — Filter by hall ID

### Alerts Query Parameters

- `limit` (1-200, default 50) — Max alerts to return
- `severity` (EventSeverity) — Filter by severity
- `event_type` (EventType) — Filter by event type
- `exam_id` (int) — Filter by exam ID
- `hall_id` (int) — Filter by hall ID

### 503 Behavior

All endpoints return 503 Service Unavailable when `get_monitoring_publisher()` returns None.
No fallback. No silent initialization.

### In-Memory Nature

- Events and alerts are in ring buffers, not databases
- Restart clears all monitoring data
- Old events disappear when buffers reach capacity
- No page/page_size pagination (ring buffer semantics)
- limit-only retrieval

### Files Changed

| File | Change |
|---|---|
| `backend/app/api/v1/monitoring.py` | **New:** 4 REST endpoints |
| `backend/app/api/v1/router.py` | **Modified:** Registered monitoring_router |
| `backend/app/schemas/monitoring.py` | **Modified:** Extended with REST response models |
| `backend/tests/test_phase_13_6_api.py` | **New:** 59 tests |
| `backend/tests/test_phase_13_1_events.py` | **Modified:** Updated schema tests for new fields |

### Tests

59 tests covering:
- Route registration (8): All 4 routes exist, wrong methods rejected
- Status (5): Response fields, empty buffers, real counts, real capacities, 503
- Events (17): Empty buffer, published events, ordering, category/event_type/min_severity/exam_id/hall_id filters, combined filters, default/custom limit, limit boundaries (200 accepted, 201 rejected, 0 rejected, negative rejected), 503
- Alerts (17): Empty buffer, alert-producing events, no alert for INFO, severity/event_type/exam_id/hall_id filters, combined filters, default/custom limit, limit boundaries, 503
- Connections (3): Response fields, real counts, 503
- Schema contract (5): Event/alert/status/connection field sets, nullable optional IDs
- Security/privacy (7): No biometrics, credentials, database URLs, filesystem paths, stack traces in events/alerts

**Total tests:** 2346 (2287 previous + 59 new), 0 failures, 0 errors
**Consecutive full-suite runs:** 2 (both 2346 passed)

---

## Phase 13.7 — Monitoring Admin UI

**Status: COMPLETE**

### Implementation

Built a monitoring admin UI using the real monitoring REST API (Phase 13.6)
and real WebSocket monitoring API (Phase 13.3). No fake data. No mock events.
No simulated live events.

- `frontend/src/lib/monitoring-api.ts` — **New:** API client + types + safePayload filter
- `frontend/src/hooks/useMonitoringSocket.ts` — **New:** WebSocket lifecycle hook
- `frontend/src/app/monitoring/page.tsx` — **New:** Monitoring page (28th route)
- `frontend/src/app/page.tsx` — **Modified:** Added Monitoring link to footer
- `frontend/src/app/dashboard/page.tsx` — **Modified:** Added Monitoring link

### REST Integration

- `getMonitoringStatus()` → status strip with real buffer counts and capacities
- `getMonitoringEvents(filters)` → initial event stream load
- `getMonitoringAlerts(filters)` → initial alerts load
- Status refreshes every 15 seconds
- All errors shown honestly (no fake zeroes)

### WebSocket Integration

- `useMonitoringSocket()` hook handles full lifecycle
- Connection states: INITIALIZING → CONNECTING → CONNECTED → DISCONNECTED → RECONNECTING
- Bounded exponential backoff reconnect (1s base, 30s max, 10 attempts)
- Server heartbeat ping responded with pong
- Clean disconnect on component unmount
- Filter updates trigger safe reconnect

### Live Event Merging

- REST initial events + WebSocket events merged by event_id
- Deduplication prevents double display
- Bounded frontend display (max 200 events)
- Client-side filter applied to live WebSocket events

### Filters Implemented

Events: category, event_type, min_severity, exam_id, hall_id, limit
Alerts: severity, event_type, limit

### Empty/Loading/Error States

- Events: "NO RETAINED EVENTS" / "Loading event stream..." / "EVENTS UNAVAILABLE"
- Alerts: "NO RETAINED ALERTS" / "Loading alerts..." / "ALERTS UNAVAILABLE"
- Status: "Loading status..." / "STATUS UNAVAILABLE"
- Each section handles failures independently

### Security/Privacy Audit

- `safePayload()` filters sensitive keys from event payloads before display
- Blocked keys: face_image, face_embeddings, biometric_data, credentials, api_key, secrets, password, token, raw_ocr, database_url, filesystem_path, stack_trace
- No sensitive data rendered in event rows or detail panels
- No console.log of monitoring payloads
- No localStorage/sessionStorage persistence of monitoring data

### Files Changed

| File | Change |
|---|---|
| `frontend/src/lib/monitoring-api.ts` | **New:** API client, types, safePayload |
| `frontend/src/hooks/useMonitoringSocket.ts` | **New:** WebSocket lifecycle hook |
| `frontend/src/app/monitoring/page.tsx` | **New:** Monitoring page |
| `frontend/src/app/page.tsx` | **Modified:** Added Monitoring to footer |
| `frontend/src/app/dashboard/page.tsx` | **Modified:** Added Monitoring link |

### Verification

- Frontend TypeScript: passes
- Frontend build: passes (28 routes)
- Backend pytest run 1: 2346 passed
- Backend pytest run 2: 2346 passed
- No migration created
- No fake data introduced
- No existing tests weakened

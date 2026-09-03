# ExamGuard Progress

## Current State

- **Phase:** 8 IN PROGRESS (8.1, 8.2, 8.3, 8.4 complete, 8.5 future)
- **Tests:** 832 passing, 0 failures, 0 errors
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

## Remaining Phase 8 Work

- **8.5 Threshold + decision integration** (FUTURE): Wire decision engine thresholds with face verification evidence
- **8.6 Failure/security/review hardening** (FUTURE): Security audit, failure modes, human review
- **8.7 Admin UI** (FUTURE): Camera capture interface, real-time verification status, review workflow
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

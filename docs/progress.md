# ExamGuard Progress

## Current State

- **Phase:** 8 IN PROGRESS (8.1, 8.2, 8.3 complete, 8.4 future)
- **Tests:** 750 passing, 0 failures, 0 errors
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

## Remaining Phase 8 Work

- **8.4 Face Verification UI** (FUTURE): Camera capture interface, real-time verification status, review workflow

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

# ExamGuard Progress

## Current State

- **Phase:** 8 IN PROGRESS (8.1 and 8.2 complete, 8.3/8.4 future)
- **Tests:** 723 passing, 0 failures, 0 errors
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

723 passed, 0 failures, 0 errors (full backend suite).

---

## Remaining Phase 8 Work

- **8.3 UniFace Integration** (FUTURE): Implement UniFace provider with real face recognition and liveness detection
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

# Face Verification

## Overview

ExamGuard verifies examinee identity by comparing a **live probe frame** from the browser camera with a stored **reference face** enrolled for the attempt.

## Components

| Piece | Location |
|---|---|
| Provider protocol + factory | `backend/app/services/face_verification/` |
| UniFace provider | `backend/app/services/face_verification/providers/uniface_provider.py` |
| Decision policy | `backend/app/services/identity_verification_decision.py` |
| Verify / evaluate API | `backend/app/api/v1/identity_verification.py` |
| Service orchestration | `backend/app/services/identity_verification.py` |
| Invigilator UI loop | `frontend/src/app/invigilator/page.tsx` |
| Camera component | `frontend/src/components/CameraCapture.tsx` |

## Pipeline

1. **Image validation** — base64 decode, format/size/corruption checks
2. **Reference load** — download `reference_face_url` (Cloudinary HTTPS) with short TTL cache
3. **Detection** — UniFace/RetinaFace: exactly one face on reference and probe
4. **Embeddings** — ArcFace; cosine similarity scored
5. **Liveness** — MiniFASNet anti-spoof score recorded as evidence
6. **Decision** — threshold policy (default match threshold `0.85`) on evaluate

## Provider selection

- `FACE_VERIFICATION_PROVIDER=uniface` — production demo (real models)
- `FACE_VERIFICATION_PROVIDER=deterministic` — local/tests without heavy models

## Failure behavior

| Condition | Client result | Attempt state |
|---|---|---|
| No face / multiple faces in **probe** | 422 with reposition message | Stays eligible (recoverable) |
| No face in **stored reference** | Clear reference error | Attempt may fail (enrollment problem) |
| Timeout / provider unavailable | Sanitized error | Fail path per service policy |
| Rate limit exceeded | Rate-limit error | Budget enforced (defaults: 5/attempt, 60/min) |

## Evidence

Successful verify returns evidence rows (e.g. `similarity_score`, `liveness_score`, `liveness`) with provider name `uniface`. Decisions are persisted on the attempt for audit/review.

## Configuration

- `FACE_VERIFICATION_MAX_IMAGE_SIZE_MB`
- `FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT` (default 5)
- `FACE_VERIFICATION_MAX_CALLS_PER_MINUTE` (default 60)
- `IDENTITY_VERIFICATION_MATCH_THRESHOLD` (default 0.85)
- `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR`

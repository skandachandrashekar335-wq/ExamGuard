# Real Biometric Verification & UniFace Neural Pipeline

## 1. Executive Summary

ExamGuard integrates `yakhyo/uniface` (v4.0.0) via ONNX Runtime for local, privacy-preserving, zero-cloud facial verification. Facial images are processed completely on-premise/in-container without transmitting candidate biometric data to third-party APIs.

- **Library**: `uniface` (v4.0.0)
- **Runtime**: ONNX Runtime (CPU / CUDA)
- **Local Model Cache**: `~/.uniface/models/` (~30 MB total model weights)
- **Supported Encodings**: JPEG, PNG (BGR 3-channel decoded via OpenCV)
- **Privacy Standard**: Zero biometric persistence — raw face images are discarded after inference; embeddings are transiently compared in-memory and never stored in audit logs or databases.

---

## 2. Neural Architecture

```
                    ┌───────────────────────────────┐
                    │  Reference Image & Probe Image│
                    └───────────────┬───────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │                RetinaFace Face Detection               │
       │   - Multi-task cascaded face detector                  │
       │   - Predicts bounding box + 5 facial landmarks         │
       │   - Enforces single face constraint (count == 1)       │
       └────────────┬──────────────────────────────┬────────────┘
                    │                              │
         Reference Landmarks                  Probe Landmarks
                    │                              │
                    ▼                              ▼
       ┌─────────────────────────┐    ┌─────────────────────────┐
       │    ArcFace Recognition  │    │    ArcFace Recognition  │
       │  512-D L2 Embedding     │    │  512-D L2 Embedding     │
       └────────────┬────────────┘    └────────────┬────────────┘
                    │                              │
                    └───────────────┬──────────────┘
                                    │
                                    ▼
                     Cosine Similarity Calculation
                      score = dot(emb_ref, emb_probe)
                                    │
                                    ├──────────────────────────┐
                                    │                          ▼
                                    │             ┌─────────────────────────┐
                                    │             │ MiniFASNet Anti-Spoofing│
                                    │             │ Evaluates probe texture │
                                    │             │ Outputs is_real & conf  │
                                    │             └────────────┬────────────┘
                                    │                          │
                                    ▼                          ▼
       ┌────────────────────────────────────────────────────────────────┐
       │               ExamGuard Decision Engine                        │
       │  Evaluates similarity score, liveness, and quality signals     │
       └────────────────────────────────────────────────────────────────┘
```

---

## 3. Decision Policy & Threshold Audit

ExamGuard employs a strict, non-bypassable three-tier decision boundary:

$$\begin{cases}
\text{MATCH} & \text{if } \text{similarity} \ge 0.68 \text{ and liveness passed} \\
\text{INCONCLUSIVE} & \text{if } 0.52 \le \text{similarity} < 0.68 \text{ or degraded image quality} \\
\text{NO\_MATCH} & \text{if } \text{similarity} < 0.52 \text{ or liveness check fails}
\end{cases}$$

### Strict Invariants:
1. **Never Lowered or Bypassed**: Thresholds are compiled in `backend/app/core/config.py` and validated at startup. API parameters cannot override or relax these thresholds.
2. **Anti-Spoofing Priority**: A detected presentation attack (print, screen, replay) results in an immediate `NO_MATCH` regardless of similarity score and triggers a `SecurityAlert` of type `SPOOF_ATTEMPT`.
3. **Inconclusive Escalation**: Inconclusive verifications are dispatched to the Chief Superintendent manual review queue. Manual reviewers cannot overwrite the biometric score — their manual decision is recorded separately with audit logs.

---

## 4. Real UniFace vs Deterministic Provider

| Capability | Real UniFace Provider (`uniface`) | Deterministic Provider (`deterministic`) |
| :--- | :--- | :--- |
| **Allowed in Production** | **YES** (Mandatory) | **STRICTLY PROHIBITED** (Fails startup) |
| **Model Execution** | ONNX Runtime RetinaFace + ArcFace + MiniFASNet | Pre-computed seeded mathematical formulas |
| **No Face Detected** | Raises `FaceVerificationError(NO_FACE_DETECTED)` | Returns static score or simulated error |
| **Multiple Faces** | Raises `FaceVerificationError(MULTIPLE_FACES_DETECTED)` | Not evaluated |
| **Spoof Detection** | Neural texture analysis (MiniFASNet) | Mock flag |
| **Latency** | 80–250 ms (CPU dependent) | < 2 ms |

---

## 5. Test Suite Verification

### Real UniFace Provider Tests:
- `backend/tests/test_uniface_provider.py`: Validates model loading, OpenCV decoding, landmark alignment, and cosine similarity.
- `backend/tests/test_verify_face_integration.py`: End-to-end integration between camera frame ingestion and UniFace inference.

### Isolated Deterministic Tests:
- Used in fast CI unit tests (`test_decision_engine.py`, `test_phase_10_*.py`) to test state transitions and RBAC without downloading 30 MB neural weights.

---

## 6. How to Test Real Face Images

### 6.1 Interactive Verification with cURL:

To verify a probe image against a reference image using the real UniFace pipeline:

```bash
# Set environment
export FACE_VERIFICATION_PROVIDER=uniface

# Run verification request
curl -X POST http://127.0.0.1:8000/api/v1/identity-verification/verify \
  -H "Authorization: Bearer <TOKEN>" \
  -F "exam_id=1" \
  -F "student_id=1" \
  -F "probe_image=@/path/to/live_candidate_photo.jpg"
```

### 6.2 Expected Responses:

**Genuine Matching Candidate:**
```json
{
  "decision": "MATCH",
  "similarity_score": 0.812,
  "liveness_passed": true,
  "provider": "uniface",
  "reasoning": "Similarity score 0.812 exceeds threshold 0.680"
}
```

**Spoof / Replay Presentation:**
```json
{
  "decision": "NO_MATCH",
  "similarity_score": 0.745,
  "liveness_passed": false,
  "provider": "uniface",
  "reasoning": "Liveness check failed — possible spoof attempt"
}
```

**Unregistered / Impersonator:**
```json
{
  "decision": "NO_MATCH",
  "similarity_score": 0.312,
  "liveness_passed": true,
  "provider": "uniface",
  "reasoning": "Similarity score 0.312 is below threshold 0.520"
}
```

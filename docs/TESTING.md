# Testing

## Backend

```bash
cd backend
pytest -q
```

- Framework: pytest (+ pytest-asyncio)
- Scope: models, services, API integration, face-verification pipeline, security/rate-limit cases
- Last full suite run on this machine: **2518 passed** (2026-09-24)

Targeted examples:

```bash
pytest tests/test_live_frame_recovery.py -q
pytest tests/test_verify_face_integration.py -q
pytest tests/test_face_verification_pipeline.py -q
```

## Frontend

```bash
cd frontend
npm run lint
npm run build
```

Playwright specs:

- `frontend/tests/e2e.spec.ts`
- `frontend/tests/crud-workflows.spec.ts`

Install Playwright browsers before running E2E if not already present.

## What is automated vs manual

| Area | Automated | Manual |
|---|---|---|
| API auth, RBAC, verification service | Yes | — |
| Face provider pipeline (mocked / unit) | Yes | — |
| Production HTTP chain (API) | Scripted checks | — |
| Live human webcam UX in browser | Partial (bundle/deploy checks) | **Required for full acceptance** |
| Cross-person NO_MATCH with real identities | Not fully | Manual with consented images |

Do not claim full biometric acceptance without a real human camera test on the deployed UI.

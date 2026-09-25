# Testing

## Backend

```bash
cd backend
pytest -q
```

- Framework: pytest (+ pytest-asyncio)
- Scope: models, services, API integration, face-verification pipeline, security/rate-limit cases
- Last full suite run: **2536 passed** (2026-09-25)

Targeted examples:

```bash
pytest tests/test_live_frame_recovery.py -q
pytest tests/test_verify_face_integration.py -q
pytest tests/test_face_verification_pipeline.py -q
```

## Frontend

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

ESLint currently reports a pre-existing baseline (69 errors / 39 warnings)
dominated by React Compiler rules across many pages; it is not yet CI-gated.

## CI

`.github/workflows/` runs on every push and pull request:

- `backend.yml` — install from `pyproject.toml`, `pytest -q` (with system
  OCR/PDF dependencies installed to mirror the Docker image)
- `frontend.yml` — `npm ci`, `npx tsc --noEmit`, `npm run build`;
  ESLint runs informationally (non-gating) until the baseline is cleared

CI parity: the suite passes with no local `.env` at all
(**2535 passed + 1 env-gated skip**); with local environment:
**2536 passed**. The test harness runs `/health` checks against the test
database, so no test depends on a reachable external database.

Playwright specs:

- `frontend/tests/e2e.spec.ts`
- `frontend/tests/crud-workflows.spec.ts`
- `frontend/tests/acceptance-e.spec.ts` — invigilator live-verification
  browser acceptance (requires `EG_INVIGILATOR_TOKEN`; run against a local
  dev server with `EG_BASE_URL`)

Install Playwright browsers before running E2E if not already present.

## What is automated vs manual

| Area | Automated | Manual |
|---|---|---|
| API auth, RBAC, verification service | Yes | — |
| Face provider pipeline (mocked / unit) | Yes | — |
| Enrollment / reference authorization (C, D) | Yes (regression tests + production acceptance, 17/17) | — |
| Production HTTP chain (API) | Scripted checks (A verified against live UniFace) | — |
| Invigilator camera modal, recoverable probe errors, capture-loop cleanup | Yes (Playwright, fake camera device, production API) | Real human pass on deployed bundle (issue #1) |
| Camera permission-denied path | Not fully | Manual browser check (issue #1) |
| Cross-person NO_MATCH with real identities | Not fully | Manual with consented images (issue #2) |

Do not claim full biometric acceptance without a real human camera test on the deployed UI.

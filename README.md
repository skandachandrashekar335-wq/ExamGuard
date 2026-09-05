# ExamGuard

AI-powered Examination Entry Verification, Anti-Proxy, Security, and Attendance Management Platform.

## Project Status

- **Phase:** 12 IN PROGRESS (12.1 complete)
- **Backend:** 1931 tests passing (0 failures, 0 errors)
- **Frontend:** 24 pages (Next.js 16.3.3, React 19, TypeScript, Tailwind v4)
- **Tech stack:** FastAPI + SQLAlchemy + PostgreSQL (backend), Next.js + TypeScript + Tailwind (frontend)

### Phase 8 — Face Verification

- **8.1** Provider abstraction: `FaceVerificationProvider` Protocol, `DeterministicProvider`, factory
- **8.2** Service integration: `verify_face()` wires provider into identity verification service, `POST /{attempt_id}/verify-face` API endpoint
- **8.3** UniFace integration: Real face detection (RetinaFace), recognition (ArcFace), anti-spoofing (MiniFASNet) via ONNX Runtime
- **8.4** Real pipeline: Robust input validation (base64, format, size, corruption, dimensions), image validation helpers, defense-in-depth at API/service layers, 82 comprehensive tests
- **8.5** Threshold + decision integration: Configurable thresholds, near-threshold zone, decision metadata for audit, config validation, 87 comprehensive tests
- **8.6** Failure/security/review hardening: Typed failure categories, rate limiting, human review/override, audit trail, API error sanitization, 77 comprehensive tests
- **8.7** Admin face verification UI: Real browser camera capture, reference image upload, verify-face integration, evidence display, human review/override, audit trail
- **8.8** Integration testing + final hardening: 107 integration tests covering full pipeline, providers, decision engine, lifecycle, evidence, concurrency, security invariants, failure matrix, API contracts, rate limiting, privacy audit

### Phase 9 — Camera & Entry Point Management

- **9.1** Domain foundation: Camera, EntryPoint, CameraEntryPointMapping models + migration 016 + 53 model tests
- **9.2** CRUD API: 15 REST endpoints (cameras, entry-points, camera-entry-points) + 42 API integration tests + FK cleanup fixes
- **9.3** Admin UI: Camera list/create/edit, entry point list/create/edit, mapping list/create/disable, API client, 23 frontend routes
- **9.4** Device health/status: Health observation boundary, last_seen_at/last_health_check_at/health_reason, health API endpoints, 53 tests
- **9.5** Secure communication: Device credential provisioning, authentication, revocation, SHA-256 hashing, device health API, 54 tests
- **9.6** Integration/hardening: Cross-component integration tests (44 tests), full domain audit

### Phase 10 — Real-Time Examination Entry Verification

- **10.1** Domain model: EntryVerification model, 4 enums, state machine, migration 019, 49 model tests
- **10.2** Service layer: 10 service functions, 71 service tests
- **10.3** REST API: 10 endpoints, 56 API tests
- **10.4** Admin UI: List page, detail page, workflow actions, escalation/resolve UI
- **10.5** Integration tests: 76 cross-component integration tests

### Phase 11 — Anti-Proxy Detection (COMPLETE)

- **11.1** Domain foundation: SecuritySignal + ProxyRiskAssessment models, 3 enums, 6 config settings, migration 020, 47 model tests
- **11.2** Deterministic signal detection: 14 signal detectors, idempotent service, 72 tests, migration 021
- **11.3** Proxy risk scoring: Pure deterministic scoring engine, risk assessment persistence, 43 tests
- **11.4** REST API: 5 endpoints (detect signals, list signals, assess risk, list assessments, get latest), 40 API tests
- **11.5** Admin risk UI: proxy-risk-api.ts client, risk panel on entry verification detail page with signals table, assessment summary/history, detect/assess buttons
- **11.6** Integration & hardening: 86 integration tests, security/privacy audit, 2 consecutive full suite runs (1889 passed)

### Phase 12 — Attendance Management (IN PROGRESS)

- **12.1** Domain foundation: AttendanceRecord + AttendanceEvent models, 3 enums (AttendanceStatus, EntryMethod, AttendanceEventType), migration 022, 42 model tests

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### PostgreSQL Setup (Windows)

1. Download and install PostgreSQL from https://www.postgresql.org/download/windows/
2. During installation, set a password for the `postgres` user.
3. Open **pgAdmin** (installed with PostgreSQL) or use the SQL shell.
4. Create the development database:

```sql
CREATE DATABASE examguard;
```

5. Create a development user (optional but recommended):

```sql
CREATE USER examguard_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE examguard TO examguard_user;
```

6. Copy `.env.example` to `.env` and update `DATABASE_URL` with your credentials:

```
DATABASE_URL=postgresql://examguard_user:your_password@localhost:5432/examguard
```

### Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev]"
```

### Database Migrations

```bash
cd backend
alembic upgrade head     # Apply all migrations
alembic downgrade -1     # Roll back one migration
alembic history          # View migration history
alembic revision --autogenerate -m "description"  # Generate new migration
```

### Running the Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Running Tests

```bash
cd backend
pytest -v
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:3000

### Environment Variables

Copy `.env.example` to `.env` and configure as needed. Required variables:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@localhost:5432/examguard` |
| `SECRET_KEY` | Application secret key | `change-me-to-a-random-secret-key` |
| `CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` |

## Architecture

See `docs/architecture.md` for detailed architecture documentation.

# ExamGuard

AI-powered Examination Entry Verification, Anti-Proxy, Security, and Attendance Management Platform.

## Project Status

- **Phase:** 8 IN PROGRESS (8.1, 8.2, and 8.3 complete)
- **Backend:** 750 tests passing (0 failures, 0 errors)
- **Frontend:** 20 pages (Next.js 16.3.3, React 19, TypeScript, Tailwind v4)
- **Tech stack:** FastAPI + SQLAlchemy + PostgreSQL (backend), Next.js + TypeScript + Tailwind (frontend)

### Phase 8 — Face Verification

- **8.1** Provider abstraction: `FaceVerificationProvider` Protocol, `DeterministicProvider`, factory
- **8.2** Service integration: `verify_face()` wires provider into identity verification service, `POST /{attempt_id}/verify-face` API endpoint
- **8.3** UniFace integration: Real face detection (RetinaFace), recognition (ArcFace), anti-spoofing (MiniFASNet) via ONNX Runtime
- **8.4** Camera capture UI (future)

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

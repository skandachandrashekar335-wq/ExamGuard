# Engineering Incidents

Real incident reports from ExamGuard operations. This is an engineering log,
not marketing.

---

## 2026-09-25 — Production API crash after redeploy: `ModuleNotFoundError: No module named 'psycopg'`

**Severity:** High (API unavailable during the incident window)
**Status:** Resolved
**Commit:** `087f726` — `fix: pin sqlalchemy<2.1 to keep psycopg2 dialect on postgresql:// URLs`

### Problem

A routine Railway redeploy (shipping the invigilator verification UX and
candidate-enrollment enforcement, `d258408`) came up crashed:

- `GET /health` returned `502 Bad Gateway`
- Railway service status: `Crashed`

The startup traceback ended at:

```text
File "/app/app/core/database.py", line 16, in <module>
    engine = create_engine(
File ".../sqlalchemy/dialects/postgresql/psycopg.py", line 497, in import_dbapi
    import psycopg
ModuleNotFoundError: No module named 'psycopg'
```

### Cause

`backend/pyproject.toml` declared an unbounded dependency:

```toml
"sqlalchemy>=2.0.0"
```

SQLAlchemy **2.1.0** (released the same day) changed the default driver for
`postgresql://` URLs to the psycopg 3 dialect, which imports the `psycopg`
module. The backend image installs only `psycopg2-binary`. The rebuild
resolved SQLAlchemy 2.1.0 (the previous image had been built when 2.0.x was
latest), so the app crashed at import time before serving any request.

### Resolution

1. Reproduced locally in a clean virtualenv: `sqlalchemy==2.1.0` +
   `psycopg2-binary` raises the identical `ModuleNotFoundError` from
   `create_engine("postgresql://...")`.
2. Pinned the dependency: `"sqlalchemy>=2.0.0,<2.1"` (commit `087f726`).
3. Redeployed from source.

### Verification

```json
GET /health → 200
{"status":"healthy","database":"connected","face_provider":"uniface"}
```

Production acceptance checks C + D were re-run against the redeployed API:
**17/17 passed**, demo data restored, no evidence rows recorded on rejected
verification attempts.

### Follow-up

- The dependency bound is committed in `backend/pyproject.toml`.
- CI (`.github/workflows/backend.yml`) installs the backend from
  `pyproject.toml` on a clean runner on every push, so dependency-resolution
  drift fails visibly instead of at production deploy time.
- A dependency lockfile (e.g. `pip-compile`) remains an optional future
  hardening step.
- Unrelated but adjacent: the demo deployment still uses a placeholder
  `SECRET_KEY` / `APP_ENV=development` — tracked in issue #4.

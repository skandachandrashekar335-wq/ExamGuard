# Contributing to ExamGuard

Thanks for helping improve ExamGuard.

## Development setup

1. Python 3.11+, Node.js 18+, PostgreSQL 15+
2. Backend: `cd backend && pip install -e ".[dev]" && alembic upgrade head`
3. Frontend: `cd frontend && npm install`
4. Copy `.env.example` → `.env` and `frontend/.env.example` → `frontend/.env.local` (local values only)

## Branches

- `main` — stable integration branch
- Feature work: short-lived branches (`feat/…`, `fix/…`, `docs/…`) merged via pull request when practical

## Commits

Use conventional prefixes:

- `feat: …`
- `fix: …`
- `test: …`
- `docs: …`
- `refactor: …`
- `chore: …`

Avoid low-signal messages (`update`, `final`, `wip`).

## Testing

- Run backend tests before opening a PR: `cd backend && pytest -q`
- Add or update tests for behavior changes (especially auth, verification, and data integrity)
- Do not commit secrets, `.env` files, tokens, or real student biometric images

## Pull requests

- Describe **what** changed and **why**
- Link related issues
- Keep diffs focused; separate unrelated refactors
- Note deployment impact (frontend / backend / migrations)

## Security

Report vulnerabilities privately per [SECURITY.md](SECURITY.md). Never include credentials in issues or screenshots.

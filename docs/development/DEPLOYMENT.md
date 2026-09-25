# Deployment

## Current demo deployment

| Service | Platform | URL |
|---|---|---|
| Frontend | Vercel | https://exam-guardian-management.vercel.app |
| Backend | Railway | https://examguard-production-ef78.up.railway.app |
| Database | Neon PostgreSQL | Connection via `DATABASE_URL` (secret) |

Health check: `GET /health` → `{"status":"healthy","database":"connected","face_provider":"uniface"}` when the face provider is healthy.

## Frontend (Vercel)

- Project root: `frontend/`
- Framework: Next.js
- Required env: `NEXT_PUBLIC_API_URL` pointing at the deployed backend origin
- Deploy the monorepo with the Vercel project configured to the `frontend` directory

## Backend (Railway)

- Build: `backend/Dockerfile` or Nixpacks
- Install includes optional extra: `pip install ".[uniface]"` for real face verification
- Required secrets (set in Railway, not in git):
  - `SECRET_KEY`
  - `DATABASE_URL`
  - `FACE_VERIFICATION_PROVIDER=uniface`
  - Cloudinary credentials if using CDN face storage
  - Firebase-related settings as needed for token exchange
- `APP_ENV=development` is currently used on the demo so placeholder `SECRET_KEY` validation is not rejected; replace with a strong secret before any real production use

## Migrations

```bash
cd backend
alembic upgrade head
```

Run migrations before or as part of backend rollout when schema changes ship.

## Post-deploy checks

1. `GET /health` — status, database, face provider
2. Frontend loads authenticated routes
3. Demo load + reference-face upload returns absolute `https://` URL
4. Invigilator verify-face returns UniFace evidence for a real face probe

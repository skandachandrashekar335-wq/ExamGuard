PRODUCTION QA REPORT — 2026-09-20 (Updated)
==================================

DEPLOYMENT
----------
Frontend:  https://exam-guardian-management.vercel.app (Vercel project: exam-guard)
Backend:   https://examguard-production-ef78.up.railway.app
Database:  Neon PostgreSQL (connected)
Firebase:  exam-guard-75675 (Google Auth)
Git:       main branch, HEAD = c3326d4

DEPLOYED COMMITS (latest session)
--------------------------------
c3326d4 docs: update README and TRD to reflect current project state
7a56595 fix: resolve Google auth redirect issue and Firebase token verification
255f7d5 docs: add production QA report for deployment verification
48f358d fix: always include production Vercel domains in CORS allow_origins
53660bf fix: add production Vercel domains to CORS_ORIGINS default
0fdc1fe style: redesign form controls for professional enterprise look

VERIFICATION RESULTS
--------------------
[PASS] Frontend returns 200
[PASS] Production frontend uses Railway API (not localhost)
[PASS] Backend health: healthy, database connected
[PASS] Firebase config (project exam-guard-75675) present in production JS
[PASS] Google sign-in UI on protected pages ("Continue with Google")
[PASS] CORS: access-control-allow-origin matches production domain
[PASS] Firebase exchange endpoint responds (401 for invalid token = correct)
[PASS] No critical console errors
[PASS] TypeScript compiles clean
[PASS] Production build: 33 routes, 0 errors
[PASS] Latest form CSS (eg-form-group, eg-input-error, eg-textarea) deployed
[PASS] Next.js dev indicator removed (devIndicators: false)

CRITICAL FIXES THIS SESSION
----------------------------
1. CORS_ORIGINS: Railway env var only had localhost:3000. Added production
   Vercel domains to both code default and middleware hardcoded list to
   guarantee Firebase auth exchange works from production frontend.

2. NEXT_PUBLIC_API_URL: Added to Vercel production env vars (was missing).
   Points to https://examguard-production-ef78.up.railway.app.

AUTH FLOW VERIFICATION
----------------------
Google -> Firebase (exam-guard-75675) -> exchange endpoint -> JWT token
- Auth gate renders correctly on protected pages
- Exchange endpoint responds to POST with correct CORS headers
- Full Google OAuth popup cannot be tested headlessly (requires user action)

REMAINING ITEMS
---------------
- Full end-to-end Google OAuth login test requires manual user verification
- Railway FIREBASE_WEB_API_KEY env var: recommended to set explicitly (startup warning when not set)
- Railway CORS_ORIGINS env var: overridden by code (hardcoded production origins)
- Firebase Web API Key: PUBLIC by design, safe as config.py default (matches frontend firebase_init.ts)

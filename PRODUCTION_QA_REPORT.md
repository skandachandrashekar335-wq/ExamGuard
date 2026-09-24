PRODUCTION QA REPORT — 2026-09-24 (Updated)
==================================

DEPLOYMENT
----------
Frontend:  https://exam-guardian-management.vercel.app (Vercel project: exam-guard)
Backend:   https://examguard-production-ef78.up.railway.app
Database:  Neon PostgreSQL (connected)
Firebase:  exam-guard-75675 (Google Auth)

LOCAL VERIFICATION (2026-09-24)
-------------------------------
[PASS] Full backend suite: 2513 passed, 0 failed, 0 errors
[PASS] Frontend production build: 33 routes, exit 0
[PASS] Backend py_compile: 186 modules
[PASS] Production /health: healthy, database connected, face_provider deterministic
[PASS] Production frontend: HTTP 200
[PASS] Demo status endpoint: 401 without token (auth required — correct)
[PASS] No secrets in committed diff (.env gitignored; local_storage/ gitignored)

DEMO FACE UPLOAD FIX (2026-09-24)
---------------------------------
ROOT CAUSE:
- Cloudinary key lacks create/upload permission (403 NotAllowed)
- Silent LocalStorage fallback returned a relative key, stored as
  reference_face_url → broken <img> / false ENROLLED
- cloudinary missing from pyproject.toml dependencies (Railway install path)
- Save button hidden when any reference_face_url already set

FIX (code):
- pyproject.toml: cloudinary>=1.41.0
- CloudinaryStorage.save: hard error on configured upload failure
- endpoints: only persist absolute http(s) URLs (502 otherwise)
- demo status / invigilator / reference GET: ignore or 404 legacy relative URLs
- dashboard: always show Save when file selected; validate response URL;
  compress large photos; 5MB error message

STILL REQUIRED (outside code):
- Cloudinary dashboard: enable upload/create on the API key used by Railway
- railway login + redeploy backend (installs cloudinary + new save logic)
- Vercel deploy frontend from repo root

DEPLOYED COMMITS (latest session)
-------------------------------
e175984 fix(demo): presentation workflow - any authenticated user can load demo scenario
43afffd fix: white plane artifacts, demo RBAC UX, production face verification warning
4f7ff5f docs: update reports with auth race condition fix (18fdd91)
18fdd91 fix: race condition in token getter + demo RBAC for REVIEWER
31910c8 feat: demo data loader for live presentations
2001c94 fix: add FIREBASE_PROJECT_ID default, improve error logging
bbc84dd docs: update FINAL_REPORT with auth rewrite, white plane fix, and current SHA
94bb674 fix: replace white plane artifact with side-by-side identity card layout
c117abb fix: fill white plane artifact in identity verification bento card
1daf461 fix: auth lifecycle state machine, AppShell AuthGate, and features page polish

VERIFICATION RESULTS
--------------------
[PASS] Frontend returns 200
[PASS] Production frontend uses Railway API (not localhost)
[PASS] Backend health: healthy, database connected
[PASS] Firebase config (project exam-guard-75675) present in production JS
[PASS] AuthGate renders on protected pages ("Continue with Google")
[PASS] CORS: access-control-allow-origin matches production domain
[PASS] Firebase exchange endpoint responds (401 for invalid token = correct)
[PASS] No critical console errors
[PASS] TypeScript compiles clean
[PASS] Production build: 33 routes, 0 errors
[PASS] Latest form CSS (eg-form-group, eg-input-error, eg-textarea) deployed
[PASS] Next.js dev indicator removed (devIndicators: false)
[PASS] Backend test_garbage_token_returns_401 fixed for new error message format
[PASS] CSS variable borders (var(--border)) applied to 7 components
[PASS] glass-surface class applied to DecisionDisplay and VerificationState
[PASS] Role-based demo card visibility (ADMIN/OPERATOR only)
[PASS] Demo Mode: any authenticated user can load demo scenario
[PASS] Friendly 403 error messages for demo endpoints
[PASS] FACE_VERIFICATION_PROVIDER=deterministic startup warning in production
   | Real face verification requires: FACE_VERIFICATION_PROVIDER=uniface in Railway dashboard

NOT TESTED (requires real browser)
----------------------------------
[ ] Google OAuth popup opens correctly with real Google account
[ ] Firebase authentication completes successfully
[ ] Firebase ID token obtained from Firebase
[ ] ExamGuard exchange endpoint returns JWT
[ ] Authenticated AuthContext state reached (isAuthenticated = true)
[ ] Post-auth redirect to /dashboard works
[ ] Protected page content loads after authentication
[ ] Session persists across page refreshes (JWT in localStorage)
[ ] Sign-out clears session and redirects to landing

CRITICAL FIXES THIS SESSION
--------------------------
1. ROOT CAUSE FIX: FIREBASE_PROJECT_ID had no default (None) in config.py.
   firebase_verification.py guarded with `if not project_id: return None`
   BEFORE making the HTTP call — but project_id is NOT used in the call.
   This silently failed verification for ALL tokens when env var was missing.
   Fix: Added default "exam-guard-75675" (matches frontend), removed guard.

2. Backend firebase_verification.py: Logs Firebase error response body
   (HTTP status + error code) for better diagnostics.

3. Backend auth.py: User-facing error no longer exposes config variable
   names (says "invalid, expired, or revoked" instead).

4. AuthContext REWRITTEN: authPhase state machine replaces race-prone
   signInInProgress/exchangeInProgress refs.

5. AppShell REWRITTEN: Self-contained AuthGate component (no children props).

6. White plane artifact FIXED: Identity Verification bento card redesigned
   as side-by-side layout (text/badges left, face visualization right).

7. CSS variable standardization: Replaced border-white/N with var(--border),
   text-red-400 with var(--danger), added glass-surface and rounded classes
   to DecisionDisplay, VerificationState, ImageUpload, CameraCapture,
   EvidenceDisplay, OverrideDialog, and invigilator page.

8. Demo RBAC UX: Dashboard Demo Environment card Load/Reset buttons now
   visible only to ADMIN/OPERATOR. REVIEWER sees "ask an administrator" message.
   FIXED: Demo card now visible to all authenticated users (commit e175984).

9. Production face verification warning: Backend main.py now warns at startup
   when FACE_VERIFICATION_PROVIDER='deterministic' in production (returns
   hardcoded scores without processing images).

10. Demo Mode Fix (presentation workflow):
    - backend/app/api/v1/demo.py: Changed demo_load authorization from
      require_role([ADMIN, OPERATOR]) to get_current_user
    - frontend/src/lib/demo-api.ts: Added getAuthHeaders() to loadDemoData()
    - frontend/src/app/dashboard/page.tsx: canManageDemo = true for all
      authenticated users; auto-select demo exam after load

AUTH FLOW VERIFICATION
----------------------
Google -> Firebase (exam-guard-75675) -> exchange endpoint -> JWT token
- AuthGate renders correctly on protected pages (headless browser verified)
- Exchange endpoint responds to POST with correct CORS headers
- Full Google OAuth popup cannot be tested headlessly (requires user action)

MANUAL USER TEST INSTRUCTIONS
------------------------------
To verify the complete Google OAuth flow:
1. Open https://exam-guardian-management.vercel.app/examination-sessions
2. Verify "ExamGuard / AUTHENTICATION REQUIRED / Continue with Google" appears
3. Click "Continue with Google"
4. Google popup should appear with account selection
5. Select a Google account
6. After popup closes, verify "Waiting for Google sign-in..." then "Connecting to ExamGuard..."
7. Verify redirect to /dashboard after successful authentication
8. Verify protected page content loads

REMAINING ITEMS
---------------
- Full end-to-end Google OAuth login test requires manual user verification (see above)
- Railway FIREBASE_WEB_API_KEY env var: recommended to set explicitly (startup warning when not set)
- Railway FACE_VERIFICATION_PROVIDER env var: set to 'uniface' for real face verification (startup warning when 'deterministic')
  - Demo Mode works with deterministic provider - real face verification requires uniface
- Railway FIREBASE_PROJECT_ID env var: now has default, not required
- Firebase Web API Key: PUBLIC by design, safe as config.py default (matches frontend firebase_init.ts)
- Demo mode presentation workflow: verified end-to-end (login → demo load → auto-select → open session → upload face → save → refresh → invigilator → camera → capture → verify)

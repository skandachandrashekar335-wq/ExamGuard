# ExamGuard Application Flow Documentation

## Landing Page

- **Route**: `/`
- **Purpose**: Homepage / hero section introducing the examination entry verification system
- **Who can access**: Public (no authentication required)
- **Navigation entry**: Top-level route; accessible from anywhere via browser address bar or homepage link
- **Buttons/actions**:
  - "ACCESS SYSTEM" — navigates to `/examination-sessions` (or login if not authenticated)
  - READY, DETECT, VERIFY, DECIDE buttons (visual pipeline stages)
- **API calls**: None on load
- **Success behavior**: Page renders with monochrome editorial design, verification pipeline visualization
- **Error behavior**: TypeScript compilation error for `--progress` CSS variable (pre-existing, known issue)
- **Role restrictions**: Public; no authentication state required

## Authentication / Login

- **Route**: `/` (initial load) → protected routes after auth
- **Purpose**: Firebase/Google sign-in to establish ExamGuard session
- **Who can access**: Public (anon access to landing; protected routes after auth)
- **Navigation entry**: "ACCESS SYSTEM" button on homepage, or direct URL entry to protected routes

### Google Sign-In Flow

1. User clicks "Continue with Google" or "ACCESS SYSTEM"
2. Firebase Authentication popup opens (`signInWithPopup` with `GoogleAuthProvider`)
3. User selects Google account
4. Frontend gets Firebase ID token (`user.getIdToken()`)
5. Frontend calls `POST /api/v1/auth/firebase/exchange` with the Firebase ID token
6. Backend verifies token server-side, maps Firebase identity to ExamGuard user
7. User receives REVIEWER role by default; ADMIN only via `INITIAL_ADMIN_EMAILS`
8. ExamGuard JWT issued (30 min expiry, HS256)
9. Frontend AuthContext updated with user state, role, `isAuthenticated: true`
10. Role-specific UI navigation visible

### Sign-Out Flow

1. User clicks "LOG OUT" in the header
2. `signOut()` action dispatchs: Firebase sign-out + ExamGuard session cleanup
3. `firebaseSignOut(auth)` — signs out from Firebase Authentication
4. Auth state cleared: `user: null`, `isAuthenticated: false`, `requiresOnboarding: true`
5. Redirect to login / landing page
6. All protected routes redirect to `/`

### Protected Routes

- **Dashboard**: `/dashboard` — ADMIN/OPERATOR/REVIEWER depending on role
- **Examination sessions**: `/examination-sessions` — role-dependent access
- **Exams**: `/exams` — role-dependent access
- **Verification**: `/identity-verifications` — role-dependent access
- **Attendance**: role-dependent access
- **Security events**: `/security-events` — role-dependent access
- **Analytics**: role-dependent access
- **Audit**: role-dependent access

### Unauthenticated Behavior

- When unauthenticated and trying to access a protected route:
  - Frontend AuthContext loading state → authenticated state transition fails
  - User redirected to `/` (landing page)
  - Auth error handled gracefully (no credential leakage in error messages)
- Protected API endpoints return 401 for unauthenticated requests

### Logout Behavior

- Firebase sign-out + ExamGuard session cleanup
- Auth state reset to default (guest)
- User redirected to landing page
- Protected routes become inaccessible until re-authentication

### Frontend Navigation After Authentication

- Role-specific navigation visible in header (EXAMGUARD, Dashboard, Examinations, Verification, Attendance, Security, Analytics, Audit)
- User name/email/role displayed in header
- LOG OUT button always available
- Route protection: frontend UX only; backend RBAC is the real security boundary

## Examination Sessions

- **Route**: `/examination-sessions`
- **Purpose**: List and manage examination sessions
- **Who can access**: Role-dependent (ADMIN/OPERATOR/REVIEWER)
- **Navigation entry**: Header navigation link "EXAMINATION SESSIONS"; also from homepage "ACCESS SYSTEM"
- **Buttons/actions**:
  - "CREATE EXAMINATION SESSION" — opens detail/form page
  - View session details, candidates, status
  - Filter/search by status, hall, exam
- **API calls**: 
  - `GET /api/v1/examination-sessions` — list with pagination/filters
  - `POST /api/v1/examination-sessions` — create new session
  - `GET /api/v1/examination-sessions/{id}` — get by ID
- **Success behavior**: Session created/listed with correct data
- **Error behavior**: 404 if not found; 422 for validation errors
- **Role restrictions**: ADMIN/OPERATOR can create/view; REVIEWER may have read-only access

## Exams

- **Route**: `/exams`
- **Purpose**: Manage examinations (create, view, edit)
- **Who can access**: Role-dependent
- **Navigation entry**: Header navigation link "EXAMS"
- **Buttons/actions**:
  - "CREATE EXAM" — opens form
  - View exam list, edit, delete
  - Filter by status, subject, hall
- **API calls**:
  - `GET/POST /api/v1/exams` — list/create
  - `GET/POST /api/v1/exams/{id}` — get/update by ID
- **Success behavior**: Exam created/listed with correct data
- **Error behavior**: 404/409/422 as appropriate
- **Role restrictions**: ADMIN has full control; OPERATOR/REVIEWER read-only or limited

## Students

- **Route**: `/students` (or within examination workflow)
- **Purpose**: Student management
- **Who can access**: Role-dependent (ADMIN full control, OPERATOR/REVIEWER limited)
- **Navigation entry**: Within admin section or examination workflow
- **Buttons/actions**:
  - Create student, edit, activate/deactivate
  - Search by USN, name, ID
- **API calls**:
  - `GET/POST /api/v1/students` — list/create
  - `GET/POST /api/v1/students/{id}` — get/update by ID
- **Success behavior**: Student created/listed with correct data
- **Error behavior**: 404/409/422 as appropriate
- **Role restrictions**: ADMIN full control; OPERATOR/REVIEWER limited

## Halls

- **Route**: `/exam-halls` or `/halls`
- **Purpose**: Examination hall management
- **Who can access**: Role-dependent
- **Navigation entry**: Within admin section
- **Buttons/actions**:
  - Create hall, edit, deactivate
  - Assign cameras, entry points
- **API calls**:
  - `GET/POST /api/v1/exam-halls` — list/create
  - `GET/POST /api/v1/exam-halls/{id}` — get/update by ID
- **Success behavior**: Hall created/listed with correct data
- **Error behavior**: 404/409/422 as appropriate
- **Role restrictions**: ADMIN full control; OPERATOR/REVIEWER limited

## Registrations

- **Route**: Within examination workflow
- **Purpose**: Student exam registrations
- **Who can access**: Role-dependent
- **Buttons/actions**:
  - Register student for exam
  - View registrations, edit
- **API calls**:
  - `GET/POST /api/v1/exam-registrations` — list/create
- **Success behavior**: Registration created/listed
- **Error behavior**: 404/422 as appropriate
- **Role restrictions**: Role-dependent

## Seats

- **Route**: Within examination workflow
- **Purpose**: Seat assignment management
- **Who can access**: Role-dependent
- **Buttons/actions**:
  - Assign seat, view assignments
- **API calls**:
  - `GET/POST /api/v1/seat-assignments` — list/create
- **Success behavior**: Seat assignment created/listed
- **Error behavior**: 404/422 as appropriate
- **Role restrictions**: Role-dependent

## Hall Tickets

- **Route**: `/hall-tickets` or within workflow
- **Purpose**: Hall ticket generation and lifecycle management
- **Who can access**: Role-dependent
- **Buttons/actions**:
  - Generate hall ticket, view details, approve/reject
  - Link document, status transitions
- **API calls**:
  - `GET/POST /api/v1/hall-tickets` — list/create
  - `GET/POST /api/v1/hall-tickets/{id}` — get by ID
  - `POST /api/v1/hall-tickets/{id}/approve`, `POST /{id}/reject`
- **Success behavior**: Hall ticket created/listed with correct lifecycle state
- **Error behavior**: 404/409/422 as appropriate
- **Role restrictions**: Role-dependent

## Identity Verification

- **Route**: `/identity-verifications`
- **Purpose**: Face verification and identity confirmation
- **Who can access**: Role-dependent (ADMIN/OPERATOR/REVIEWER)
- **Navigation entry**: Header navigation link "VERIFICATION"; also from examination workflow
- **Buttons/actions**:
  - "Verify Identity" — camera capture or image upload → `POST /{attempt_id}/verify-face`
  - View evidence signals (similarity_score, liveness_score, image_quality)
  - Review decision, escalate for human review, override decision
  - "Request Review" on terminal states (COMPLETED/FAILED)
  - "Override Decision" on terminal states with reason
- **API calls**:
  - `POST /api/v1/identity-verifications` — create attempt
  - `POST /{attempt_id}/verify-face` — trigger face verification
  - `POST /{attempt_id}/evaluate` — evaluate evidence (GRANTED/DENIED/ESCALATED)
  - `POST /{attempt_id}/escalate` — escalate for human review
  - `POST /{attempt_id}/resolve` — resolve escalation (GRANTED/DENIED)
  - `POST /{attempt_id}/review` — mark as under human review (optional notes)
  - `POST /{attempt_id}/override` — override decision (new_decision + reason required)
- **Success behavior**: Evidence evaluated, decision rendered, UI updated
- **Error behavior**: 404 if attempt not found; 422 for validation errors (wrong status, wrong method, invalid decision); 403 for insufficient role
- **Role restrictions**: ADMIN/OPERATOR/REVIEWER can verify; specific actions may require minimum role
- **Loading state**: UI shows loading during face verification API calls
- **Error state**: UI displays safe error messages (no credential leakage)

## Attendance

- **Route**: Within examination workflow or dedicated attendance section
- **Purpose**: Record and track attendance per examination session
- **Who can access**: Role-dependent
- **Buttons/actions**:
  - Record check-in/check-out
  - View attendance summary per exam/session
  - Filter by student, exam, date range
- **API calls**:
  - `GET/POST /api/v1/attendance` — list/create attendance records
  - `GET /api/v1/monitoring/events` — monitoring events (public)
- **Success behavior**: Attendance recorded/listed with correct data
- **Error behavior**: 404/422 as appropriate
- **Role restrictions**: Role-dependent

## Security Events

- **Route**: `/security-events`
- **Purpose**: View security events and alerts
- **Who can access**: Role-dependent
- **Buttons/actions**:
  - View security events list
  - Filter by severity, category, event type, exam_id, hall_id
  - Acknowledge/resolve alerts
- **API calls**:
  - `GET /api/v1/security-events` — list with filters
  - `GET /api/v1/monitoring/alerts` — monitoring alerts (public)
- **Success behavior**: Events listed with correct data and filters
- **Error behavior**: 404/422 as appropriate
- **Role restrictions**: Role-dependent

## Analytics

- **Route**: `/monitoring` or dedicated analytics section
- **Purpose**: View analytical data about examinations
- **Who can access**: Role-dependent
- **Buttons/actions**:
  - View analytical summaries
  - Filter by date range, exam, hall, event type
- **API calls**:
  - `GET /api/v1/monitoring/status` — monitoring system status (public)
  - `GET /api/v1/monitoring/events` — events with filters (public)
  - `GET /api/v1/monitoring/alerts` — alerts with filters (public)
- **Success behavior**: Data displayed with correct filters
- **Error behavior**: 404/422 as appropriate
- **Role restrictions**: Role-dependent

## Audit

- **Route**: `/audit` or within examination workflow
- **Purpose**: View audit trail and override records
- **Who can access**: Role-dependent (typically ADMIN/OPERATOR)
- **Buttons/actions**:
  - View audit timeline
  - Parse override JSON entries
  - View verification event history
  - Filter by attempt, timestamp, operator
- **API calls**: (depends on implementation; may use security-events or dedicated audit endpoints)
- **Success behavior**: Audit trail displayed with correct data
- **Error behavior**: 404/422 as appropriate
- **Role restrictions**: Typically ADMIN/OPERATOR; REVIEWER may have limited read access

## Import Workflows

- **Route**: `/import` or within admin section
- **Purpose**: Bulk import students, subjects, exams, registrations, seat assignments
- **Who can access**: Role-dependent (typically ADMIN; public for import status config)
- **Buttons/actions**:
  - Upload Excel/CSV file
  - Select import type (students, subjects-exams, registrations, seat-assignments)
  - View import status and limits
  - View import history/audit
- **API calls**:
  - `GET /api/v1/import/status` — available import types and limits (public)
  - `POST /api/v1/import/students` — bulk import students
  - `POST /api/v1/import/subjects-exams` — bulk import subjects and exams
  - `POST /api/v1/import/registrations` — bulk import registrations
  - `POST /api/v1/import/seat-assignments` — bulk import seat assignments
  - `GET /api/v1/import/registrations` — list registrations
  - `GET /api/v1/import/seat-assignments` — list seat assignments
  - `GET /api/v1/import/subjects-exams` — list subjects and exams
- **Success behavior**: Import processed; records created in database
- **Error behavior**: 400 for validation errors; 422 for wrong status, wrong method; 404 for not found
- **Role restrictions**: ADMIN for actual import; import_status.py publicly readable for config

## Critical Flows

### Full Entry Verification Workflow

1. Student arrives at examination gate
2. Camera captures live image (or image uploaded)
3. Operator clicks "Verify Identity"
4. Both images base64-encoded and sent to `POST /{attempt_id}/verify-face`
5. Provider evaluates evidence; results returned as signals (similarity_score, liveness_score, image_quality)
6. Evidence stored; attempt stays in IN_PROGRESS status
7. Operator clicks "Evaluate"
8. `POST /{attempt_id}/evaluate` runs decision engine with configurable thresholds
9. Decision rendered: GRANTED (MATCH), DENIED (NO_MATCH), or ESCALATED (INCONCLUSIVE)
10. UI displays decision and evidence; next steps (seat assignment, hall ticket, attendance)
11. If ESCALATED: operator clicks "Escalate" → provides reason → `POST /{attempt_id}/escalate`
12. Resolution: `POST /{attempt_id}/resolve` → GRANTED or DENIED (with optional reason)

### Admin Provisioning Workflow (First Admin)

1. No ADMIN exists in system
2. First admin sets `INITIAL_ADMIN_EMAILS` env var (comma-separated list of emails)
3. First admin logs in with one of the provisioned emails
4. Backend checks: no ADMIN exists + email in INITIAL_ADMIN_EMAILS → grants ADMIN role
5. Subsequent logins: admin exists → `INITIAL_ADMIN_EMAILS` ignored; all users receive their default role (REVIEWER)
6. Admin can manage users, roles, and configuration thereafter

### End-to-End Workflow (Simplified)

1. Student arrives → identity verified via face recognition
2. Hall ticket validated → seat assigned
3. Entry granted → attendance recorded
4. Examination proceeds → evidence collected at each stage
5. Decision rendered at end → audit trail maintained
6. If issues: human review/override available at every step

## State Management

### AuthState (Frontend)

- `user`: AuthUser | null — ExamGuard user (id, email, full_name, role, is_active, firebase_uid)
- `loading`: boolean — during auth state initialization
- `firebaseIdToken`: string | null — current Firebase ID token
- `requiresOnboarding`: boolean — whether user needs to complete onboarding (new users: true until role assigned)
- `displayName`: string — formatted user name (e.g., "John Doe (john@example.com)") or "User" / "Guest"
- `isAuthenticated`: boolean — whether user is authenticated
- `signInWithGoogle`: () => Promise<void> — initiate Google sign-in
- `signOut`: () => Promise<void> — clear both Firebase and ExamGuard sessions

### ExamAttempt State (Backend)

- `status`: CREATED | IN_PROGRESS | COMPLETED | FAILED | CANCELLED
- `decision`: MATCH | NO_MATCH | INCONCLUSIVE | PENDING
- `checks`: hall_ticket_check, seat_check, identity_check — each: PASSED | FAILED | PENDING | SKIPPED
- `evidence`: accumulated IdentityVerificationEvidence records
- `timestamps`: created_at, started_at, completed_at, escalated_at, resolved_at
- `review_state`: NONE | REVIEW | OVERRILLED
- `override_metadata`: JSON (original_decision → override_decision → reason → timestamp)

## Error Handling

### Frontend

- API errors displayed as safe, human-readable messages
- No credential leakage in error messages
- 401 → redirect to login / re-authenticate
- 403 → insufficient role error; role-specific UI visibility
- Network errors: fallback message ("Unable to reach server. Please try again.")
- Loading states shown during API calls
- Error state: inline error messages; no console.log/debug output visible to user

### Backend

- 404 for not-found attempts, entries, resources
- 422 for validation errors, wrong status, wrong method, invalid decisions
- 401 for unauthenticated/insufficient authentication
- 403 for insufficient role
- No filesystem paths, Python tracebacks, or internal module names exposed
- Error categories preserved for legitimate clients (e.g., "Invalid input", "Provider unavailable")
- Safe error messages at API boundary; no stack traces

## Role-Based Access Control

### Frontend (UX Only)

- Header shows: EXAMGUARD, role-specific navigation, user name/email/role, LOG OUT
- Navigation visibility: ADMIN sees all options; OPERATOR sees operational options; REVIEWER sees review/verify options
- Role-specific administration options hidden/visible based on role
- User name/email/role displayed in header

### Backend (Real Security Boundary)

- `require_role(["ADMIN"])` — only ADMIN can access
- `require_role(["OPERATOR"])` — OPERATOR and ADMIN can access
- `require_role(["REVIEWER"])` — REVIEWER, OPERATOR, ADMIN can access
- `require_any_role(["ADMIN", "OPERATOR"])` — either ADMIN or OPERATOR can access
- `has_permission(role, permission)` — check specific permission
- Users cannot self-promote (cannot change own role)
- Google user auto-promotion blocked (REVIEWER by default)
- Admin provisioning via `INITIAL_ADMIN_EMAILS` only when no ADMIN exists

### Role Hierarchy

- **ADMIN**: Full access to all admin operations and routes
- **OPERATOR**: Examination operations, verification/entry/attendance/monitoring as appropriate
- **REVIEWER**: Review/read/audit capabilities as appropriate; cannot administer

## Firebase Configuration Requirements

### What Must Be Configured Manually (Firebase Console)

- **Project setup**: Create Firebase project in console
- **Authentication**: Enable sign-in method (Google provider)
- **Google provider**: Enable Google sign-in provider
- **Authorized domains**: Add deployment domain(s) (e.g., `localhost`, production domain)
- **Web app configuration**: Register web app; get `apiKey`, `projectId`, `authDomain`, etc.
- **`INITIAL_ADMIN_EMAILS`**: Set in backend `.env` for initial admin provisioning (comma-separated list)
- **First ADMIN login**: Must use one of the provisioned emails; subsequent logins ignored

### What the Code Already Has

- **Public Firebase web config** in `frontend/src/lib/firebase_init.ts` (apiKey, projectId, etc. — safe to expose)
- **Backend Firebase config** in `backend/app/core/config.py` (`FIREBASE_PROJECT_ID`, etc. — env-driven)
- **Firebase verification service** in `backend/app/services/firebase_verification.py` (HTTP-based ID token verification, no Admin SDK)
- **Google provider config** in `frontend/src/lib/firebase.ts` (`prompt: "select_account"` for account selection)
- **No service account keys** in code (HTTP-based verification used)

### What Is NOT in the Code (Requires Manual Config)

- Firebase project ID (set in `.env` via `FIREBASE_PROJECT_ID`)
- Google OAuth consent screen setup
- Authorized domains list
- Web app registration in Firebase Console
- `INITIAL_ADMIN_EMAILS` in `.env` (optional, for first-time admin setup)

## Frontend TypeScript Issues (Known)

- **page.tsx(168,60)**: `Object literal may only specify known properties, and '"--progress"' does not exist in type 'Properties<string | number, string & {}>'`
- This is a pre-existing TypeScript error related to CSS custom property `--progress` in the inline style object
- Fix: Use proper TypeScript-safe approach for CSS custom properties (currently unfixed due to constraints)
- Impact: Production build (`next build`) fails typecheck until resolved
- Note: All other AuthContext TypeScript errors were fixed during earlier verification

## E2E Test Coverage

### Existing Integration Tests (76 tests, `test_phase_10_5_integration.py`)

1. Full workflow E2E (2 tests): Complete flow from creation through all checks to GRANTED, with and without optional fields
2. Hall Ticket Integration (7 tests): Verified ticket passes, auto-link from registration, no ticket fails, unverified ticket fails, matched-not-verified fails, hall ticket not mutated by entry verification, repeated check consistent
3. Seat/Hall Integration (5 tests): Correct hall passes, wrong hall fails, no seat fails, seat not mutated, cancelled seat fails
4. Camera/Entry Point Integration (7 tests): Camera mapped to entry point, not mapped rejected, inactive camera rejected, disabled camera → identity skipped, offline camera → identity skipped, unknown camera → identity pending, online camera without attempt → identity pending
5. Identity Verification Integration (4 tests): Match attempt passes, no match fails, pending attempt → pending, no biometric data in entry verification

### Test Coverage Details

- **Full Pipeline E2E**: Service layer and HTTP API flows; MATCH, NO_MATCH, INCONCLUSIVE, and liveness failure paths
- **Provider Abstraction**: DeterministicProvider through API; custom stub provider through service; provider failure/exception handling; authorization field isolation
- **Decision Engine Integration**: High/low/near-threshold similarity; missing evidence; liveness fail override; poor quality; detailed metadata
- **Lifecycle State Machine**: All valid transitions; cancel/fail from CREATED; cannot start/complete/fail/cancel twice; cannot verify after terminal states; cannot review/override from non-terminal states; completed_at verification
- **Evidence Consistency**: Evidence belongs to correct attempt; accumulates across multiple calls; metadata sanitized; manual recording; cannot record on completed
- **Repeated Verification**: Three calls accumulate; lifecycle intact; decision correct after accumulation
- **Concurrency**: Concurrent verify calls; concurrent review requests; concurrent overrides; verify-then-cancel
- **Human Review**: Review flow; evidence preservation; review on failed attempts; review without notes
- **Human Override**: All 6 transition directions; audit entry creation; evidence preservation; reason requirement; terminal state requirement; multiple override chaining; API integration
- **Audit Trail**: Override JSON structure; review JSON structure; metadata safety; non-override parsing; full flow audit
- **Failure Matrix**: Provider unavailable/exception; empty images; wrong method; attempt not found; invalid decision; empty failure reason; provider failure ≠ identity mismatch; insufficient evidence ≠ MATCH
- **Security Invariants**: Client cannot set threshold; cannot force decision via evidence; provider cannot authorize; VerifyFaceRequest schema validation; decision engine cannot be bypassed; liveness fail always NO_MATCH; no composite score leakage
- **Rate Limiting**: Attempt limits within/at/over; global limits within/at; zero means unlimited; independent attempts; reset
- **API Contract**: List, context, verify-face, complete, override response shapes; 404, 422; filter parameters
- **Configuration**: Default values; retention zero; rate limits; invalid threshold/factor rejection
- **Error Sanitization**: No filesystem paths; no tracebacks; safe validation errors
- **Privacy**: No raw images in API responses; no images in context; config retention zero
- **Provider Failure ≠ False Decision**: Unavailable not NO_MATCH; exception not mismatch; empty evidence not MATCH

### Test Repeatability

- Two full suite runs, both 1103 passed (0 failures, 0 errors)
- Stable and repeatable results

## Documentation Cross-References

- PRD.md — Product goals, users, capabilities, limitations
- TRD.md — Technical architecture, API, configuration, testing strategy
- APP_FLOW.md — This file; page routes, navigation, state management
- UI_UX_DESIGN_BRIEF.md — Design system, visual language, component library
- BACKEND_SCHEMA.md — Database tables, models, relationships, ASCII diagram
- IMPLEMENTATION_PLAN.md — Completed, in-progress, blocked, future work
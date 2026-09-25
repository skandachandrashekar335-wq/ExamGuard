# ExamGuard Product Requirements Document

## Product Overview

ExamGuard is an AI-powered Examination Entry Verification, Anti-Proxy, Security, and Attendance Management Platform. The system connects identity, hall-ticket, seating, evidence and attendance into one auditable workflow, ensuring examination integrity from entry to decision.

## Problem Statement

Examination entries lack a unified, evidence-driven verification workflow. AI perception produces evidence, but business logic must evaluate evidence — AI must never silently become the business authority. Without proper verification, examination entries are vulnerable to identity fraud, proxy attendance, and security violations.

## Goals

- Provide a complete end-to-end examination entry verification workflow
- Ensure AI produces evidence only; business logic evaluates evidence and makes decisions
- Maintain full audit trail for all decisions and operations
- Support role-based access control (ADMIN/OPERATOR/REVIEWER)
- Integrate Firebase/Google authentication with proper RBAC
- Enable attendance tracking and security event monitoring
- Support import workflows (students, subjects, exams, registrations, seat assignments)

## Non-Goals

- AI as business authority (evidence ≠ decision)
- Hard-coded production data or thresholds
- Database reset or seed scripts
- Paid AI services or cloud AI APIs
- Biometric API integration beyond face verification
- Terminal aesthetic or neon sci-fi styling

## Target Users

- **ADMIN**: Full access to all administrative operations and user/role management
- **OPERATOR**: Examination operations, verification/entry/attendance/monitoring operations
- **REVIEWER**: Review and verify capabilities, but not administer
- **Student/Examinee**: Entry verification flow (frontend-facing)

## ADMIN

- Administrative/configuration operations
- User/role management where implemented
- Full access to all admin operations and routes
- Initial admin provisioning via `INITIAL_ADMIN_EMAILS` env var (only when no ADMIN exists)

## OPERATOR

- Examination operations
- Verification/entry/attendance/monitoring operations as appropriate
- Can manage exams, students, halls, registrations, seats
- Cannot administer or promote users

## REVIEWER

- Review/read/audit capabilities as appropriate
- Can verify entries, view attendance, security events
- Cannot administer or promote users
- New Google users receive REVIEWER role by default

## Student/Examinee

- Entry verification flow (frontend-facing)
- Hall-ticket validation
- Seat assignment display

## Major Product Capabilities

### Examination Management

- Create, read, update examinations and exam sessions
- Hall ticket generation and validation
- Seat assignment and allocation
- Entry verification workflow (7-stage pipeline)
- Evidence-based decision engine with configurable thresholds

### Student Management

- Student CRUD operations
- Student activation/deactivation
- Search and pagination
- USN and profile management

### Hall Tickets

- Hall ticket creation and lifecycle management
- Linking to exam registrations and students
- Status transitions (CREATED → EXTRACTED → MATCHED → VERIFIED/REJECTED/CANCELLED)
- Detailed context retrieval (student, exam, registration, document info)

### Entry Verification

- 7-stage verification pipeline: CAMERA → IDENTITY → LIVENESS → HALL TICKET → SEAT → EVIDENCE → DECISION
- Face verification provider architecture (provider-agnostic)
- Identity verification with similarity scoring
- Liveness/anti-spoofing detection
- Decision engine with configurable thresholds and near-threshold zone
- Human review and override at every step

### Identity Verification

- Face verification provider integration (deterministic/UniFace)
- Base64-encoded image submission
- Evidence signal storage (similarity_score, liveness_score, image_quality)
- No raw image persistence (retention_days = 0 by default)
- Typed failure categories and audit trail

### Anti-Proxy Detection

- Security signal detection (duplicate entry, unusual entry point, unusual time, seat mismatch, multiple registrations, document anomaly, behavioral anomaly, identity mismatch)
- Risk scoring engine with configurable thresholds
- Rate limiting per-attempt and global per-minute
- Idempotency: repeated verification attempts accumulate evidence by design

### Attendance

- Attendance recording per examination session
- Attendance events (check-in, check-out, status changes)
- Summary reports per exam/session
- Integration with entry verification workflow

### Monitoring

- Real-time monitoring WebSocket endpoint (/ws/monitoring)
- In-memory event and alert buffers (Phase 19, no persistence)
- Connection status and publisher status
- Filterable event queries (by category, type, severity, exam_id, hall_id)

### Security Events

- Security event logging and classification
- Severity levels (INFO, WARNING, ERROR, CRITICAL)
- Alert generation and threshold-based triggering
- Investigation workflow with audit trail

### Import Workflows

- Bulk student import (Excel/CSV support)
- Bulk subject/exam import
- Bulk registration management
- Bulk seat assignment workflows
- Import validation framework
- Import audit logging with bounded error summaries

### Authentication

- Firebase/Google authentication with popup sign-in
- Server-side Firebase ID token verification
- ExamGuard JWT session (30 min expiry, HS256)
- Role hierarchy: ADMIN > OPERATOR > REVIEWER
- New Google users receive REVIEWER role by default
- No auto-ADMIN grant; admin provisioning via `INITIAL_ADMIN_EMAILS`
- Frontend route protection is UX only; backend RBAC is the real security boundary

### RBAC

- Role hierarchy: ADMIN > OPERATOR > REVIEWER
- Permission-based access control
- Frontend route hiding is UX only; backend authorization enforces security
- Users cannot self-promote
- REVIEWER cannot become ADMIN through crafted requests
- Role values are validated

### Firebase/Google Authentication

- Firebase ID token verification via REST API (no Admin SDK in code)
- Public Firebase web config only (apiKey, projectId, etc. safe to expose)
- No service account private keys in frontend or backend
- `INITIAL_ADMIN_EMAILS` env var for initial provisioning only
- First ADMIN login must use provisioned email; subsequent logins ignored

### Analytics

- Analytical capabilities for examination data
- Aggregation and reporting (dependent on attendance and security event data)
- Integration with monitoring and security events

### Storage

- Local document storage abstraction
- Configurable upload limits and retention policies
- Cloud provider switching support (Cloudinary later)

### Privacy Principles

- No raw biometric images stored (retention_days = 0 by default)
- No embeddings persisted in database
- No biometric data in audit metadata
- Transient in-memory processing only
- Provider errors sanitized at API boundary
- No secrets hard-coded in source

### Evidence vs Decision Architecture

- AI/perception produces evidence packages
- Business logic evaluates evidence against configurable thresholds
- AI must never silently become the business authority
- Human review remains available at every step
- Full audit trail maintained for all decisions and overrides

### Operational Requirements

- All configuration environment-driven via `.env` (no hard-coded production data)
- Database changes require proper Alembic migrations
- No destructive database operations
- Test suite: 2466+ backend tests passing
- Frontend: Next.js 16.x, React 19.x, TypeScript, Tailwind CSS v4
- Production readiness requires Firebase Console configuration

### Known Limitations

- Frontend TypeScript error in `page.tsx` (`--progress` CSS variable, pre-existing)
- Full RBAC not yet enforced on all API routes
- Production Firebase Console configuration required (Google provider, OAuth consent screen)
- `INITIAL_ADMIN_EMAILS` must be set for initial admin provisioning
- E2E test coverage limited (integration tests exist for core workflow)
- Some Phase 16-22 features still in planning

### Future Work

- Phase 16-22 completion (monitoring, analytics, ERP integration)
- Full E2E test suite expansion
- Production Firebase Console setup
- RBAC wire-up on all API routes
- Performance optimization and scaling
- ERP integration implementation

## Evidence vs Decision Architecture

```
AI Perception                    Business Logic
     ↓                              ↓
Biometric data → Evidence package → Evaluate evidence
     ↓                              ↓
   (signals)                       (thresholds, liveness, quality)
     ↓                              ↓
Decision engine decides          Human review available
```

AI systems provide evidence/perception. Business logic makes authorization and operational decisions. AI must never silently become the business authority.

## Operational Requirements

- All configuration environment-driven via `.env` (no hard-coded production data)
- Database changes require proper Alembic migrations
- No destructive database operations
- Test suite: 2466+ backend tests passing (verified)
- Frontend: Next.js 16.x, React 19.x, TypeScript, Tailwind CSS v4
- Production readiness requires Firebase Console configuration

## Privacy Principles

- No raw biometric images stored (retention_days = 0 by default)
- No embeddings persisted in database
- No biometric data in audit metadata
- Transient in-memory processing only
- Provider errors sanitized at API boundary
- No secrets hard-coded in source code or frontend bundles

## Evidence vs Decision

AI/perception produces evidence packages. Business logic evaluates evidence against configurable thresholds. AI must never silently become the business authority. Human review remains available at every step. Full audit trail maintained for all decisions and overrides.

## Future Work

- Phase 16-22 completion
- Full E2E test suite expansion
- Production Firebase Console setup
- RBAC wire-up on all API routes
- Performance optimization and scaling
- ERP integration implementation
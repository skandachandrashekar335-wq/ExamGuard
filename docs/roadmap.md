# ExamGuard Master Roadmap

> This is the reconstructed master roadmap for the ExamGuard project.
> It serves as the project's authoritative planning document going forward.
> This document was created after Phase 4 completion to formalize the 23-phase architecture.

---

## Project Overview

**ExamGuard** — AI-powered Examination Entry Verification, Anti-Proxy, Security, and Attendance Management Platform.

Built with FastAPI + SQLAlchemy + PostgreSQL (backend), Next.js + TypeScript + Tailwind (frontend).

---

## Phase 0 — Architecture & Project Foundation

**Status: COMPLETE**

- Repository and monorepo foundation
- FastAPI backend
- Next.js frontend
- PostgreSQL
- SQLAlchemy
- Alembic
- Configuration and environment management
- Architecture documentation
- Git workflow

---

## Phase 1 — Database & Student Foundation

**Status: COMPLETE**

- PostgreSQL integration
- SQLAlchemy models/base
- Database dependency
- Student model
- Initial migrations
- Student persistence foundation

---

## Phase 2 — Student Management

**Status: COMPLETE**

- Student CRUD
- Pydantic schemas
- Service layer
- Search
- Pagination
- Student activation/deactivation
- Student management frontend

---

## Phase 3 — Document Ingestion & OCR Intelligence

**Status: COMPLETE**

- Document upload
- Storage abstraction
- Local storage
- Document validation
- OCR pipeline
- PDF/image preprocessing
- Tesseract integration
- Rule-based extraction
- OCR confidence signals
- Extracted fields
- Processing workflow
- Hall-ticket document support

---

## Phase 4 — Exam & Hall-Ticket Intelligence

**Status: COMPLETE**

- Subject management
- Exam management
- Exam hall management
- Exam registration
- Seat assignment
- Hall-ticket domain matching
- Extraction review/correction
- Verification decision and audit trail
- Exam verification dashboard
- Batch verification
- Admin management pages

---

## Phase 5 — Examination Operations & Data Import

**Status: COMPLETE**

Focus:
- Bulk student import (Step 1)
- Bulk subject/exam import (Step 2)
- Bulk registration management (Step 3)
- Bulk seat assignment workflows (Step 4)
- Import validation framework (Step 5)
- Excel/CSV admin import center (Step 6)
- Import audit logging (Step 7)

**Dependencies:** Phases 0–4 (student, subject, exam, registration, seat assignment models and APIs must exist).

**New models/migrations:** `ImportAuditLog` model (migration 013) with enums for import type, operation, and status. Tracks every bulk import operation with row counts, timestamps, and bounded error summaries.

**Frontend work completed:** Import hub page, 4 import pages (students, subjects-exams, registrations, seat-assignments) with Excel/CSV support, import history/audit page.

**Testing requirements:** 525 backend tests passing (38 audit-specific tests covering model, service, API, integration).

---

## Phase 6 — Hall-Ticket Lifecycle Management

**Status: COMPLETE**

### 6.1 Hall-Ticket Domain Model & Database Foundation
**Status: COMPLETE**
- `HallTicket` model with lifecycle statuses (CREATED → EXTRACTED → MATCHED → VERIFIED/REJECTED/CANCELLED)
- Links exam_registration to document, extraction, match, and verification outcomes
- Unique constraint on exam_registration_id prevents duplicate active tickets
- Alembic migration 014
- Service layer with status transition validation
- REST API: create, get by ID, get by registration, list, update
- 46 comprehensive tests (model, service, API, lifecycle, regression)

### 6.2 Hall-Ticket Upload & Ingestion
**Status: COMPLETE**
- `link_document()` service: associates a HALL_TICKET document with an existing HallTicket
- `on_extraction_complete()` hook: auto-transitions CREATED → EXTRACTED when OCR finishes
- `on_match_complete()` hook: auto-transitions EXTRACTED → MATCHED when matching finishes
- Both hooks integrated into `processing.py` and `hall_ticket_matching.py` pipelines
- API: `POST /hall-tickets/{id}/link-document`

### 6.3 Hall-Ticket ↔ Student/Exam Linking
**Status: COMPLETE**
- `get_with_context()`: returns HallTicket with linked Student, Exam, ExamRegistration, Document
- API: `GET /hall-tickets/{id}/detailed` — full context response
- Schema: `HallTicketDetailedResponse`, `HallTicketStudentInfo`, `HallTicketExamInfo`, `HallTicketDocumentInfo`

### 6.4 Hall-Ticket Lifecycle & Status Management
**Status: COMPLETE**
- `_transition()` helper: validates and applies status transitions with timestamp update
- `STATUS_TRANSITIONS` dict enforced on all status changes
- Auto-transitions via hooks (extraction/matching) + manual via PATCH

### 6.5 Hall-Ticket Review/Approval Workflow
**Status: COMPLETE**
- `approve()`: moves MATCHED → VERIFIED, optionally links verification_outcome_id
- `reject()`: moves MATCHED → REJECTED, stores rejection_reason, optionally links verification_outcome_id
- API: `POST /hall-tickets/{id}/approve`, `POST /hall-tickets/{id}/reject`

### 6.6 Hall-Ticket Admin UI
**Status: COMPLETE**
- `/hall-tickets` — list page with status filter, USN search, pagination, status-colored badges
- `/hall-tickets/[id]` — detail page with lifecycle progress, student/exam/document info, approve/reject actions
- 17 frontend pages total, all building successfully

### 6.7 Hall-Ticket Search & Operations
**Status: COMPLETE**
- `search_hall_tickets()`: filter by USN (partial match), exam_id, status, subject_code
- API: `GET /hall-tickets/search?usn=...&exam_id=...&status=...&subject_code=...`

### 6.8 Integration Tests + Phase 6 hardening
**Status: COMPLETE**
- 73 hall-ticket-specific tests: model, create, retrieve, update, list, link-document, approve, reject, context, search, API endpoints
- Fixed FK cleanup ordering in `test_verification.py`, `test_batch_verification.py`, `test_dashboard.py` (HallTicket before ExamRegistration, ExtractedField before ExtractionResult)
- 598 total backend tests passing
- Frontend: 17 pages building successfully

---

## Phase 7 — Identity Verification Foundation

**Status: COMPLETE**

### 7.1 Identity Verification Domain Model & Database Foundation
**Status: COMPLETE**
- `IdentityVerificationAttempt` model with lifecycle: CREATED → IN_PROGRESS → COMPLETED/FAILED/CANCELLED
- `IdentityVerificationEvidence` model for signal-level evidence storage
- `IdentityVerificationMethod` enum: FACE, MANUAL, DOCUMENT, OTHER
- `IdentityVerificationDecision` enum: PENDING, MATCH, NO_MATCH, INCONCLUSIVE
- Alembic migration 015
- `STATUS_TRANSITIONS` dict enforced on all status changes

### 7.2 Identity Verification Service Layer
**Status: COMPLETE**
- `create_attempt()`: validates student, registration, hall_ticket ownership
- `get_attempt()`, `list_attempts()`: retrieval with filters
- `start_attempt()`: CREATED → IN_PROGRESS
- `complete_attempt()`: → COMPLETED with decision
- `fail_attempt()`: → FAILED with reason
- `cancel_attempt()`: → CANCELLED
- `record_evidence()`: stores evidence signals
- `get_attempt_with_context()`: returns attempt + student + exam + hall_ticket

### 7.3 Identity Verification Decision Engine
**Status: COMPLETE**
- Provider-independent decision engine (`identity_verification_decision.py`)
- Configurable similarity threshold via `IDENTITY_VERIFICATION_MATCH_THRESHOLD` (default 0.85)
- Decision logic: similarity + liveness + quality checks
- No biometric data stored; no raw face images

### 7.4 Identity Verification API
**Status: COMPLETE**
- REST API at `/api/v1/identity-verifications`
- Endpoints: create, get, get-context, list, start, fail, cancel, evaluate
- Full validation on all inputs
- Read-only list with pagination

### 7.5 Identity Verification Admin UI
**Status: COMPLETE**
- `/identity-verifications` list page with status/decision filters
- `/identity-verifications/[id]` detail page with lifecycle progress, evidence, actions
- 19 frontend pages total, all building successfully

### 7.6 Identity Verification Tests
**Status: COMPLETE**
- 62 comprehensive tests: model, service create, lifecycle, evidence, context, list, decision engine, API
- 660 total backend tests passing

**Dependencies:** Phases 0–4. This is an architectural phase establishing abstractions before Phase 8 implements face verification.

**New models/migrations:** `IdentityVerificationAttempt`, `IdentityVerificationEvidence` models (migration 015).

**Frontend work completed:** Identity verification list and detail pages.

---

## Phase 8 — Face Verification / UniFace Integration

**Status: IN PROGRESS (Phase 8.1 complete)**

### 8.1 Face Verification Architecture & Provider Abstraction
**Status: COMPLETE**

Core architectural principle:
> AI/perception = evidence. Business logic = authority.

Face verification providers produce evidence signals. The decision engine
evaluates that evidence. Providers NEVER directly authorize or deny exam entry.

**Provider contract:**
- `FaceVerificationProvider` Protocol with `verify()`, `health_check()`, `get_capabilities()`
- `FaceVerificationRequest`: reference_image + probe_image bytes + context
- `FaceVerificationResult`: identity_match_score, liveness_score, liveness_passed, image_quality_score, evidence_metadata
- `FaceVerificationError`: typed error categories (PROVIDER_UNAVAILABLE, TIMEOUT, INVALID_INPUT, etc.)
- `ProviderCapabilities` and `ProviderStatus`: describe provider features and health
- All dataclasses are frozen (immutable)

**Provider abstraction location:** `app/services/face_verification/`

**Files created:**
- `app/services/face_verification/__init__.py` — public API
- `app/services/face_verification/types.py` — all data types
- `app/services/face_verification/protocol.py` — FaceVerificationProvider Protocol
- `app/services/face_verification/factory.py` — provider factory from config
- `app/services/face_verification/providers/__init__.py`
- `app/services/face_verification/providers/deterministic.py` — test provider

**Configuration added to `app/core/config.py`:**
- `FACE_VERIFICATION_PROVIDER: str = "deterministic"` — provider selection
- `FACE_VERIFICATION_PROVIDER_URL: str | None = None` — future provider URL
- `FACE_VERIFICATION_PROVIDER_API_KEY: str | None = None` — future API key
- `FACE_VERIFICATION_MAX_IMAGE_SIZE_MB: int = 5` — image size limit
- `FACE_VERIFICATION_IMAGE_RETENTION_DAYS: int = 0` — 0 = never store images

**Privacy decisions:**
- Raw images are NEVER stored by ExamGuard (retention_days = 0 by default)
- Biometric templates are managed by the provider, not ExamGuard
- Provider credentials are never exposed in API responses
- Evidence metadata must not contain raw images or biometric templates
- Provider errors are NOT logged with image content

**Security decisions:**
- All dataclasses are frozen to prevent accidental mutation
- Provider errors are typed (FaceVerificationErrorType) — not generic strings
- Provider availability is checked before verification attempts
- Image size limits enforced via configuration

**Tests added:** 28 tests
- Protocol conformance (4 tests)
- DeterministicProvider behavior (8 tests)
- Provider failure handling (3 tests)
- Sensitive data leakage prevention (3 tests)
- Evidence ≠ Decision separation (3 tests)
- Factory behavior (2 tests)
- Immutability verification (5 tests)

**Test count:** 688 passing (660 existing + 28 new)

**Frontend changes:**
- `privacy/page.tsx`: Fixed monochrome violations (replaced accent-cyan/emerald/amber/pink with monochrome tokens)
- `terms/page.tsx`: Fixed monochrome violations (same treatment)
- No camera UI, no fake face-match percentages, no fake liveness PASS

### 8.2 Face Verification Provider Integration (NEXT)
- Wire provider into identity verification service
- Add evidence recording from provider results
- Add provider error handling in service layer
- Add API endpoint for face verification trigger

### 8.3 UniFace Integration (FUTURE)
- Implement UniFace provider
- Real face recognition
- Real liveness detection

### 8.4 Face Verification UI (FUTURE)
- Camera capture interface
- Real-time verification status
- Review workflow for failures

---

## Phase 9 — Camera & Entry Point Management

**Status: PLANNED**

Focus:
- Camera/device models
- Entry gate management
- Camera configuration
- Device health/status
- Camera-to-entry-point mapping
- Secure device communication foundation

**Dependencies:** Phases 0–4 (exam hall models must exist for mapping).

**New models/migrations likely required:** `Camera`, `EntryPoint`, `CameraEntryPointMapping` models. Device health/status tracking.

**Frontend work expected:** Camera management pages, entry point configuration, device status dashboard.

**Testing requirements:** Unit tests for device models, mapping logic. API tests for camera CRUD endpoints.

---

## Phase 10 — Real-Time Examination Entry Verification

**Status: PLANNED**

Focus:
- Live entry workflow
- Hall-ticket verification at entry
- Identity verification at entry
- Seat/hall validation
- Real-time verification status
- Entry authorization workflow
- Human review escalation

**Dependencies:** Phases 7, 8, 9 (identity verification, face verification, and camera infrastructure must exist).

**New models/migrations likely required:** `EntryVerification` or `EntryEvent` model capturing live verification attempts.

**Frontend work expected:** Live entry monitoring dashboard, verification status displays, human review escalation UI.

**Testing requirements:** Unit tests for entry workflow logic, authorization decisions. API tests for entry verification endpoints.

---

## Phase 11 — Anti-Proxy Detection

**Status: PLANNED**

Focus:
- Proxy-risk signals
- Identity mismatch detection
- Duplicate identity/entry detection
- Suspicious verification patterns
- Risk scoring based on evidence
- Human review workflow
- Auditability

**Dependencies:** Phase 10 (real-time entry verification must exist to generate proxy-risk signals).

**New models/migrations likely required:** `ProxyRiskAssessment` or `SecuritySignal` model. Risk scoring evidence storage.

**Frontend work expected:** Risk assessment dashboard, suspicious activity review pages.

**Testing requirements:** Unit tests for risk scoring logic, duplicate detection, mismatch detection. API tests for risk assessment endpoints.

---

## Phase 12 — Attendance Management

**Status: PLANNED**

Focus:
- Attendance models
- Attendance state management
- Entry-based attendance
- Manual attendance correction
- Attendance audit trail
- Attendance reports

**Dependencies:** Phase 10 (entry verification events are the source of attendance records).

**New models/migrations likely required:** `Attendance` model with state machine (absent → present → corrected). `AttendanceCorrection` audit model. `backend/app/services/attendance/` implementation.

**Frontend work expected:** Attendance dashboard, manual correction UI, attendance reports.

**Testing requirements:** Unit tests for attendance state transitions, correction logic. API tests for attendance endpoints.

---

## Phase 13 — Real-Time Monitoring

**Status: PLANNED**

Focus:
- WebSocket architecture
- Live verification events
- Live entry monitoring
- Dashboard updates
- Real-time operational status

**Dependencies:** Phases 10, 12 (entry events and attendance data must exist to stream).

**New models/migrations likely required:** WebSocket connection management (likely in-memory, not DB). `backend/app/api/v1/ws/` implementation.

**Frontend work expected:** Real-time dashboard components, live status indicators, WebSocket client integration.

**Testing requirements:** Unit tests for WebSocket message handling, connection management. Integration tests for live event streaming.

---

## Phase 14 — Security Event Management

**Status: PLANNED**

Focus:
- Security event models
- Suspicious activity logging
- Security alerts
- Severity levels
- Investigation workflow
- Immutable audit history

**Dependencies:** Phases 10, 11 (entry verification and anti-proxy systems generate security events).

**New models/migrations likely required:** `SecurityEvent` model with severity enum, immutable append-only design. `SecurityAlert` model.

**Frontend work expected:** Security event dashboard, alert management, investigation workflow pages.

**Testing requirements:** Unit tests for event classification, severity assignment. API tests for security event endpoints.

---

## Phase 15 — Examination Session Management

**Status: PLANNED**

Focus:
- Examination session lifecycle
- Session start/end
- Gate opening/closing workflow
- Active hall monitoring
- Session-level operational controls
- Session audit trail

**Dependencies:** Phases 9, 10 (cameras and entry verification must exist for session context).

**New models/migrations likely required:** `ExaminationSession` model with lifecycle states. Gate status tracking.

**Frontend work expected:** Session management dashboard, gate control UI, active hall monitoring.

**Testing requirements:** Unit tests for session lifecycle, gate workflow. API tests for session endpoints.

---

## Phase 16 — Attendance & Examination Analytics

**Status: PLANNED**

Focus:
- Attendance analytics
- Verification analytics
- Proxy-risk analytics
- Hall utilization
- Examination statistics
- Admin reporting dashboards

**Dependencies:** Phases 12, 14 (attendance and security event data must exist for analytics).

**New models/migrations likely required:** Possibly materialized views or analytics aggregation tables. No core domain models expected.

**Frontend work expected:** Analytics dashboard pages, charts, export functionality.

**Testing requirements:** Unit tests for aggregation logic. API tests for analytics endpoints.

---

## Phase 17 — ERP Integration

**Status: PLANNED**

Focus:
- ERP adapter abstraction
- Student synchronization
- Subject synchronization
- Examination synchronization
- Registration synchronization
- Attendance export/synchronization
- Retry/error handling

**Dependencies:** Phases 0–4 (all core domain models must exist for sync targets).

**New models/migrations likely required:** `ErpSyncLog` or `ErpSyncJob` model for tracking sync operations. `backend/app/services/erp/adapter.py` implementation.

**Frontend work expected:** ERP sync status dashboard, sync configuration, error review pages.

**Testing requirements:** Unit tests for adapter abstraction, sync logic, error handling. Integration tests with mock ERP responses.

---

## Phase 18 — Cloud Storage & Deployment Storage

**Status: PLANNED**

Focus:
- Cloudinary/storage abstraction
- Production document storage
- Secure file access
- Storage lifecycle
- Local/cloud backend switching
- Migration strategy

**Dependencies:** Phase 3 (storage abstraction ABC must exist).

**New models/migrations likely required:** `backend/app/storage/cloudinary.py` implementation. No new DB models expected.

**Frontend work expected:** None expected — storage is backend infrastructure.

**Testing requirements:** Unit tests for cloud storage backend, switching logic. Integration tests with mock cloud storage.

---

## Phase 19 — Advanced Administration & Access Control

**Status: PLANNED**

Focus:
- Authentication
- Authorization
- Admin roles
- Operator roles
- Reviewer roles
- Permission management
- Protected APIs and frontend routes

**Dependencies:** All prior phases (auth must wrap existing endpoints and pages).

**New models/migrations likely required:** `User`, `Role`, `Permission` models. Session/token management. JWT or session-based auth.

**Frontend work expected:** Login page, role-based navigation, protected route wrappers, user management pages.

**Testing requirements:** Unit tests for auth logic, permission checks. API tests for protected endpoints. Frontend auth flow verification.

---

## Phase 20 — Security Hardening & Compliance

**Status: PLANNED**

Focus:
- API security
- Input validation
- Rate limiting
- Secret management
- Secure file handling
- Audit integrity
- Privacy controls
- Data retention policies
- Security testing

**Dependencies:** Phase 19 (auth must exist before security hardening).

**New models/migrations likely required:** Data retention policy models, rate limit tracking (possibly Redis-backed, not DB).

**Frontend work expected:** Privacy consent flows, data retention configuration UI.

**Testing requirements:** Security-focused unit tests, penetration testing preparation, input validation tests.

---

## Phase 21 — Reliability, Performance & Scale

**Status: PLANNED**

Focus:
- Background processing
- Queue architecture
- Concurrent verification
- Database optimization
- Caching where appropriate
- Large examination batch handling
- Performance testing
- Failure recovery

**Dependencies:** Phases 10–15 (real-time systems must exist to optimize).

**New models/migrations likely required:** Queue/job tracking models. Possibly Redis or Celery integration.

**Frontend work expected:** Performance monitoring dashboard, queue status views.

**Testing requirements:** Load tests, concurrent access tests, failure recovery tests.

---

## Phase 22 — Production Deployment & Observability

**Status: PLANNED**

Focus:
- Production deployment
- Environment configuration
- Logging
- Metrics
- Health checks
- Monitoring
- Error tracking
- Backup/recovery
- CI/CD

**Dependencies:** All prior phases (production deployment wraps the complete system).

**New models/migrations likely required:** None expected — observability is infrastructure, not domain.

**Frontend work expected:** Health check endpoints, monitoring dashboards.

**Testing requirements:** Deployment tests, health check verification, backup/recovery drills.

---

## Phase 23 — Final ExamGuard Platform Integration

**Status: PLANNED**

Focus:
- End-to-end integration
- Complete examination workflow
- Entry verification
- Anti-proxy
- Attendance
- Security monitoring
- ERP integration
- Production readiness
- End-to-end testing
- Final documentation

**Dependencies:** All prior phases (this is the integration and finalization phase).

**New models/migrations likely required:** None expected — integration phase.

**Frontend work expected:** End-to-end workflow testing, final UI polish.

**Testing requirements:** Full end-to-end test suite, production readiness verification, final documentation review.

---

## Roadmap Rules

1. Phases 0–7 are COMPLETE.
2. Phase 8 is IN PROGRESS (8.1 complete).
3. Phases 9–23 are PLANNED.
4. Do not mark future phases complete.
5. Do not implement future phases.
6. Each future phase should eventually be broken into smaller implementation steps before coding begins.
7. Future implementation must proceed sequentially unless the architecture explicitly justifies another order.
8. AI systems provide evidence/perception; business logic makes authorization and operational decisions.
9. Never hard-code production data or thresholds.
10. Database changes require Alembic migrations.
11. Preserve auditability and security throughout the project.
12. Do not introduce paid/cloud AI services unless explicitly planned and approved.
13. Face/biometric functionality must have privacy, security, fallback, and human-review considerations.
14. Never destructively reset production-style databases.
15. Never weaken or delete tests to make a feature pass.

---

## Current Project State

- **Current phase:** Phase 8 IN PROGRESS (8.1 complete)
- **Current completed step:** Phase 8.1 — Face Verification Architecture & Provider Abstraction
- **Current tests:** 688 passing (660 existing + 28 new)
- **Frontend pages:** 20 (all building successfully)
- **Design system:** Minimalist monochrome (Playfair Display / Source Serif 4 / JetBrains Mono), zero border-radius, no neon colors
- **Next step:** Phase 8.2 — Wire provider into identity verification service
- **Provider architecture:** `app/services/face_verification/` with Protocol, DeterministicProvider, factory

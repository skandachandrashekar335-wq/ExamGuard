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

**Status: PLANNED**

Focus:
- Bulk student import
- Bulk subject/exam import
- Bulk registration management
- Bulk seat assignment workflows
- Validation and duplicate detection
- Import error reporting
- Admin operational workflows

**Dependencies:** Phases 0–4 (student, subject, exam, registration, seat assignment models and APIs must exist).

**New models/migrations likely required:** None expected — bulk operations operate on existing models. Possibly an `ImportJob` or `ImportBatch` tracking model for operational audit.

**Frontend work expected:** Import wizard pages, bulk操作 UI, error reporting views.

**Testing requirements:** Unit tests for bulk validation logic, duplicate detection, error handling. API tests for import endpoints. Frontend build verification.

---

## Phase 6 — Hall-Ticket Lifecycle Management

**Status: PLANNED**

Focus:
- Hall-ticket batches
- Document lifecycle management
- Reprocessing workflows
- Review queues
- Verification history
- Operational document management

**Dependencies:** Phases 0–4 (document, extraction, matching, verification models must exist).

**New models/migrations likely required:** Possibly `HallTicketBatch` model for batch tracking. Document lifecycle status extensions.

**Frontend work expected:** Batch management views, reprocessing UI, review queue pages.

**Testing requirements:** Unit tests for lifecycle transitions, batch processing. API tests for batch endpoints.

---

## Phase 7 — Identity Verification Foundation

**Status: PLANNED**

Focus:
- Identity verification architecture
- Identity evidence models
- Verification interfaces
- AI perception abstraction
- Human-review fallback
- Privacy and security design
- No production biometric identification yet

**Dependencies:** Phases 0–4. This is an architectural phase establishing abstractions before Phase 8 implements face verification.

**New models/migrations likely required:** `IdentityVerification` or `IdentityEvidence` model. Verification interface ABCs.

**Frontend work expected:** Architecture-level — no user-facing pages expected yet.

**Testing requirements:** Unit tests for abstraction interfaces, mock implementations.

---

## Phase 8 — Face Verification / UniFace Integration

**Status: PLANNED**

Focus:
- Face detection abstraction
- Face verification interface
- UniFace integration behind an abstraction
- Face evidence storage
- Configurable verification thresholds
- Failure and review states
- Security/privacy controls

**Dependencies:** Phase 7 (identity verification abstractions must exist).

**New models/migrations likely required:** `FaceVerification` evidence model, face embedding storage. `backend/app/ai/face.py` implementation.

**Frontend work expected:** Face verification status views, review workflow for failures.

**Testing requirements:** Unit tests for face abstraction, threshold logic, failure states. Integration tests with mock face data.

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

1. Phases 0–4 are COMPLETE.
2. Phases 5–23 are PLANNED.
3. Do not mark future phases complete.
4. Do not implement future phases.
5. Each future phase should eventually be broken into smaller implementation steps before coding begins.
6. Future implementation must proceed sequentially unless the architecture explicitly justifies another order.
7. AI systems provide evidence/perception; business logic makes authorization and operational decisions.
8. Never hard-code production data or thresholds.
9. Database changes require Alembic migrations.
10. Preserve auditability and security throughout the project.
11. Do not introduce paid/cloud AI services unless explicitly planned and approved.
12. Face/biometric functionality must have privacy, security, fallback, and human-review considerations.
13. Never destructively reset production-style databases.
14. Never weaken or delete tests to make a feature pass.

---

## Current Project State

- **Current phase:** Phase 4 COMPLETE
- **Current completed step:** Phase 4 Step 11 — Admin Management Pages
- **Current tests:** 373 passing
- **Latest commit:** f86e9d5
- **Frontend pages:** `/`, `/students`, `/documents`, `/dashboard`, `/subjects`, `/exams`, `/exam-halls`
- **Next phase:** Phase 5 — Examination Operations & Data Import
- **Next action:** Before implementation, break Phase 5 into concrete steps and implement only Phase 5 Step 1.

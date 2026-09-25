# ExamGuard Backend Schema

## Database Engine

- **Engine**: PostgreSQL
- **Migration System**: Alembic (26 migrations)
- **Head revision**: `026_create_users_table.py`
- **Migration consistency**: User model and migration consistent; all 26 migrations verified reversible
- **Soft-delete behavior**: `is_active` field used throughout (not hard deletes); no SQL `DELETE` statements in normal operations; records soft-deactivated via `is_active = false`

## All Actual Tables/Models

### Users (migration 026)

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial/identity | PK |
| email | VARCHAR | YES | — | UNIQUE + INDEX |
| full_name | VARCHAR | YES | — | — |
| firebase_uid | VARCHAR | YES | — | UNIQUE + INDEX |
| role | VARCHAR | YES | 'REVIEWER' | CHECK: IN ('ADMIN', 'OPERATOR', 'REVIEWER') |
| is_active | BOOLEAN | YES | true | Indexed; soft-delete |
| created_at | TIMESTAMP | YES | — | — |
| updated_at | TIMESTAMP | YES | — | — |
| last_login_at | TIMESTAMP | YES | — | — |

### Students

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| user_id | INTEGER | YES | — | FK → users(id), cascade |
| usn | VARCHAR | YES | — | — |
| full_name | VARCHAR | YES | — | — |
| email | VARCHAR | YES | — | — |
| is_active | BOOLEAN | YES | true | — |
| created_at | TIMESTAMP | YES | — | — |
| updated_at | TIMESTAMP | YES | — | — |

### Exam Halls

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| name | VARCHAR | YES | — | — |
| capacity | INTEGER | YES | — | — |
| location_detail | TEXT | YES | — | — |
| is_active | BOOLEAN | YES | true | — |
| created_at | TIMESTAMP | YES | — | — |
| updated_at | TIMESTAMP | YES | — | — |

### Cameras

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| exam_hall_id | INTEGER | YES | — | FK → exam_halls(id), cascade |
| device_identifier | VARCHAR | YES | — | — |
| camera_type | VARCHAR | YES | — | (e.g., "USB", "IP", "RTSP") |
| manufacturer | VARCHAR | YES | — | — |
| model_name | VARCHAR | YES | — | — |
| resolution | VARCHAR | YES | — | (e.g., "1920x1080") |
| status | VARCHAR | YES | 'ONLINE' | Enum: ONLINE, OFFLINE, UNKNOWN, DISABLED |
| connection_info | TEXT | YES | — | Plain text (IP/URL only; no credentials) |
| is_active | BOOLEAN | YES | true | Soft-delete pattern |
| last_seen_at | TIMESTAMP | YES | — | Set on ONLINE observation |
| last_health_check_at | TIMESTAMP | YES | — | — |
| health_reason | VARCHAR | YES | 'NO_OBSERVATION' | Enum: DEVICE_RESPONDED, DEVICE_UNREACHABLE, DEVICE_DISABLED, NO_OBSERVATION |

### Entry Points

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| exam_hall_id | INTEGER | YES | — | FK → exam_halls(id), cascade |
| code | VARCHAR | YES | — | Auto-uppercased on create; unique |
| description | TEXT | YES | — | — |
| location_detail | TEXT | YES | — | — |
| is_active | BOOLEAN | YES | true | — |
| created_at | TIMESTAMP | YES | — | — |
| updated_at | TIMESTAMP | YES | — | — |

### Camera Entry Point Mappings

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| camera_id | INTEGER | YES | — | FK → cameras(id), cascade (on delete) |
| entry_point_id | INTEGER | YES | — | FK → entry_points(id), cascade (on delete) |
| is_enabled | BOOLEAN | YES | true | — |
| created_at | TIMESTAMP | YES | — | — |
| Updated at | TIMESTAMP | YES | — | — |

### Identity Verification Attempts

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| student_id | INTEGER | YES | — | FK → students(id), cascade |
| exam_registration_id | INTEGER | YES | — | FK → exam_registrations(id), cascade |
| hall_ticket_id | INTEGER | YES | — | FK → hall_tickets(id), cascade |
| status | VARCHAR | YES | 'CREATED' | Enum: CREATED, IN_PROGRESS, COMPLETED, FAILED, CANCELLED |
| decision | VARCHAR | YES | 'PENDING' | Enum: MATCH, NO_MATCH, INCONCLUSIVE, PENDING |
| method | VARCHAR | YES | 'FACE' | Enum: FACE, MANUAL, DOCUMENT, OTHER |
| failure_reason | JSON | YES | — | Free-form; override audit entries |
| created_at | TIMESTAMP | YES | now() | — |
| started_at | TIMESTAMP | YES | — | — |
| completed_at | TIMESTAMP | YES | — | — |
| escalated_at | TIMESTAMP | YES | — | — |
| resolved_at | TIMESTAMP | YES | — | — |

### Identity Verification Evidence

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| attempt_id | INTEGER | YES | — | FK → identity_verification_attempts(id), cascade |
| signal_type | VARCHAR | YES | — | (e.g., similarity_score, liveness_score, image_quality) |
| confidence | FLOAT | YES | — | Score value (0.0-1.0 or str) |
| signal_value | VARCHAR | YES | — | e.g., "PASS", "FAIL", "GOOD", "POOR" |
| details | JSON | YES | — | Provider metadata; `source: "face_verification_provider"` |
| created_at | TIMESTAMP | YES | now() | — |

### Entry Verifications

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| student_id | INTEGER | YES | — | FK → students(id), cascade |
| exam_registration_id | INTEGER | YES | — | FK → exam_registrations(id), cascade |
| entry_point_id | INTEGER | YES | — | FK → entry_points(id), cascade |
| hall_ticket_id | INTEGER | YES | — | FK → hall_tickets(id), cascade |
| camera_id | INTEGER | YES | — | FK → cameras(id), cascade |
| status | VARCHAR | YES | 'PENDING' | Enum: PENDING, IN_PROGRESS, COMPLETED, CANCELLED |
| decision | VARCHAR | YES | 'PENDING' | Enum: GRANTED, DENIED, ESCALATED |
| threshold | FLOAT | YES | 0.85 | Configurable; `IDENTITY_VERIFICATION_MATCH_THRESHOLD` |
| near_threshold_factor | FLOAT | YES | 0.7 | Configurable; `IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR` |
| policy_version | VARCHAR | YES | "1.0" | — |
| begun_at | TIMESTAMP | YES | — | — |
| hall_ticket_check_status | VARCHAR | YES | 'PENDING' | Enum: PASSED, FAILED, PENDING, SKIPPED |
| seat_check_status | VARCHAR | YES | 'PENDING' | Enum: PASSED, FAILED, PENDING, SKIPPED |
| identity_check_status | VARCHAR | YES | 'PENDING' | Enum: PASSED, FAILED, PENDING, SKIPPED |
| commenced_at | TIMESTAMP | YES | — | — |
| completed_at | TIMESTAMP | YES | — | — |
| escalated_at | TIMESTAMP | YES | — | — |
| resolved_at | TIMESTAMP | YES | — | — |

### Exam Registrations

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| student_id | INTEGER | YES | — | FK → students(id), cascade |
| exam_id | INTEGER | YES | — | FK → exams(id), cascade |
| hall_ticket_id | INTEGER | YES | — | FK → hall_tickets(id), cascade |
| seat_id | INTEGER | YES | — | FK → seat_assignments(id), cascade |
| status | VARCHAR | YES | 'ACTIVE' | Enum: ACTIVE, COMPLETED, CANCELLED |
| enrolled_at | TIMESTAMP | YES | now() | — |
| completed_at | TIMESTAMP | YES | — | — |

### Seat Assignments

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| exam_registration_id | INTEGER | YES | — | FK → exam_registrations(id), cascade |
| seat_number | VARCHAR | YES | — | (e.g., "A-17") |
| assigned_at | TIMESTAMP | YES | — | — |
| is_active | BOOLEAN | YES | true | — |

### Hall Tickets

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| exam_registration_id | INTEGER | YES | — | FK → exam_registrations(id), cascade |
| student_id | INTEGER | YES | — | FK → students(id), cascade |
| hall_id | INTEGER | YES | — | FK → exam_halls(id), cascade |
| status | VARCHAR | YES | 'CREATED' | Enum: CREATED, EXTRACTED, MATCHED, VERIFIED, REJECTED, CANCELLED |
| document_linked | BOOLEAN | YES | false | — |
| document_extracted | BOOLEAN | YES | false | — |
| document_match_status | VARCHAR | YES | 'PENDING' | Enum: PENDING, MATCHED, NO_MATCH |
| verification_outcome_id | INTEGER | YES | — | FK → identity_verification_attempts(id), cascade (optional) |
| verified_by_id | INTEGER | YES | — | FK → users(id), cascade (optional) |
| created_at | TIMESTAMP | YES | now() | — |
| updated_at | TIMESTAMP | YES | — | — |

### Security Events

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| attempt_id | INTEGER | YES | — | FK → identity_verification_attempts(id), cascade |
| event_type | VARCHAR | YES | — | (e.g., IDENTITY_MISMATCH, WRONG_HALL, LIVENESS_SPOOF, WRONG_ENTRY_POINT, REPEATED_FAILED_VERIFICATION) |
| severity | VARCHAR | YES | 'INFO' | Enum: INFO, WARNING, ERROR, CRITICAL |
| description | TEXT | YES | — | Human-readable; safe (no stack traces, no internal details) |
| recorded_by | INTEGER | YES | — | FK → users(id), cascade (optional) |
| created_at | TIMESTAMP | YES | now() | — |

### Security Alerts (Monitoring)

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| event_id | INTEGER | YES | — | FK → security_events(id), cascade |
| title | VARCHAR | YES | — | Short alert title |
| message | TEXT | YES | — | Human-readable detail (safe) |
| severity | VARCHAR | YES | 'INFO' | Enum: INFO, WARNING, ERROR, CRITICAL |
| is_resolved | BOOLEAN | YES | false | — |
| resolved_at | TIMESTAMP | YES | — | — |
| recorded_by | INTEGER | YES | — | FK → users(id), cascade (optional) |
| created_at | TIMESTAMP | YES | now() | — |

### Audit/Import Logs

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | INTEGER | NO | serial | PK |
| import_type | VARCHAR | YES | — | (e.g., STUDENTS, SUBJECTS_EXAMS, REGISTRATIONS, SEAT_ASSIGNMENTS) |
| operation | VARCHAR | YES | — | (e.g., CREATE, UPDATE, DELETE) |
| status | VARCHAR | YES | 'SUCCESS' | Enum: SUCCESS, FAILURE |
| items_processed | INTEGER | YES | 0 | — |
| items_failed | INTEGER | YES | 0 | — |
| error_summary | TEXT | YES | — | Bounded error summary; no stack traces |
| recorded_by | INTEGER | YES | — | FK → users(id), cascade (optional) |
| created_at | TIMESTAMP | YES | now() | — |

## ASCII Relationship Diagram

```
users
├─ id (PK)
├─ email (UNIQUE, INDEX)
├─ firebase_uid (UNIQUE, INDEX)
├─ role (ADMIN/OPERATOR/REVIEWER, default REVIEWER)
├─ is_active (soft-delete, indexed)
├─ created_at, updated_at, last_login_at
├─ students (1:many, cascade)
│   └─ user_id (FK → users.id)
├─ exam_registrations (1:many, cascade)
│   └─ student_id (FK → students.id)
├─ hall_tickets (1:many, cascade)
│   └─ student_id (FK → students.id)
│   └─ exam_registration_id (FK → exam_registrations.id)
├─ camera_device_credentials (1:many, cascade on delete)
│   └─ camera_id (FK → cameras.id)
├─ identity_verification_attempts (1:many, cascade)
│   └─ student_id (FK → students.id)
│   └─ exam_registration_id (FK → exam_registrations.id)
│   └─ hall_ticket_id (FK → hall_tickets.id, optional)
│   └─ verified_by_id (FK → users.id, optional)
│   └─ failure_reason (JSON, override audit)
├─ entry_verifications (1:many, cascade)
│   └─ student_id (FK → students.id)
│   └─ exam_registration_id (FK → exam_registrations.id)
│   └─ entry_point_id (FK → entry_points.id)
│   └─ hall_ticket_id (FK → hall_tickets.id)
│   └─ camera_id (FK → cameras.id)
│   ├─ status, decision, threshold, near_threshold_factor, policy_version
│   └─ checks: hall_ticket_check, seat_check, identity_check
│   └─ begun_at, completed_at, escalated_at, resolved_at
├─ security_events (1:many, cascade)
│   └─ attempt_id (FK → identity_verification_attempts.id)
│   └─ event_type, severity, description (safe)
│   └─ recorded_by (FK → users.id, optional)
├─ security_alerts (1:many, cascade)
│   └─ event_id (FK → security_events.id)
│   ├─ title, message, severity
│   └─ is_resolved, resolved_at
└─ import_audit_logs (1:many, cascade)
    ├─ import_type, operation, status
    ├─ items_processed, items_failed
    └─ error_summary (bounded), recorded_by

exam_halls
├─ id (PK)
├─ name, capacity, location_detail
├─ is_active, created_at, updated_at
├─ cameras (1:many, cascade)
│   └─ exam_hall_id (FK → exam_halls.id)
│   ├─ status (ONLINE/OFFLINE/UNKNOWN/DISABLED)
│   ├─ is_active (soft-delete)
│   ├─ last_seen_at, last_health_check_at, health_reason
│   └─ device_credentials (1:many, cascade on delete)
│      └─ camera_id (FK → cameras.id)
└─ camera_entry_point_mappings (1:many)
    ├─ camera_id (FK → cameras.id, cascade on delete)
    └─ entry_point_id (FK → entry_points.id, cascade on delete)

entry_points
├─ id (PK)
├─ exam_hall_id (FK → exam_halls.id, cascade)
├─ code (auto-uppercased, unique)
├─ description, location_detail
├─ is_active, created_at, updated_at

seat_assignments
├─ id (PK)
├─ exam_registration_id (FK → exam_registrations.id, cascade)
├─ seat_number, assigned_at, is_active

students
├─ id (PK)
├─ user_id (FK → users.id, cascade)
├─ usn, full_name, email
├─ is_active, created_at, updated_at

hall_tickets
├─ id (PK)
├─ exam_registration_id (FK → exam_registrations.id, cascade)
├─ student_id (FK → students.id, cascade)
├─ hall_id (FK → exam_halls.id, cascade)
├─ status (CREATED/EXTRACTED/MATCHED/VERIFIED/REJECTED/CANCELLED)
├─ document_linked, document_extracted, document_match_status
├─ verification_outcome_id (FK → identity_verification_attempts.id, optional)
├─ verified_by_id (FK → users.id, optional)
├─ created_at, updated_at
```

## Indexes & Constraints

- **Unique indexes**: `email` (unique + index), `firebase_uid` (unique + index)
- **Soft-delete index**: `is_active` indexed on users table
- **Foreign keys**: All models have proper FK constraints with cascade/optional behavior as noted
- **Check constraints**: `role` IN ('ADMIN', 'OPERATOR', 'REVIEWER'); `status` enums; `is_active` BOOLEAN
- **Cascade behavior**: Standard SQLAlchemy cascade rules; `ondelete="CASCADE"` on many FK relationships; `ondelete="SET NULL"` where appropriate (e.g., optional relationships)

## Timestamps

- **created_at**: Set on record creation; not typically user-editable
- **updated_at**: Updated on record modification; managed by app logic/triggers
- **now()**: Used as default in Alembic migrations for `created_at`, ` commenced_at`, etc.
- **Consistent**: All models have `created_at`; many have `updated_at`

## User/Role Relationships

- **Role hierarchy**: ADMIN > OPERATOR > REVIEWER
- **User model**: `role` field defaults to `'REVIEWER'`; can be `'ADMIN'` or `'OPERATOR'`
- **No self-promotion**: Users cannot change their own role
- **Google user auto-promotion**: Blocked; new Google users receive `REVIEWER` role by default
- **Admin provisioning**: `INITIAL_ADMIN_EMAILS` env var; only evaluated when no ADMIN exists in system; one-time grant on first admin login

## Student Relationships

- **FK → users**: `user_id` on students table; cascade delete; each student linked to one user
- **USN**: Unique school identification number; may be indexed in future; not currently unique constraint but application-enforced
- **Full name**: Free text; not validated beyond length

## Exam Relationships

- **FK → halls**: `exam_hall_id` on cameras; cascade delete (delete hall → delete all cameras)
- **FK → registrations**: Various models reference exam_registrations; cascade where appropriate
- **FK → seats**: `exam_registration_id` on seat_assignments; cascade delete (delete registration → delete seat assignments)

## Hall Relationships

- **FK → cameras**: `exam_hall_id`; cascade (delete hall → delete cameras)
- **FK → entry_points**: `exam_hall_id`; cascade (delete hall → delete entry points)
- **Camera deactivation**: does not break mappings (mappings preserve history; deactivation sets `is_active=false` and `status=DISABLED`)

## Registration Relationships

- **FK → students**: `student_id`; cascade delete (delete student → delete registrations)
- **FK → exams**: `exam_id`; cascade where appropriate
- **FK → hall_tickets**: Various models reference hall_tickets; cascade where noted
- **FK → seat_assignments**: `exam_registration_id`; cascade (delete registration → delete seat assignments)

## Seat Relationships

- **FK → exam_registrations**: `exam_registration_id`; cascade delete (delete registration → delete seat assignments)
- **Seat number**: Free text (e.g., "A-17"); not validated beyond format

## Hall Ticket Relationships

- **FK → exam_registrations**: `exam_registration_id`; cascade delete (delete registration → delete hall ticket)
- **FK → students**: `student_id`; cascade delete (delete student → delete hall ticket)
- **FK → halls**: `hall_id`; cascade delete (delete hall → delete hall ticket)
- **FK → identity_verification_attempts**: `verification_outcome_id`; optional (cascade if present)
- **Status transitions**: CREATED → EXTRACTED → MATCHED → VERIFIED/REJECTED/CANCELLED; auto-transitions via hooks; manual via PATCH

## Identity Verification Relationships

- **FK → students**: `student_id` on identity_verification_attempts; cascade delete
- **FK → exam_registrations**: `exam_registration_id`; cascade delete
- **FK → hall_tickets**: `hall_ticket_id` on identity_verification_attempts; optional; cascade if present
- **FK → users**: `verified_by_id` on hall_tickets; optional; cascade if present
- **FK → identity_verification_attempts**: `verification_outcome_id` on hall_tickets; optional; cascade if present

## Monitoring/Security Relationships

- **FK → attempts**: `attempt_id` on security_events; cascade delete (delete attempt → delete security events)
- **FK → users**: `recorded_by` on security_events, security_alerts, import_audit_logs; optional; cascade if present
- **Monitoring buffers**: In-memory; no DB persistence (Phase 19); cleared on restart
- **Alert thresholds**: Configurable via `PROXY_RISK_*` settings; no DB model for alert thresholds

## Import/Audit Relationships

- **FK → users**: `recorded_by` on import_audit_logs; optional; cascade if present
- **Import tracking**: `import_type`, `operation`, `status`, `items_processed`, `items_failed`, `error_summary` (bounded; no stack traces)
- **Audit trail**: Uses `failure_reason` field on attempts for override entries; no new DB tables

## Session/Gate Structures

- **Examination sessions**: Managing gate opening/closing workflow; active hall monitoring; session-level operational controls; session-level audit trail
- **Gate status**: Tracked via camera health observations; `is_active` ≠ `status`; `ONLINE` only set when device responds; `OFFLINE` when unreachable; `DISABLED` set automatically when camera deactivated
- **Health observations**: Only path to change camera status; `record_health_observation()` endpoint; future timestamps rejected

## Any Other Actual Models

- **CameraDeviceCredential**: 256-bit secrets; SHA-256 hashed before storage; raw secret returned ONCE at provisioning; never stored/logged/returned again; `camera_id` FK; `secret_hash`, `secret_prefix`, `status`, `camera_id` fields; constant-time comparison via `hmac.compare_digest`; identity derived from authenticated credential (caller cannot override camera_id); admin CRUD cannot change camera status; only `record_health_observation()` changes status; revoked credentials immediately rejected; inactive cameras cannot authenticate
- **ErpSyncLog/ErpSyncJob**: (planned; not in current codebase) tracking sync operations; no core domain models expected

Note: This schema is derived from the actual SQLAlchemy models and Alembic migrations in the repository. No columns or relationships are invented beyond what the code establishes.
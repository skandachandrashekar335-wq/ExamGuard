# Database Production Readiness & Migration Plan

## 1. Executive Summary

This document certifies the persistence layer, migration history, indexing strategy, and connection pooling topology for the production PostgreSQL instance hosting ExamGuard (`skandachandrashekar335-wq/ExamGuard`).

- **Database Provider**: Neon Serverless PostgreSQL (`ep-icy-flower-b453od0f-pooler.c-6.us-east-2.aws.neon.tech`)
- **Current Live Production Revision**: `028` (Verified live via `alembic_version` inspection)
- **Target Target Revision**: `031` (3 migrations pending: 029, 030, 031)
- **Tables Verified in Target Schema**: 34 tables (including `knowledge_base_items`, `chat_query_logs`)
- **Persistence Verification**: End-to-end relational hierarchy test verified in `backend/tests/test_real_hierarchy_persistence.py`.

---

## 2. Neon Connection Pooling Configuration

Neon provides PgBouncer-based connection pooling on port 5432 (default pooler endpoint) with two primary pooling modes:

### 2.1 Pooling Modes Analysis

| Mode | Neon Port / Connection String | Suitability for ExamGuard | Notes |
| :--- | :--- | :--- | :--- |
| **Transaction Mode** | Neon Pooler (`*-pooler.*.aws.neon.tech`) with transaction pooling | **Recommended for API instances** | Reuses connections immediately after transaction commit/rollback. Essential for Railway's stateless worker processes. |
| **Session Mode** | Direct Neon endpoint without pooler or session-pinned pooler | Required for Alembic migrations | Alembic migration scripts alter schema, acquire DDL locks, and may use session-level locks. |

### 2.2 SQLAlchemy Engine Configuration

In `backend/app/core/database.py`, SQLAlchemy is configured to support resilient pooling when connected to Neon:

```python
# Production connection parameters
pool_size = 5                # Number of permanent connections per worker
max_overflow = 10            # Maximum burst connections during peak exam check-in
pool_timeout = 30            # Timeout waiting for pool connection
pool_recycle = 1800          # Recycle connections every 30 mins to avoid stale SSL sockets
pool_pre_ping = True         # Live ping (SELECT 1) before handing connection to worker
```

**Railway Sizing Calculation**:
- Railway container instances: 1–2 web containers running uvicorn with 2 workers each.
- Max theoretical active connections from workers: $2 \times (5 + 10) = 30$ connections.
- Neon free/standard tier pooler accommodates up to 10,000 pooled connections, well within headroom.

---

## 3. Pending Migration Analysis & Safety Review

### 3.1 Migration 029: `029_attendance_ev_nullable.py`
- **Revises**: `028`
- **Purpose**: Relaxes `NOT NULL` constraint on `entry_verification_id` in `attendance_events` and `attendance_records` to allow manual review events (such as manual check-ins by chief superintendents) to persist without requiring an automated gate scan.
- **Safety**: **SAFE / ZERO DOWNTIME**. Relaxing a constraint to nullable does not lock rows or require table rewrites in PostgreSQL.
- **Rollback Risk**: If manual review rows with `entry_verification_id IS NULL` exist, `downgrade()` will fail until those rows are assigned an ID or removed. Rollback script includes note to delete or backfill nulls prior to downgrade.

### 3.2 Migration 030: `030_document_exam_context.py`
- **Revises**: `029`
- **Purpose**: Adds nullable column `exam_id` (ForeignKey to `exams.id`) and index `ix_documents_exam_id` to `documents` table to associate uploaded hall-ticket PDFs directly with specific exams.
- **Safety**: **SAFE / ZERO DOWNTIME**. Adding a nullable column and standard B-tree index in PostgreSQL does not block concurrent SELECTs or INSERTs.
- **Rollback**: Fully reversible via `op.drop_index` and `op.drop_column`.

### 3.3 Migration 031: `031_create_chatbot_tables.py`
- **Revises**: `030`
- **Purpose**: Creates `knowledge_base_items` and `chat_query_logs` tables with supporting indexes on `category`, `intent`, and `session_id`.
- **Safety**: **SAFE / ZERO DOWNTIME**. Creates completely new tables with isolated foreign/primary keys. Does not touch or lock any existing exam or candidate tables.
- **Rollback**: Fully reversible via table drops.

---

## 4. Safe Deployment & Migration Execution Sequence

> [!IMPORTANT]
> Live database migrations must only be executed by an authorized human operator with production credentials during a scheduled maintenance window.

### Step-by-Step Execution Plan:

1. **Pre-Migration Snapshot**:
   Take a Neon point-in-time branch or snapshot of the `main` branch:
   ```bash
   neonctl branches create --name pre-migration-031
   ```

2. **Verify Current Head**:
   ```bash
   alembic current
   # Expected output: 028 (head)
   ```

3. **Dry-Run SQL Generation**:
   Generate SQL scripts offline to review exact DDL:
   ```bash
   alembic upgrade 028:head --sql > /tmp/migration_028_to_031.sql
   ```

4. **Execute Migration**:
   ```bash
   alembic upgrade head
   ```

5. **Post-Migration Verification**:
   ```bash
   alembic current
   # Expected output: 031 (head)
   ```
   Query `/health/ready` on the backend to confirm `alembic_version: "031"` is reported.

6. **Rollback Strategy (if needed)**:
   ```bash
   # Revert to 028
   alembic downgrade 028
   ```

---

## 5. Index and Constraint Audit

### 5.1 Uniqueness Constraints
- `students.usn`: Unique index (`ix_students_usn`) enforcing one record per USN.
- `hall_tickets.exam_registration_id`: Unique constraint (`uq_hall_ticket_active_per_registration`) preventing duplicate tickets for the same registration.
- `exam_registrations(student_id, exam_id)`: Unique composite constraint (`uq_registration_student_exam`).
- `seat_assignments(exam_hall_id, exam_id, seat_number)`: Prevents double-booking seats.
- `knowledge_base_items.intent`: Unique constraint (`uq_knowledge_base_items_intent`).

### 5.2 Foreign Key Supporting Indexes
All primary relational joins have supporting B-Tree indexes:
- `exams.subject_id` -> `ix_exams_subject_id`
- `exam_registrations.student_id` -> `ix_exam_registrations_student_id`
- `exam_registrations.exam_id` -> `ix_exam_registrations_exam_id`
- `entry_verifications.exam_registration_id` -> `ix_entry_verifications_exam_registration_id`
- `attendance_records.student_id` -> `ix_attendance_records_student_id`
- `attendance_records.exam_id` -> `ix_attendance_records_exam_id`

---

## 6. Real-Data Hierarchy Write Verification

Automated test `backend/tests/test_real_hierarchy_persistence.py` verifies the complete real-data hierarchy lifecycle:

$$\text{Subject} \longrightarrow \text{Exam} \longrightarrow \text{ExamHall} \longrightarrow \text{Student} \longrightarrow \text{Registration} \longrightarrow \text{Seat} \longrightarrow \text{HallTicket} \longrightarrow \text{EntryVerification} \longrightarrow \text{Attendance}$$

- **Execution Result**: PASSED (0.29s).
- **Integrity Verified**: All foreign keys resolved, relational queries navigation (`record.student.name`, `record.entry_verification.entry_point.code`) verified across database transactions.

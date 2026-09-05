"""Create attendance tables

Revision ID: 022
Revises: 021
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=False,
            index=True,
            comment="Student this attendance record is for",
        ),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=False,
            index=True,
            comment="Exam this attendance record is for",
        ),
        sa.Column(
            "exam_registration_id",
            sa.Integer(),
            sa.ForeignKey("exam_registrations.id"),
            nullable=False,
            index=True,
            comment="Exam registration this attendance record is for",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="PRESENT",
            index=True,
            comment="Current attendance status",
        ),
        sa.Column(
            "entry_verification_id",
            sa.Integer(),
            sa.ForeignKey("entry_verifications.id"),
            nullable=False,
            index=True,
            comment="Entry verification that established this attendance",
        ),
        sa.Column(
            "entry_method",
            sa.String(50),
            nullable=False,
            server_default="VERIFIED_ENTRY",
            comment="How attendance was recorded: VERIFIED_ENTRY or MANUAL_ENTRY",
        ),
        sa.Column(
            "entry_time",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the student entered (from EV created_at or manual override)",
        ),
        sa.Column(
            "hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=False,
            index=True,
            comment="Exam hall where student entered (snapshot at entry time)",
        ),
        sa.Column(
            "seat_number",
            sa.String(50),
            nullable=True,
            comment="Seat number (snapshot from SeatAssignment at entry time)",
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When this attendance record was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "exam_registration_id",
            name="uq_attendance_record_per_registration",
        ),
    )

    op.create_table(
        "attendance_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=False,
            index=True,
            comment="Student this event is for",
        ),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=False,
            index=True,
            comment="Exam this event is for",
        ),
        sa.Column(
            "exam_registration_id",
            sa.Integer(),
            sa.ForeignKey("exam_registrations.id"),
            nullable=False,
            index=True,
            comment="Exam registration this event is for",
        ),
        sa.Column(
            "entry_verification_id",
            sa.Integer(),
            sa.ForeignKey("entry_verifications.id"),
            nullable=False,
            index=True,
            comment="Entry verification that triggered this event",
        ),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            index=True,
            comment="Type of attendance event",
        ),
        sa.Column(
            "status_snapshot",
            sa.String(20),
            nullable=False,
            comment="AttendanceRecord.status after this event (or N/A for denied/escalated)",
        ),
        sa.Column(
            "recorded_by",
            sa.String(100),
            nullable=True,
            comment="system for automated, admin identifier for manual corrections",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Reason for correction or excuse",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
            comment="When this event was recorded",
        ),
        sa.UniqueConstraint(
            "entry_verification_id",
            name="uq_attendance_event_per_entry_verification",
        ),
    )


def downgrade() -> None:
    op.drop_table("attendance_events")
    op.drop_table("attendance_records")

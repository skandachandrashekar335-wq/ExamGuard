"""Create examination session and gate event tables, add session_id FKs

Revision ID: 025
Revises: 024
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "examination_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=False,
            index=True,
            comment="Exam this session is for",
        ),
        sa.Column(
            "exam_hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=False,
            index=True,
            comment="Hall where this session takes place",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="NOT_STARTED",
            index=True,
            comment="Session lifecycle status",
        ),
        sa.Column(
            "gate_status",
            sa.String(50),
            nullable=False,
            server_default="GATES_CLOSED",
            comment="Current gate status for this session",
        ),
        sa.Column(
            "gate_open_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When gates were opened",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the session officially started",
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the session ended",
        ),
        sa.Column(
            "expected_capacity",
            sa.Integer(),
            nullable=True,
            comment="Expected number of students for this session",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Optional notes about this session",
        ),
        sa.Column(
            "created_by",
            sa.String(100),
            nullable=True,
            comment="Who created this session",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "exam_id",
            "exam_hall_id",
            name="uq_session_exam_hall",
        ),
    )

    op.create_table(
        "gate_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("examination_sessions.id"),
            nullable=False,
            index=True,
            comment="Session this gate event belongs to",
        ),
        sa.Column(
            "previous_status",
            sa.String(50),
            nullable=False,
            comment="Gate status before this change",
        ),
        sa.Column(
            "new_status",
            sa.String(50),
            nullable=False,
            comment="Gate status after this change",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Reason for the gate status change",
        ),
        sa.Column(
            "performed_by",
            sa.String(100),
            nullable=True,
            comment="Who performed this gate operation",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
    )

    # Add session_id to entry_verifications
    op.add_column(
        "entry_verifications",
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("examination_sessions.id"),
            nullable=True,
            index=True,
            comment="Examination session this entry belongs to",
        ),
    )

    # Add session_id to attendance_records
    op.add_column(
        "attendance_records",
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("examination_sessions.id"),
            nullable=True,
            index=True,
            comment="Examination session this attendance belongs to",
        ),
    )


def downgrade() -> None:
    op.drop_column("attendance_records", "session_id")
    op.drop_column("entry_verifications", "session_id")
    op.drop_table("gate_events")
    op.drop_table("examination_sessions")

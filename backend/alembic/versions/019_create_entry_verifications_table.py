"""Create entry_verifications table

Revision ID: 019
Revises: 018
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entry_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=False,
            index=True,
            comment="Student attempting entry",
        ),
        sa.Column(
            "exam_registration_id",
            sa.Integer(),
            sa.ForeignKey("exam_registrations.id"),
            nullable=False,
            index=True,
            comment="Registration this entry attempt is for",
        ),
        sa.Column(
            "exam_hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=False,
            index=True,
            comment="Exam hall the student is attempting to enter",
        ),
        sa.Column(
            "entry_point_id",
            sa.Integer(),
            sa.ForeignKey("entry_points.id"),
            nullable=False,
            index=True,
            comment="Physical entry point where student arrived",
        ),
        sa.Column(
            "hall_ticket_id",
            sa.Integer(),
            sa.ForeignKey("hall_tickets.id"),
            nullable=True,
            index=True,
            comment="Hall ticket being verified (nullable until linked)",
        ),
        sa.Column(
            "identity_verification_attempt_id",
            sa.Integer(),
            sa.ForeignKey("identity_verification_attempts.id"),
            nullable=True,
            index=True,
            comment="Identity verification attempt created for this entry",
        ),
        sa.Column(
            "camera_id",
            sa.Integer(),
            sa.ForeignKey("cameras.id"),
            nullable=True,
            index=True,
            comment="Camera that observed the entry",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="PENDING",
            index=True,
            comment="Lifecycle status of this entry verification",
        ),
        sa.Column(
            "hall_ticket_check",
            sa.String(50),
            nullable=False,
            server_default="PENDING",
            comment="Hall ticket verification result",
        ),
        sa.Column(
            "identity_check",
            sa.String(50),
            nullable=False,
            server_default="PENDING",
            comment="Identity verification result",
        ),
        sa.Column(
            "seat_check",
            sa.String(50),
            nullable=False,
            server_default="PENDING",
            comment="Seat assignment verification result",
        ),
        sa.Column(
            "escalation_reason",
            sa.Text(),
            nullable=True,
            comment="Reason for human review escalation",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When escalation was resolved",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
            comment="When the entry verification was initiated",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("entry_verifications")

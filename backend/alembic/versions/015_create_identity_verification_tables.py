"""create identity verification tables

Revision ID: 015
Revises: 014
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_verification_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "exam_registration_id",
            sa.Integer(),
            sa.ForeignKey("exam_registrations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "hall_ticket_id",
            sa.Integer(),
            sa.ForeignKey("hall_tickets.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="CREATED",
            index=True,
        ),
        sa.Column(
            "verification_method",
            sa.String(50),
            nullable=False,
            server_default="MANUAL",
        ),
        sa.Column(
            "decision",
            sa.String(50),
            nullable=False,
            server_default="PENDING",
            index=True,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "identity_verification_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.Integer(),
            sa.ForeignKey("identity_verification_attempts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "signal_type",
            sa.String(100),
            nullable=False,
            comment="Type of evidence signal (e.g. similarity_score, liveness, quality)",
        ),
        sa.Column(
            "signal_value",
            sa.String(500),
            nullable=True,
            comment="Numeric or categorical value of the signal",
        ),
        sa.Column(
            "provider_name",
            sa.String(100),
            nullable=True,
            comment="Name of the AI/provider that produced this evidence",
        ),
        sa.Column(
            "provider_version",
            sa.String(50),
            nullable=True,
            comment="Version of the provider",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Provider-reported confidence for this signal",
        ),
        sa.Column(
            "details",
            sa.Text(),
            nullable=True,
            comment="Additional details or metadata about this evidence",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("identity_verification_evidence")
    op.drop_table("identity_verification_attempts")

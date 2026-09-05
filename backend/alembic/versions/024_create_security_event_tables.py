"""Create security_events and security_alerts tables

Revision ID: 024
Revises: 023
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            index=True,
            comment="Type of security event",
        ),
        sa.Column(
            "severity",
            sa.String(50),
            nullable=False,
            index=True,
            comment="Event severity level",
        ),
        sa.Column(
            "entity_type",
            sa.String(100),
            nullable=False,
            comment="Domain entity type this event relates to",
        ),
        sa.Column(
            "entity_id",
            sa.Integer(),
            nullable=False,
            comment="Domain entity ID",
        ),
        sa.Column(
            "entry_verification_id",
            sa.Integer(),
            sa.ForeignKey("entry_verifications.id"),
            nullable=True,
            index=True,
            comment="Related entry verification if applicable",
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=True,
            index=True,
            comment="Related student if applicable",
        ),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=True,
            index=True,
            comment="Related exam if applicable",
        ),
        sa.Column(
            "hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=True,
            index=True,
            comment="Related exam hall if applicable",
        ),
        sa.Column(
            "entry_point_id",
            sa.Integer(),
            sa.ForeignKey("entry_points.id"),
            nullable=True,
            comment="Related entry point if applicable",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Human-readable event description",
        ),
        sa.Column(
            "metadata_json",
            sa.Text(),
            nullable=True,
            comment="JSON-encoded structured evidence/context data",
        ),
        sa.Column(
            "source",
            sa.String(100),
            nullable=False,
            comment="Source that produced this event",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
            comment="When this event was created",
        ),
    )

    op.create_table(
        "security_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "security_event_id",
            sa.Integer(),
            sa.ForeignKey("security_events.id"),
            nullable=False,
            index=True,
            comment="Security event that triggered this alert",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="OPEN",
            index=True,
            comment="Alert lifecycle status",
        ),
        sa.Column(
            "severity",
            sa.String(50),
            nullable=False,
            index=True,
            comment="Alert severity",
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
            comment="Human-readable alert message",
        ),
        sa.Column(
            "assigned_to",
            sa.String(100),
            nullable=True,
            comment="Operator assigned to this alert",
        ),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the alert was acknowledged",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the alert was resolved",
        ),
        sa.Column(
            "resolution_notes",
            sa.Text(),
            nullable=True,
            comment="Notes from the operator on resolution",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
            comment="When the alert was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the alert was last updated",
        ),
    )


def downgrade() -> None:
    op.drop_table("security_alerts")
    op.drop_table("security_events")

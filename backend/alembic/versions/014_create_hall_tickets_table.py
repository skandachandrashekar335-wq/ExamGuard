"""create hall_tickets table

Revision ID: 014
Revises: 013
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hall_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exam_registration_id",
            sa.Integer(),
            sa.ForeignKey("exam_registrations.id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id"),
            nullable=True,
        ),
        sa.Column(
            "extraction_result_id",
            sa.Integer(),
            sa.ForeignKey("extraction_results.id"),
            nullable=True,
        ),
        sa.Column(
            "match_result_id",
            sa.Integer(),
            sa.ForeignKey("hall_ticket_match_results.id"),
            nullable=True,
        ),
        sa.Column(
            "verification_outcome_id",
            sa.Integer(),
            sa.ForeignKey("verification_outcomes.id"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "exam_registration_id",
            name="uq_hall_ticket_active_per_registration",
        ),
    )
    op.create_index(
        "ix_hall_tickets_exam_registration_id",
        "hall_tickets",
        ["exam_registration_id"],
    )
    op.create_index(
        "ix_hall_tickets_document_id",
        "hall_tickets",
        ["document_id"],
    )
    op.create_index(
        "ix_hall_tickets_extraction_result_id",
        "hall_tickets",
        ["extraction_result_id"],
    )
    op.create_index(
        "ix_hall_tickets_match_result_id",
        "hall_tickets",
        ["match_result_id"],
    )
    op.create_index(
        "ix_hall_tickets_verification_outcome_id",
        "hall_tickets",
        ["verification_outcome_id"],
    )
    op.create_index(
        "ix_hall_tickets_status",
        "hall_tickets",
        ["status"],
    )
    op.create_index(
        "ix_hall_tickets_created_at",
        "hall_tickets",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("hall_tickets")

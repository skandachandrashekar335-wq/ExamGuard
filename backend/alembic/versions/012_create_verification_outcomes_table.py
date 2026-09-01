"""create verification_outcomes table

Revision ID: 012
Revises: 011
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id"),
            nullable=False,
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
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=True,
        ),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=True,
        ),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("extraction_check", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("match_check", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("review_check", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("ocr_avg_confidence", sa.Float(), nullable=True),
        sa.Column("match_status", sa.String(50), nullable=True),
        sa.Column("review_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_verification_outcomes_document_id",
        "verification_outcomes",
        ["document_id"],
    )
    op.create_index(
        "ix_verification_outcomes_decision",
        "verification_outcomes",
        ["decision"],
    )
    op.create_index(
        "ix_verification_outcomes_student_id",
        "verification_outcomes",
        ["student_id"],
    )
    op.create_index(
        "ix_verification_outcomes_exam_id",
        "verification_outcomes",
        ["exam_id"],
    )
    op.create_index(
        "ix_verification_outcomes_extraction_result_id",
        "verification_outcomes",
        ["extraction_result_id"],
    )
    op.create_index(
        "ix_verification_outcomes_match_result_id",
        "verification_outcomes",
        ["match_result_id"],
    )


def downgrade() -> None:
    op.drop_table("verification_outcomes")

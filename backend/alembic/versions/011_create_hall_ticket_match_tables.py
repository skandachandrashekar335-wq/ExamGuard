"""create hall ticket match tables

Revision ID: 011
Revises: 010
Create Date: 2026-09-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hall_ticket_match_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "extraction_result_id",
            sa.Integer(),
            sa.ForeignKey("extraction_results.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "registration_id",
            sa.Integer(),
            sa.ForeignKey("exam_registrations.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "seat_assignment_id",
            sa.Integer(),
            sa.ForeignKey("seat_assignments.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "overall_status",
            sa.String(50),
            nullable=False,
            index=True,
        ),
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
    )

    op.create_table(
        "hall_ticket_match_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "match_result_id",
            sa.Integer(),
            sa.ForeignKey("hall_ticket_match_results.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("extracted_value", sa.String(500), nullable=True),
        sa.Column("expected_value", sa.String(500), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=False, default=False),
        sa.Column("signal_type", sa.String(100), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("hall_ticket_match_signals")
    op.drop_table("hall_ticket_match_results")

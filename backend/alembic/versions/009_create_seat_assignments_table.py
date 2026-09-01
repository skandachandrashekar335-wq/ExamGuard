"""create seat_assignments table

Revision ID: 009
Revises: 008
Create Date: 2026-09-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seat_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exam_registration_id",
            sa.Integer(),
            sa.ForeignKey("exam_registrations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "exam_hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("seat_number", sa.String(50), nullable=False),
        sa.Column(
            "row_number",
            sa.Integer(),
            nullable=True,
            comment="Seating row (optional)",
        ),
        sa.Column(
            "column_number",
            sa.Integer(),
            nullable=True,
            comment="Seating column (optional)",
        ),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="ASSIGNED",
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
        sa.UniqueConstraint(
            "exam_registration_id", "exam_hall_id",
            name="uq_active_assignment_per_registration",
        ),
    )
    op.create_index(
        "ix_seat_assignment_exam_hall_seat",
        "seat_assignments",
        ["exam_id", "exam_hall_id", "seat_number"],
        unique=True,
        postgresql_where=sa.text("status = 'ASSIGNED'"),
    )


def downgrade() -> None:
    op.drop_index("ix_seat_assignment_exam_hall_seat", table_name="seat_assignments")
    op.drop_table("seat_assignments")

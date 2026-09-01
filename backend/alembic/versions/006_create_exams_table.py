"""create exams table

Revision ID: 006
Revises: 005
Create Date: 2026-09-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "subject_id",
            sa.Integer(),
            sa.ForeignKey("subjects.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("exam_name", sa.String(255), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False, index=True),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False, index=True),
        sa.Column("department", sa.String(100), nullable=False, index=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
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
            "subject_id", "exam_date", "start_time",
            name="uq_exam_subject_date_start",
        ),
    )


def downgrade() -> None:
    op.drop_table("exams")

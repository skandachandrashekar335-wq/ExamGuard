"""add is_active column to students

Revision ID: 002
Revises: 001
Create Date: 2026-08-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
            comment="Soft-delete flag",
        ),
    )
    op.create_index(
        "ix_students_is_active",
        "students",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_students_is_active", table_name="students")
    op.drop_column("students", "is_active")

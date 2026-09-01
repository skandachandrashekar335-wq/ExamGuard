"""create exam_halls table

Revision ID: 007
Revises: 006
Create Date: 2026-09-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_halls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building", sa.String(100), nullable=False, index=True),
        sa.Column("room_number", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column(
            "rows",
            sa.Integer(),
            nullable=True,
            comment="Seating rows (optional)",
        ),
        sa.Column(
            "columns",
            sa.Integer(),
            nullable=True,
            comment="Seating columns (optional)",
        ),
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
            "building", "room_number",
            name="uq_hall_building_room",
        ),
    )


def downgrade() -> None:
    op.drop_table("exam_halls")

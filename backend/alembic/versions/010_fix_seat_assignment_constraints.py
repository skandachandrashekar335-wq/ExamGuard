"""fix seat assignment constraints

Revision ID: 010
Revises: 009
Create Date: 2026-09-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_active_assignment_per_registration",
        "seat_assignments",
        type_="unique",
    )
    op.create_index(
        "uq_one_active_assignment_per_registration",
        "seat_assignments",
        ["exam_registration_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ASSIGNED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_one_active_assignment_per_registration",
        table_name="seat_assignments",
    )
    op.create_unique_constraint(
        "uq_active_assignment_per_registration",
        "seat_assignments",
        ["exam_registration_id", "exam_hall_id"],
    )

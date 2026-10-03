"""Make attendance entry_verification_id nullable for manual review events

Manual review decisions (CHECK_IN / CHECK_OUT on an INCONCLUSIVE identity
attempt) are recorded as attendance events without an entry verification
trigger, so the FK must be nullable. Existing rows are unaffected.

Revision ID: 029
Revises: 028
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "attendance_events",
        "entry_verification_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "attendance_records",
        "entry_verification_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # Fails if any NULL rows exist (manual review events) — restore those
    # rows first before downgrading.
    op.alter_column(
        "attendance_records",
        "entry_verification_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "attendance_events",
        "entry_verification_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

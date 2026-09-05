"""Drop UNIQUE constraint on attendance_events.entry_verification_id

The UNIQUE constraint on entry_verification_id prevented creation of
correction events when an EV already had an auto-recorded event.
A manual correction should always produce its own auditable event.

Revision ID: 023
Revises: 022
Create Date: 2026-09-05
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_attendance_event_per_entry_verification",
        "attendance_events",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_attendance_event_per_entry_verification",
        "attendance_events",
        ["entry_verification_id"],
    )

"""add camera health fields

Revision ID: 017
Revises: 016
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When device was last observed responding",
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "last_health_check_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When health status was last evaluated",
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "health_reason",
            sa.String(50),
            nullable=True,
            comment="Reason for current status (DEVICE_RESPONDED, DEVICE_UNREACHABLE, etc.)",
        ),
    )


def downgrade() -> None:
    op.drop_column("cameras", "health_reason")
    op.drop_column("cameras", "last_health_check_at")
    op.drop_column("cameras", "last_seen_at")

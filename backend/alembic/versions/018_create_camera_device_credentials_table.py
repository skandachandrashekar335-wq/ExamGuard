"""Create camera device credentials table

Revision ID: 018
Revises: 017
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "camera_device_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "camera_id",
            sa.Integer(),
            sa.ForeignKey("cameras.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "label",
            sa.String(255),
            nullable=False,
            comment="Human-readable label for this credential",
        ),
        sa.Column(
            "secret_hash",
            sa.Text(),
            nullable=False,
            comment="SHA-256 hash of the device secret (never store plaintext)",
        ),
        sa.Column(
            "secret_prefix",
            sa.String(8),
            nullable=False,
            comment="First 8 chars of secret for identification (not the hash)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="ACTIVE",
            index=True,
            comment="Credential status (ACTIVE, REVOKED)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            index=True,
            comment="Soft-delete flag",
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


def downgrade() -> None:
    op.drop_table("camera_device_credentials")

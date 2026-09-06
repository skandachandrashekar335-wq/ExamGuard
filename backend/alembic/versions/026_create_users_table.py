"""Create users table for authentication

Revision ID: 026
Revises: 025
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "email",
            sa.String(255),
            unique=True,
            nullable=False,
            index=True,
            comment="User email address. Must be unique when provided.",
        ),
        sa.Column(
            "full_name",
            sa.String(255),
            nullable=True,
            comment="User's full name",
        ),
        sa.Column(
            "firebase_uid",
            sa.String(128),
            unique=True,
            nullable=True,
            index=True,
            comment="Firebase authentication UID. Unique when linked.",
        ),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            server_default="REVIEWER",
            comment="ExamGuard role: ADMIN, OPERATOR, or REVIEWER",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            index=True,
            comment="Soft-delete flag. Inactive users cannot authenticate.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            onupdate=sa.func.now(),
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of last successful login",
        ),
    )


def downgrade() -> None:
    op.drop_table("users")
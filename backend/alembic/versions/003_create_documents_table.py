"""create documents table

Revision ID: 003
Revises: 002
Create Date: 2026-09-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column(
            "stored_key",
            sa.String(512),
            nullable=False,
            unique=True,
            index=True,
            comment="Unique storage key",
        ),
        sa.Column("content_type", sa.String(127), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, comment="File size in bytes"),
        sa.Column(
            "document_type",
            sa.String(50),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(50),
            server_default="UPLOADED",
            nullable=False,
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
    )


def downgrade() -> None:
    op.drop_table("documents")

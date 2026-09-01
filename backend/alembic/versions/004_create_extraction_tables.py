"""create extraction_results and extracted_fields tables

Revision ID: 004
Revises: 003
Create Date: 2026-09-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extraction_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_engine", sa.String(50), nullable=False),
        sa.Column("ocr_avg_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="PENDING",
            index=True,
        ),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "extraction_result_id",
            sa.Integer(),
            sa.ForeignKey("extraction_results.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("extracted_value", sa.String(500), nullable=True),
        sa.Column("corrected_value", sa.String(500), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("pattern_match", sa.Boolean(), nullable=True),
        sa.Column("label_found", sa.Boolean(), nullable=True),
        sa.Column("database_match", sa.Boolean(), nullable=True),
        sa.Column("extraction_method", sa.String(100), nullable=True),
        sa.Column("validation_status", sa.String(50), nullable=False, server_default="UNCERTAIN"),
        sa.Column("review_status", sa.String(50), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("extracted_fields")
    op.drop_table("extraction_results")

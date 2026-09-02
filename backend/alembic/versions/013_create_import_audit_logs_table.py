"""create import_audit_logs table

Revision ID: 013
Revises: 012
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_type", sa.String(50), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="started",
        ),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "successful_rows", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "skipped_rows", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "failed_rows", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "actor",
            sa.String(100),
            nullable=True,
            comment="Future-compatible: will be populated when authentication is implemented",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_index(
        "ix_import_audit_logs_import_type",
        "import_audit_logs",
        ["import_type"],
    )
    op.create_index(
        "ix_import_audit_logs_status",
        "import_audit_logs",
        ["status"],
    )
    op.create_index(
        "ix_import_audit_logs_started_at",
        "import_audit_logs",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_table("import_audit_logs")

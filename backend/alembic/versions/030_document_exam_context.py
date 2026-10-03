"""Associate exam-specific uploaded documents with their selected exam.

Revision ID: 030
Revises: 029
"""

from alembic import op
import sqlalchemy as sa


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("exam_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_documents_exam_id_exams",
            "exams",
            ["exam_id"],
            ["id"],
        )
    op.create_index("ix_documents_exam_id", "documents", ["exam_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_exam_id", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_exam_id_exams", type_="foreignkey")
        batch.drop_column("exam_id")
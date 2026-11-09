"""Create chatbot tables for student admission guidance.

Revision ID: 031
Revises: 030
"""

from alembic import op
import sqlalchemy as sa


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("intent", sa.String(length=100), nullable=False),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("keywords", sa.Text(), server_default="", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("requires_admin_confirmation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("intent", name="uq_knowledge_base_items_intent"),
    )
    op.create_index("ix_knowledge_base_items_category", "knowledge_base_items", ["category"])
    op.create_index("ix_knowledge_base_items_intent", "knowledge_base_items", ["intent"])
    op.create_index("ix_knowledge_base_items_is_active", "knowledge_base_items", ["is_active"])

    op.create_table(
        "chat_query_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("query_text", sa.String(length=500), nullable=False),
        sa.Column("matched_intent", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_query_logs_session_id", "chat_query_logs", ["session_id"])
    op.create_index("ix_chat_query_logs_matched_intent", "chat_query_logs", ["matched_intent"])
    op.create_index("ix_chat_query_logs_category", "chat_query_logs", ["category"])


def downgrade() -> None:
    op.drop_index("ix_chat_query_logs_category", table_name="chat_query_logs")
    op.drop_index("ix_chat_query_logs_matched_intent", table_name="chat_query_logs")
    op.drop_index("ix_chat_query_logs_session_id", table_name="chat_query_logs")
    op.drop_table("chat_query_logs")

    op.drop_index("ix_knowledge_base_items_is_active", table_name="knowledge_base_items")
    op.drop_index("ix_knowledge_base_items_intent", table_name="knowledge_base_items")
    op.drop_index("ix_knowledge_base_items_category", table_name="knowledge_base_items")
    op.drop_table("knowledge_base_items")

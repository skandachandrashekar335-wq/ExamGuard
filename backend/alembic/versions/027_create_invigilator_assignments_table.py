"""Create invigilator_assignments table

Revision ID: 027
Revises: 026
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invigilator_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
            comment="User with INVIGILATOR role",
        ),
        sa.Column(
            "exam_id",
            sa.Integer(),
            sa.ForeignKey("exams.id"),
            nullable=False,
            index=True,
            comment="Examination this invigilator is assigned to",
        ),
        sa.Column(
            "exam_hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=False,
            index=True,
            comment="Exam hall this invigilator is responsible for",
        ),
        sa.Column(
            "entry_point_id",
            sa.Integer(),
            sa.ForeignKey("entry_points.id"),
            nullable=True,
            index=True,
            comment="Entry point this invigilator monitors (optional)",
        ),
        sa.Column(
            "camera_id",
            sa.Integer(),
            sa.ForeignKey("cameras.id"),
            nullable=True,
            index=True,
            comment="Camera assigned to this invigilator (optional)",
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
            "notes",
            sa.Text(),
            nullable=True,
            comment="Optional notes about this assignment",
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
    )

    # Unique constraint: one active assignment per user+exam+hall
    op.create_unique_constraint(
        "uq_invigilator_user_exam_hall",
        "invigilator_assignments",
        ["user_id", "exam_id", "exam_hall_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_invigilator_user_exam_hall", "invigilator_assignments", type_="unique")
    op.drop_table("invigilator_assignments")

"""create camera and entry point tables

Revision ID: 016
Revises: 015
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cameras
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable camera name",
        ),
        sa.Column(
            "device_identifier",
            sa.String(255),
            nullable=False,
            unique=True,
            index=True,
            comment="Unique device identifier (serial number, MAC, etc.)",
        ),
        sa.Column(
            "camera_type",
            sa.String(100),
            nullable=True,
            comment="Camera type/protocol (e.g. IP, USB, RTSP)",
        ),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column(
            "resolution_width",
            sa.Integer(),
            nullable=True,
            comment="Max resolution width in pixels",
        ),
        sa.Column(
            "resolution_height",
            sa.Integer(),
            nullable=True,
            comment="Max resolution height in pixels",
        ),
        sa.Column(
            "exam_hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=True,
            index=True,
            comment="Exam hall this camera is installed in",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="UNKNOWN",
            index=True,
            comment="Device operational status",
        ),
        sa.Column(
            "connection_info",
            sa.Text(),
            nullable=True,
            comment="Connection metadata (IP, endpoint URL) — no credentials",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            index=True,
            comment="Soft-delete flag. Inactive cameras are hidden from active operations.",
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

    # Entry points
    op.create_table(
        "entry_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable entry point name",
        ),
        sa.Column(
            "code",
            sa.String(50),
            nullable=False,
            unique=True,
            index=True,
            comment="Short unique code (e.g. MAIN_GATE, NORTH_ENTRY)",
        ),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "location_detail",
            sa.String(255),
            nullable=True,
            comment="Physical location detail (floor, wing, etc.)",
        ),
        sa.Column(
            "exam_hall_id",
            sa.Integer(),
            sa.ForeignKey("exam_halls.id"),
            nullable=True,
            index=True,
            comment="Exam hall this entry point serves",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            index=True,
            comment="Soft-delete flag. Inactive entry points are hidden from active operations.",
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

    # Camera ↔ Entry point mapping
    op.create_table(
        "camera_entry_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "camera_id",
            sa.Integer(),
            sa.ForeignKey("cameras.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "entry_point_id",
            sa.Integer(),
            sa.ForeignKey("entry_points.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether this mapping is currently active",
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
        sa.UniqueConstraint(
            "camera_id",
            "entry_point_id",
            name="uq_camera_entry_point",
        ),
    )


def downgrade() -> None:
    op.drop_table("camera_entry_points")
    op.drop_table("entry_points")
    op.drop_table("cameras")

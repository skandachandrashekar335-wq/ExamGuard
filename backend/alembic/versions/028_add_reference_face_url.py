"""Add reference_face_url to identity_verification_attempts

Revision ID: 028
Revises: 027
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "identity_verification_attempts",
        sa.Column(
            "reference_face_url",
            sa.String(500),
            nullable=True,
            comment="Cloudinary/public URL of the student's reference face image for comparison",
        ),
    )


def downgrade() -> None:
    op.drop_column("identity_verification_attempts", "reference_face_url")

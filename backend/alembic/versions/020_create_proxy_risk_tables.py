"""Create proxy risk tables

Revision ID: 020
Revises: 019
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "entry_verification_id",
            sa.Integer(),
            sa.ForeignKey("entry_verifications.id"),
            nullable=False,
            index=True,
            comment="Entry verification this signal was detected for",
        ),
        sa.Column(
            "signal_type",
            sa.String(50),
            nullable=False,
            index=True,
            comment="Type of security signal detected",
        ),
        sa.Column(
            "strength",
            sa.String(50),
            nullable=False,
            comment="Strength of this signal",
        ),
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            comment="Source that produced this signal",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Human-readable description of what was detected",
        ),
        sa.Column(
            "evidence_json",
            sa.Text(),
            nullable=True,
            comment="JSON-encoded structured evidence data",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
            comment="When this signal was detected",
        ),
    )

    op.create_table(
        "proxy_risk_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "entry_verification_id",
            sa.Integer(),
            sa.ForeignKey("entry_verifications.id"),
            nullable=False,
            index=True,
            comment="Entry verification this assessment is for",
        ),
        sa.Column(
            "risk_level",
            sa.String(50),
            nullable=False,
            index=True,
            comment="Classified risk level",
        ),
        sa.Column(
            "risk_score",
            sa.Float(),
            nullable=False,
            comment="Numeric risk score (0.0 - max_score)",
        ),
        sa.Column(
            "signals_summary_json",
            sa.Text(),
            nullable=True,
            comment="JSON summary of signals used in this assessment",
        ),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
            comment="When this assessment was performed",
        ),
        sa.Column(
            "policy_version",
            sa.String(50),
            nullable=True,
            comment="Version of risk scoring policy used",
        ),
    )


def downgrade() -> None:
    op.drop_table("proxy_risk_assessments")
    op.drop_table("security_signals")

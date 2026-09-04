"""Expand SecuritySignalType enum with signal detection types

Revision ID: 021
Revises: 020
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


# New enum values added for deterministic signal detection (Phase 11.2).
# SQLite stores String(50) — no ALTER TYPE needed. Column already accepts
# arbitrary strings. This migration exists for documentation and PostgreSQL
# compatibility where enum types may be used.
NEW_SIGNAL_TYPES = [
    "LIVENESS_SPOOF_DETECTED",
    "WRONG_HALL_DETECTED",
    "IDENTITY_INCONCLUSIVE",
    "DUPLICATE_ENTRY_SAME_EXAM",
    "REPEATED_FAILED_IDENTITY",
    "HALL_TICKET_FIELD_MISMATCH",
    "WRONG_ENTRY_POINT",
    "MISSING_IDENTITY_CHECK",
    "NO_SEAT_ASSIGNMENT",
    "NO_HALL_TICKET",
    "CAMERA_OFFLINE_AT_ENTRY",
    "LATE_ENTRY",
    "RAPID_SEQUENTIAL_ENTRY",
]


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

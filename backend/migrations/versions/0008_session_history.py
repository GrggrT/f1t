"""Add race_session_history table for sector times.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "race_session_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_index", sa.Integer(), nullable=False),
        sa.Column("best_lap_num", sa.Integer(), nullable=True),
        sa.Column("best_s1_lap", sa.Integer(), nullable=True),
        sa.Column("best_s2_lap", sa.Integer(), nullable=True),
        sa.Column("best_s3_lap", sa.Integer(), nullable=True),
        sa.Column("laps", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_race_session_history_race_vehicle",
        "race_session_history",
        ["race_id", "vehicle_index"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("race_session_history")

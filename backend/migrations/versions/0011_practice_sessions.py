"""Practice sessions for personal telemetry.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("web_user_id", sa.Integer, sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_id", sa.Integer, nullable=False),
        sa.Column("track_name", sa.String(100), nullable=True),
        sa.Column("session_type", sa.String(20), default="practice"),
        sa.Column("total_laps", sa.Integer, default=0),
        sa.Column("best_lap_ms", sa.Float, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_practice_sessions_user", "practice_sessions", ["web_user_id"])

    op.create_table(
        "practice_laps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lap_number", sa.Integer, nullable=False),
        sa.Column("lap_time_ms", sa.Float, nullable=True),
        sa.Column("sector1_ms", sa.Float, nullable=True),
        sa.Column("sector2_ms", sa.Float, nullable=True),
        sa.Column("sector3_ms", sa.Float, nullable=True),
        sa.Column("tyre_compound", sa.String(20), nullable=True),
        sa.Column("valid", sa.Boolean, default=True),
    )
    op.create_index("ix_practice_laps_session", "practice_laps", ["session_id"])


def downgrade():
    op.drop_table("practice_laps")
    op.drop_table("practice_sessions")

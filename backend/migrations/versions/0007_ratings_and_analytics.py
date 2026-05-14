"""Add player_ratings table and consistency_index to championship_standings.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Player ratings (Glicko-2)
    op.create_table(
        "player_ratings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Float, nullable=False, server_default="1500.0"),
        sa.Column("rd", sa.Float, nullable=False, server_default="350.0"),        # rating deviation
        sa.Column("volatility", sa.Float, nullable=False, server_default="0.06"),
        sa.Column("wins", sa.Integer, server_default="0"),
        sa.Column("losses", sa.Integer, server_default="0"),
        sa.Column("races_rated", sa.Integer, server_default="0"),
        sa.Column("peak_rating", sa.Float, server_default="1500.0"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_player_ratings_player_id", "player_ratings", ["player_id"], unique=True)
    op.create_index("ix_player_ratings_rating", "player_ratings", ["rating"])

    # Rating history for graphs
    op.create_table(
        "rating_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating_before", sa.Float, nullable=False),
        sa.Column("rating_after", sa.Float, nullable=False),
        sa.Column("rd_after", sa.Float, nullable=False),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rating_history_player", "rating_history", ["player_id"])

    # Add consistency_index to championship_standings
    op.add_column(
        "championship_standings",
        sa.Column("consistency_index", sa.Float, nullable=True),
    )
    op.add_column(
        "championship_standings",
        sa.Column("avg_grid_delta", sa.Float, nullable=True),
    )

    # Add position column to championship_standings (was calculated on the fly before)
    op.add_column(
        "championship_standings",
        sa.Column("position", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("championship_standings", "position")
    op.drop_column("championship_standings", "avg_grid_delta")
    op.drop_column("championship_standings", "consistency_index")
    op.drop_table("rating_history")
    op.drop_table("player_ratings")

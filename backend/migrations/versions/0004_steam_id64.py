"""add steam_id64 and steam_url to players

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("steam_id64", sa.String(20), nullable=True))
    op.add_column("players", sa.Column("steam_url",  sa.Text(),     nullable=True))
    op.create_unique_constraint("uq_players_steam_id64", "players", ["steam_id64"])


def downgrade() -> None:
    op.drop_constraint("uq_players_steam_id64", "players", type_="unique")
    op.drop_column("players", "steam_id64")
    op.drop_column("players", "steam_url")

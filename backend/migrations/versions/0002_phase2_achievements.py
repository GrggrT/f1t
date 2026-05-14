"""Phase 2 — achievements, penalty corrections

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("achievements",
        sa.Column("id",          sa.Integer(), primary_key=True),
        sa.Column("code",        sa.String(50), unique=True, nullable=False),
        sa.Column("name",        sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("icon",        sa.String(10)),
        sa.Column("phase",       sa.Integer(), server_default="2"),
    )

    op.create_table("player_achievements",
        sa.Column("id",             sa.Integer(), primary_key=True),
        sa.Column("player_id",      sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("achievement_id", sa.Integer(), sa.ForeignKey("achievements.id"), nullable=False),
        sa.Column("race_id",        sa.Integer(), sa.ForeignKey("races.id"), nullable=True),
        sa.Column("unlocked_at",    sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("context",        JSONB(), nullable=True),
        sa.UniqueConstraint("player_id", "achievement_id"),
    )

    op.create_index("ix_player_achievements_player", "player_achievements", ["player_id"])

    # penalty_corrections уже создана в 0001, пропускаем
    # Добавляем колонку season_id в race_results для быстрых запросов fun stats
    op.add_column("race_results",
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), nullable=True)
    )
    op.create_index("ix_race_results_season_id", "race_results", ["season_id"])


def downgrade() -> None:
    op.drop_index("ix_race_results_season_id")
    op.drop_column("race_results", "season_id")
    op.drop_index("ix_player_achievements_player")
    op.drop_table("player_achievements")
    op.drop_table("achievements")

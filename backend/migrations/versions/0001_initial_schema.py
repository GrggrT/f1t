"""Initial schema — Phase 1

Revision ID: 0001
Revises:
Create Date: 2026-03-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # players
    op.create_table("players",
        sa.Column("id",          sa.Integer(), primary_key=True),
        sa.Column("name",        sa.String(50), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("steam_names", ARRAY(sa.Text()), nullable=True),
        sa.Column("avatar_url",  sa.Text(), nullable=True),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # seasons
    op.create_table("seasons",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("name",          sa.String(50)),
        sa.Column("status",        sa.String(20), server_default="active"),
        sa.Column("calendar",      JSONB(), nullable=True),
        sa.Column("points_system", JSONB(), nullable=True),
        sa.Column("created_at",    sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # season_contracts
    op.create_table("season_contracts",
        sa.Column("id",          sa.Integer(), primary_key=True),
        sa.Column("season_id",   sa.Integer(), sa.ForeignKey("seasons.id")),
        sa.Column("player_id",   sa.Integer(), sa.ForeignKey("players.id")),
        sa.Column("driver_id",   sa.Integer(), nullable=False),
        sa.Column("driver_name", sa.String(50)),
        sa.Column("team_id",     sa.Integer(), nullable=False),
        sa.Column("team_name",   sa.String(50)),
        sa.UniqueConstraint("season_id", "player_id"),
    )

    # races
    op.create_table("races",
        sa.Column("id",             sa.Integer(), primary_key=True),
        sa.Column("season_id",      sa.Integer(), sa.ForeignKey("seasons.id")),
        sa.Column("round_number",   sa.Integer(), nullable=False),
        sa.Column("track_id",       sa.Integer(), nullable=False),
        sa.Column("track_name",     sa.String(50)),
        sa.Column("session_uid",    sa.BigInteger(), unique=True),
        sa.Column("packet_format",  sa.Integer(), server_default="2025"),
        sa.Column("weather_start",  sa.Integer(), nullable=True),
        sa.Column("weather_end",    sa.Integer(), nullable=True),
        sa.Column("total_laps",     sa.Integer(), nullable=True),
        sa.Column("air_temp",       sa.Integer(), nullable=True),
        sa.Column("track_temp",     sa.Integer(), nullable=True),
        sa.Column("host_player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("raced_at",       sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # race_results
    op.create_table("race_results",
        sa.Column("id",              sa.Integer(), primary_key=True),
        sa.Column("race_id",         sa.Integer(), sa.ForeignKey("races.id")),
        sa.Column("vehicle_index",   sa.Integer(), nullable=False),
        sa.Column("is_human",        sa.Boolean(), nullable=False),
        sa.Column("player_id",       sa.Integer(), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("driver_id",       sa.Integer(), nullable=False),
        sa.Column("driver_name",     sa.String(50)),
        sa.Column("team_id",         sa.Integer(), nullable=False),
        sa.Column("team_name",       sa.String(50)),
        sa.Column("grid_position",   sa.Integer(), nullable=True),
        sa.Column("position",        sa.Integer(), nullable=True),
        sa.Column("points",          sa.Float(), server_default="0"),
        sa.Column("result_status",   sa.Integer()),
        sa.Column("total_race_time", sa.Float(), nullable=True),
        sa.Column("best_lap_ms",     sa.Integer(), nullable=True),
        sa.Column("penalties_time",  sa.Integer(), nullable=True),
        sa.Column("num_penalties",   sa.Integer(), nullable=True),
        sa.Column("num_pit_stops",   sa.Integer(), nullable=True),
        sa.Column("num_tyre_stints", sa.Integer(), nullable=True),
        sa.Column("tyre_stints",     JSONB(), nullable=True),
        sa.Column("has_fastest_lap", sa.Boolean(), server_default="false"),
        sa.UniqueConstraint("race_id", "vehicle_index"),
    )

    # race_events
    op.create_table("race_events",
        sa.Column("id",           sa.Integer(), primary_key=True),
        sa.Column("race_id",      sa.Integer(), sa.ForeignKey("races.id")),
        sa.Column("event_code",   sa.String(4)),
        sa.Column("event_data",   JSONB()),
        sa.Column("lap_number",   sa.Integer(), nullable=True),
        sa.Column("session_time", sa.Float(), nullable=True),
    )

    # championship_standings
    op.create_table("championship_standings",
        sa.Column("season_id",    sa.Integer(), sa.ForeignKey("seasons.id"), primary_key=True),
        sa.Column("driver_id",    sa.Integer(), primary_key=True),
        sa.Column("driver_name",  sa.String(50)),
        sa.Column("player_id",    sa.Integer(), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("is_human",     sa.Boolean()),
        sa.Column("team_id",      sa.Integer()),
        sa.Column("team_name",    sa.String(50)),
        sa.Column("total_points", sa.Float(), server_default="0"),
        sa.Column("wins",         sa.Integer(), server_default="0"),
        sa.Column("podiums",      sa.Integer(), server_default="0"),
        sa.Column("fastest_laps", sa.Integer(), server_default="0"),
        sa.Column("dnfs",         sa.Integer(), server_default="0"),
        sa.Column("best_finish",  sa.Integer(), nullable=True),
    )

    # constructor_standings
    op.create_table("constructor_standings",
        sa.Column("season_id",     sa.Integer(), sa.ForeignKey("seasons.id"), primary_key=True),
        sa.Column("team_id",       sa.Integer(), primary_key=True),
        sa.Column("team_name",     sa.String(50)),
        sa.Column("total_points",  sa.Float(), server_default="0"),
        sa.Column("wins",          sa.Integer(), server_default="0"),
        sa.Column("driver_1_name", sa.String(50), nullable=True),
        sa.Column("driver_2_name", sa.String(50), nullable=True),
    )

    # penalty_corrections
    op.create_table("penalty_corrections",
        sa.Column("id",             sa.Integer(), primary_key=True),
        sa.Column("race_id",        sa.Integer(), sa.ForeignKey("races.id")),
        sa.Column("player_id",      sa.Integer(), sa.ForeignKey("players.id")),
        sa.Column("correction_sec", sa.Integer()),
        sa.Column("reason",         sa.Text()),
        sa.Column("applied_by",     sa.Integer(), sa.ForeignKey("players.id")),
        sa.Column("applied_at",     sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # Indexes
    op.create_index("ix_races_season_id",       "races",       ["season_id"])
    op.create_index("ix_race_results_race_id",  "race_results",["race_id"])
    op.create_index("ix_race_results_player_id","race_results",["player_id"])
    op.create_index("ix_race_events_race_id",   "race_events", ["race_id"])


def downgrade() -> None:
    op.drop_table("penalty_corrections")
    op.drop_table("constructor_standings")
    op.drop_table("championship_standings")
    op.drop_table("race_events")
    op.drop_table("race_results")
    op.drop_table("races")
    op.drop_table("season_contracts")
    op.drop_table("seasons")
    op.drop_table("players")

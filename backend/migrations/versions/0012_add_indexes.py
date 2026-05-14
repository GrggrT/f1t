"""Add performance indexes and unique constraint for lobby_members.

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _index_names(table_name: str) -> set[str]:
    return {item["name"] for item in _inspector().get_indexes(table_name)}


def _unique_constraint_names(table_name: str) -> set[str]:
    return {item["name"] for item in _inspector().get_unique_constraints(table_name)}


def _create_index_if_missing(name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=unique)


def _drop_index_if_exists(name: str, table_name: str) -> None:
    if name in _index_names(table_name):
        op.drop_index(name, table_name=table_name)


def _create_lobby_member_uniqueness_if_missing() -> None:
    constraint_names = _unique_constraint_names("lobby_members")
    index_names = _index_names("lobby_members")
    if "uq_lobby_member" in constraint_names or "ix_lobby_members_unique" in index_names:
        return
    op.create_unique_constraint("uq_lobby_member", "lobby_members", ["lobby_id", "web_user_id"])


def _drop_lobby_member_uniqueness_if_exists() -> None:
    if "uq_lobby_member" in _unique_constraint_names("lobby_members"):
        op.drop_constraint("uq_lobby_member", "lobby_members", type_="unique")


def upgrade() -> None:
    _create_lobby_member_uniqueness_if_missing()
    _create_index_if_missing("ix_lobby_members_web_user_id", "lobby_members", ["web_user_id"])
    _create_index_if_missing("ix_seasons_lobby_id", "seasons", ["lobby_id"])
    _create_index_if_missing("ix_race_results_season_id", "race_results", ["season_id"])
    _create_index_if_missing("ix_race_results_player_id", "race_results", ["player_id"])
    _create_index_if_missing("ix_race_results_race_id", "race_results", ["race_id"])
    _create_index_if_missing("ix_championship_standings_player_id", "championship_standings", ["player_id"])


def downgrade() -> None:
    _drop_index_if_exists("ix_championship_standings_player_id", "championship_standings")
    _drop_index_if_exists("ix_race_results_race_id", "race_results")
    _drop_index_if_exists("ix_race_results_player_id", "race_results")
    _drop_index_if_exists("ix_race_results_season_id", "race_results")
    _drop_index_if_exists("ix_seasons_lobby_id", "seasons")
    _drop_index_if_exists("ix_lobby_members_web_user_id", "lobby_members")
    _drop_lobby_member_uniqueness_if_exists()

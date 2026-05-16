"""Sprint 2 / PR 2.5 — drop legacy FK columns on dependent tables.

After this migration the application code talks to the new `user_id`
(and `creator_user_id` / `granted_by_user_id` / `applied_by_user_id`)
columns exclusively. The per-table BEFORE INSERT/UPDATE triggers
created in 0015 are no longer needed and are dropped here.

We do NOT drop the legacy tables (`web_users`, `players`,
`season_moderators`) in this migration — that happens in 0017 along
with the dual-write trigger functions from 0014.

Revision ID: 0016
Revises: 0015
"""
from alembic import op


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


# (table, legacy_col, new_col)
# Mirror of 0015._TABLES — keep in sync.
_TABLES = [
    ("lobbies",                "creator_id",  "creator_user_id"),
    ("lobby_members",          "web_user_id", "user_id"),
    ("seasons",                "creator_id",  "creator_user_id"),
    ("season_moderators",      "web_user_id", "user_id"),
    ("season_moderators",      "granted_by",  "granted_by_user_id"),
    ("practice_sessions",      "web_user_id", "user_id"),
    ("race_results",           "player_id",   "user_id"),
    ("championship_standings", "player_id",   "user_id"),
    ("player_ratings",         "player_id",   "user_id"),
    ("rating_history",         "player_id",   "user_id"),
    ("player_achievements",    "player_id",   "user_id"),
    ("penalty_corrections",    "player_id",   "user_id"),
    ("penalty_corrections",    "applied_by",  "applied_by_user_id"),
    ("season_contracts",       "player_id",   "user_id"),
]


def _trg_name(table: str, new_col: str) -> str:
    return f"trg_{table}_{new_col}_from_legacy"


def _fn_name(table: str, new_col: str) -> str:
    return f"sync_{table}_{new_col}_from_legacy"


def upgrade() -> None:
    # 1. Drop the BEFORE INSERT/UPDATE triggers + functions from 0015.
    for table, _legacy_col, new_col in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {_trg_name(table, new_col)} ON {table};")
        op.execute(f"DROP FUNCTION IF EXISTS {_fn_name(table, new_col)}();")

    # 2. Drop legacy FK columns. We use raw SQL with CASCADE for the FK + index
    # so we don't have to remember every index/constraint name.
    for table, legacy_col, _new_col in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {legacy_col} CASCADE;")

    # 3. races.host_player_id was dead before Sprint 2; drop it now to clear the
    # last FK pointing at the soon-to-be-gone `players` table.
    op.execute("ALTER TABLE races DROP COLUMN IF EXISTS host_player_id CASCADE;")


def downgrade() -> None:
    # PR 2.5 is destructive by design. Use the pre-PR2.5 backup
    # (backups/pre-sprint-2-final-*.pgc) to restore if needed.
    raise NotImplementedError(
        "Sprint 2 PR 2.5 cannot be downgraded with Alembic. "
        "Restore from the pre-PR2.5 pg_dump backup instead."
    )

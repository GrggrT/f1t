"""Sprint 2 / PR 2.2 — add user_id columns to all dependent tables + backfill + sync triggers.

Revision ID: 0015
Revises: 0014

Every table that holds a FK on web_users or players gets a parallel
`user_id` column (or `creator_user_id` / `granted_by_user_id` /
`applied_by_user_id` where the original was named differently).

For each dependent table:
  1. ADD COLUMN user_id (nullable initially).
  2. Backfill via JOIN users.legacy_web_user_id / legacy_player_id.
  3. NOT NULL where the legacy column was NOT NULL.
  4. FK to users.id (with the same ondelete behaviour).
  5. BEFORE INSERT/UPDATE trigger that auto-populates user_id from the
     legacy column — so application code can keep writing only the legacy
     column and user_id stays consistent without dual-write in every
     INSERT site. (PR 2.5 will drop the legacy columns and triggers.)

Dead column carried forward:
  races.host_player_id stays — never used in production paths and gets
  dropped in PR 2.5 alongside the rest of the legacy cleanup.
"""
from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


# (table, legacy_col, new_col, ondelete, legacy_kind, not_null)
# legacy_kind: 'web' → users.legacy_web_user_id;  'player' → users.legacy_player_id
_TABLES = [
    ("lobbies",                "creator_id",  "creator_user_id",      None,       "web",    True),
    ("lobby_members",          "web_user_id", "user_id",              "CASCADE",  "web",    True),
    ("seasons",                "creator_id",  "creator_user_id",      None,       "web",    False),
    ("season_moderators",      "web_user_id", "user_id",              "CASCADE",  "web",    True),
    ("season_moderators",      "granted_by",  "granted_by_user_id",   "SET NULL", "web",    False),
    ("practice_sessions",      "web_user_id", "user_id",              "CASCADE",  "web",    True),
    ("race_results",           "player_id",   "user_id",              None,       "player", False),
    ("championship_standings", "player_id",   "user_id",              None,       "player", False),
    ("player_ratings",         "player_id",   "user_id",              "CASCADE",  "player", True),
    ("rating_history",         "player_id",   "user_id",              "CASCADE",  "player", True),
    ("player_achievements",    "player_id",   "user_id",              None,       "player", True),
    ("penalty_corrections",    "player_id",   "user_id",              None,       "player", False),
    ("penalty_corrections",    "applied_by",  "applied_by_user_id",   None,       "player", False),
    ("season_contracts",       "player_id",   "user_id",              None,       "player", True),
]


def _fk_name(table: str, new_col: str) -> str:
    return f"fk_{table}_{new_col}_users"


def _ix_name(table: str, new_col: str) -> str:
    return f"ix_{table}_{new_col}"


def _trg_name(table: str, new_col: str) -> str:
    return f"trg_{table}_{new_col}_from_legacy"


def _fn_name(table: str, new_col: str) -> str:
    return f"sync_{table}_{new_col}_from_legacy"


def upgrade() -> None:
    for table, legacy_col, new_col, ondelete, _kind, _not_null in _TABLES:
        op.add_column(table, sa.Column(new_col, sa.Integer(), nullable=True))

    # Backfill from users via legacy_*_id tracking columns.
    for table, legacy_col, new_col, _ondelete, kind, _not_null in _TABLES:
        legacy_users_col = "legacy_web_user_id" if kind == "web" else "legacy_player_id"
        op.execute(
            f"""
            UPDATE {table} t
            SET {new_col} = u.id
            FROM users u
            WHERE u.{legacy_users_col} = t.{legacy_col}
              AND t.{legacy_col} IS NOT NULL
            """
        )

    # Make non-null where the legacy column was non-null.
    for table, legacy_col, new_col, _ondelete, _kind, not_null in _TABLES:
        if not_null:
            op.alter_column(table, new_col, nullable=False)

    # FK + index on every new column.
    for table, _legacy_col, new_col, ondelete, _kind, _not_null in _TABLES:
        op.create_foreign_key(
            _fk_name(table, new_col),
            table,
            "users",
            [new_col],
            ["id"],
            ondelete=ondelete,
        )
        op.create_index(_ix_name(table, new_col), table, [new_col])

    # player_ratings.user_id mirrors the UNIQUE on player_id (one rating per user).
    op.create_unique_constraint(
        "uq_player_ratings_user_id", "player_ratings", ["user_id"]
    )

    # Trigger functions + BEFORE INSERT/UPDATE triggers. Each table-column
    # pair gets its own pair so the trigger body knows exactly which legacy
    # column to read.
    for table, legacy_col, new_col, _ondelete, kind, _not_null in _TABLES:
        users_lookup_col = "legacy_web_user_id" if kind == "web" else "legacy_player_id"
        fn = _fn_name(table, new_col)
        trg = _trg_name(table, new_col)
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {fn}()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.{legacy_col} IS NOT NULL THEN
                    NEW.{new_col} := (
                        SELECT id FROM users WHERE {users_lookup_col} = NEW.{legacy_col}
                    );
                ELSE
                    NEW.{new_col} := NULL;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS {trg} ON {table};
            CREATE TRIGGER {trg}
            BEFORE INSERT OR UPDATE OF {legacy_col} ON {table}
            FOR EACH ROW EXECUTE FUNCTION {fn}();
            """
        )


def downgrade() -> None:
    for table, legacy_col, new_col, _ondelete, _kind, _not_null in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {_trg_name(table, new_col)} ON {table};")
        op.execute(f"DROP FUNCTION IF EXISTS {_fn_name(table, new_col)}();")

    op.drop_constraint("uq_player_ratings_user_id", "player_ratings", type_="unique")

    for table, _legacy_col, new_col, _ondelete, _kind, _not_null in _TABLES:
        op.drop_index(_ix_name(table, new_col), table_name=table)
        op.drop_constraint(_fk_name(table, new_col), table, type_="foreignkey")
        op.drop_column(table, new_col)

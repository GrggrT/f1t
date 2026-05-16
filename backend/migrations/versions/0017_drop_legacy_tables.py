"""Sprint 2 / PR 2.5 — drop legacy identity tables + dual-write trigger.

After this migration the unified `users` table is the single source of
truth. The legacy `web_users`, `players`, and `season_moderators`
tables are gone, along with the dual-write trigger from 0014.

`legacy_web_user_id` / `legacy_player_id` columns on `users` survive
this migration as audit metadata; they will be dropped in a future
cosmetic migration once we are confident no rollback path is needed.

Revision ID: 0017
Revises: 0016
"""
from alembic import op


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the dual-write triggers created in 0014.
    op.execute("DROP TRIGGER IF EXISTS trg_sync_web_user_to_users ON web_users;")
    op.execute("DROP TRIGGER IF EXISTS trg_sync_player_to_users  ON players;")
    op.execute("DROP FUNCTION IF EXISTS sync_web_user_to_users();")
    op.execute("DROP FUNCTION IF EXISTS sync_player_to_users();")

    # 2. Drop the legacy tables. CASCADE handles any stray FKs we might have
    # missed in PR 2.2/2.5.
    op.execute("DROP TABLE IF EXISTS season_moderators CASCADE;")
    op.execute("DROP TABLE IF EXISTS web_users         CASCADE;")
    op.execute("DROP TABLE IF EXISTS players           CASCADE;")


def downgrade() -> None:
    raise NotImplementedError(
        "Sprint 2 PR 2.5 cannot be downgraded with Alembic. "
        "Restore from the pre-PR2.5 pg_dump backup instead."
    )

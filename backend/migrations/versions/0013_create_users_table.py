"""Sprint 2 / PR 2.1 — create `users` table + backfill from web_users + players.

Revision ID: 0013
Revises: 0012

Adds the unified `users` table per Sprint 2 spec.

Conflict resolution (in backfill SQL):
    name        = COALESCE(player.name, web_user.name)
    avatar_url  = COALESCE(player.avatar_url, web_user.picture)
    steam_id64  = COALESCE(player.steam_id64, web_user.steam_id64)

Backfill is split into three INSERT statements:
    1. linked pairs (web_user.player_id IS NOT NULL)
    2. web-only (web_user with no Player)
    3. player-only (Player created via bot, no WebUser)

Tracking columns `legacy_web_user_id` and `legacy_player_id` carry the source
ids forward. They are sacred during Sprint 2 — the dual-write trigger from
0014, the read-switch in PR 2.2, and the rollback paths in PR 2.5 all rely
on them.

Pre-condition: `scripts/analyze_user_player_merge.py` returned "OK: no
blocking conflicts" — otherwise this migration will fail on the unique
constraint for legacy_player_id (multiple web_users pointing at the same
player would map to the same legacy_player_id).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column("google_id", sa.String(100), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("steam_id64", sa.String(20), nullable=True),
        sa.Column("steam_names", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("steam_url", sa.Text(), nullable=True),
        sa.Column(
            "is_system_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("legacy_web_user_id", sa.Integer(), nullable=True),
        sa.Column("legacy_player_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("google_id", name="uq_users_google_id"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
        sa.UniqueConstraint("steam_id64", name="uq_users_steam_id64"),
        sa.UniqueConstraint("legacy_web_user_id", name="uq_users_legacy_web_user_id"),
        sa.UniqueConstraint("legacy_player_id", name="uq_users_legacy_player_id"),
    )

    # Case 1: linked pairs — web_user JOIN player on web_user.player_id
    op.execute(
        """
        INSERT INTO users (
            email, hashed_password, google_id, name, avatar_url,
            telegram_id, steam_id64, steam_names, steam_url,
            is_system_admin, legacy_web_user_id, legacy_player_id, created_at
        )
        SELECT
            w.email,
            w.hashed_password,
            w.google_id,
            COALESCE(p.name, w.name),
            COALESCE(p.avatar_url, w.picture),
            p.telegram_id,
            COALESCE(p.steam_id64, w.steam_id64),
            p.steam_names,
            p.steam_url,
            w.is_system_admin,
            w.id,
            p.id,
            COALESCE(w.created_at, p.created_at, now())
        FROM web_users w
        INNER JOIN players p ON w.player_id = p.id
        """
    )

    # Case 2: web-only — web_user with no Player record
    op.execute(
        """
        INSERT INTO users (
            email, hashed_password, google_id, name, avatar_url,
            steam_id64, is_system_admin, legacy_web_user_id, created_at
        )
        SELECT
            w.email, w.hashed_password, w.google_id, w.name, w.picture,
            w.steam_id64, w.is_system_admin, w.id,
            COALESCE(w.created_at, now())
        FROM web_users w
        WHERE w.player_id IS NULL
        """
    )

    # Case 3: player-only — Player rows without any linked WebUser
    op.execute(
        """
        INSERT INTO users (
            name, avatar_url, telegram_id, steam_id64, steam_names, steam_url,
            is_system_admin, legacy_player_id, created_at
        )
        SELECT
            p.name, p.avatar_url, p.telegram_id, p.steam_id64,
            p.steam_names, p.steam_url, false, p.id,
            COALESCE(p.created_at, now())
        FROM players p
        WHERE p.id NOT IN (
            SELECT player_id FROM web_users WHERE player_id IS NOT NULL
        )
        """
    )

    # Indexes for the most common lookups (uniqueness above already creates
    # implicit indexes for those columns; these add coverage for non-unique
    # access patterns like prefix scans on `name`).
    op.create_index("ix_users_name", "users", ["name"])


def downgrade() -> None:
    op.drop_index("ix_users_name", table_name="users")
    op.drop_table("users")

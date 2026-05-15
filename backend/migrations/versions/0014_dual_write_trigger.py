"""Sprint 2 / PR 2.1 — dual-write triggers from legacy tables into `users`.

Revision ID: 0014
Revises: 0013

During Sprint 2 (PRs 2.1 → 2.5) application code keeps writing to
`web_users` and `players`; these triggers mirror every change into
`users` so reads can switch over in PR 2.2 without code changes here.

Conflict resolution mirrors 0013:
    name        = COALESCE(player.name, web_user.name)
    avatar_url  = COALESCE(player.avatar_url, web_user.picture)
    steam_id64  = COALESCE(player.steam_id64, web_user.steam_id64)

Subtle case the trigger has to handle (caught in PR 2.1 review):
    1. INSERT INTO players (id=5)   → trigger creates users row A
                                       with legacy_player_id=5,
                                       legacy_web_user_id=NULL.
    2. INSERT INTO web_users (player_id=5)
                                    → trigger MUST find row A and UPDATE
                                      it with email/google_id/legacy_web_user_id,
                                      not INSERT a duplicate row.

Same logic in reverse for web_user-first-then-player. Naive trigger that
just does INSERT ... ON CONFLICT (legacy_web_user_id) DO UPDATE would
fail on the unique(legacy_player_id) constraint when the player row
already created a users entry.
"""
from alembic import op


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------- web_users
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_web_user_to_users()
        RETURNS TRIGGER AS $$
        DECLARE
            web_user_row_id   INTEGER;  -- existing users row with legacy_web_user_id = NEW.id
            player_row_id     INTEGER;  -- existing users row with legacy_player_id = NEW.player_id
            player_row        players%ROWTYPE;
        BEGIN
            -- Pull the Player row (if linked) so COALESCE rules from 0013 apply.
            IF NEW.player_id IS NOT NULL THEN
                SELECT * INTO player_row FROM players WHERE id = NEW.player_id;
                SELECT id INTO player_row_id
                FROM users WHERE legacy_player_id = NEW.player_id LIMIT 1;
            END IF;

            SELECT id INTO web_user_row_id
            FROM users WHERE legacy_web_user_id = NEW.id LIMIT 1;

            -- Case A: a users row already mirrors this web_user. The web_user
            -- may have just been re-linked to a different player. If a
            -- player-side users row exists distinct from ours, merge them
            -- (drop the player-side, fold its identity into ours) so we don't
            -- collide on unique(legacy_player_id).
            IF web_user_row_id IS NOT NULL THEN
                IF player_row_id IS NOT NULL AND player_row_id <> web_user_row_id THEN
                    DELETE FROM users WHERE id = player_row_id;
                END IF;
                UPDATE users SET
                    email             = NEW.email,
                    hashed_password   = NEW.hashed_password,
                    google_id         = NEW.google_id,
                    name              = COALESCE(player_row.name, NEW.name, name),
                    avatar_url        = COALESCE(player_row.avatar_url, NEW.picture, avatar_url),
                    telegram_id       = COALESCE(player_row.telegram_id, telegram_id),
                    steam_id64        = COALESCE(player_row.steam_id64, NEW.steam_id64, steam_id64),
                    steam_names       = COALESCE(player_row.steam_names, steam_names),
                    steam_url         = COALESCE(player_row.steam_url, steam_url),
                    is_system_admin   = NEW.is_system_admin,
                    legacy_player_id  = NEW.player_id
                WHERE id = web_user_row_id;
                RETURN NEW;
            END IF;

            -- Case B: no web-side users row yet, but a player-side one exists.
            -- Augment it with the web_user fields (link the two identities).
            IF player_row_id IS NOT NULL THEN
                UPDATE users SET
                    email             = NEW.email,
                    hashed_password   = NEW.hashed_password,
                    google_id         = NEW.google_id,
                    name              = COALESCE(player_row.name, NEW.name, name),
                    avatar_url        = COALESCE(player_row.avatar_url, NEW.picture, avatar_url),
                    steam_id64        = COALESCE(player_row.steam_id64, NEW.steam_id64, steam_id64),
                    is_system_admin   = NEW.is_system_admin,
                    legacy_web_user_id = NEW.id
                WHERE id = player_row_id;
                RETURN NEW;
            END IF;

            -- Case C: neither side has a users row yet. Standalone INSERT.
            INSERT INTO users (
                email, hashed_password, google_id, name, avatar_url,
                telegram_id, steam_id64, steam_names, steam_url,
                is_system_admin, legacy_web_user_id, legacy_player_id
            ) VALUES (
                NEW.email,
                NEW.hashed_password,
                NEW.google_id,
                COALESCE(player_row.name, NEW.name),
                COALESCE(player_row.avatar_url, NEW.picture),
                player_row.telegram_id,
                COALESCE(player_row.steam_id64, NEW.steam_id64),
                player_row.steam_names,
                player_row.steam_url,
                NEW.is_system_admin,
                NEW.id,
                NEW.player_id
            );

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_sync_web_user_to_users ON web_users;
        CREATE TRIGGER trg_sync_web_user_to_users
        AFTER INSERT OR UPDATE ON web_users
        FOR EACH ROW EXECUTE FUNCTION sync_web_user_to_users();
        """
    )

    # ----------------------------------------------------------------- players
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_player_to_users()
        RETURNS TRIGGER AS $$
        DECLARE
            existing_user_id INTEGER;
            linked_web_user web_users%ROWTYPE;
        BEGIN
            -- Step 1: is there a web_user pointing at this Player? If so,
            -- and a users row already exists for that web_user, update it
            -- in place rather than inserting a new (legacy_player_id) row.
            SELECT * INTO linked_web_user FROM web_users WHERE player_id = NEW.id LIMIT 1;

            IF linked_web_user.id IS NOT NULL THEN
                SELECT id INTO existing_user_id
                FROM users
                WHERE legacy_web_user_id = linked_web_user.id
                LIMIT 1;
            END IF;

            IF existing_user_id IS NOT NULL THEN
                UPDATE users SET
                    name             = COALESCE(NEW.name, name),
                    avatar_url       = COALESCE(NEW.avatar_url, avatar_url),
                    telegram_id      = NEW.telegram_id,
                    steam_id64       = COALESCE(NEW.steam_id64, steam_id64),
                    steam_names      = NEW.steam_names,
                    steam_url        = NEW.steam_url,
                    legacy_player_id = NEW.id
                WHERE id = existing_user_id;
                RETURN NEW;
            END IF;

            -- Step 2: no web-user side. Insert standalone users row, or
            -- update in place if this player_id was already mirrored.
            INSERT INTO users (
                name, avatar_url, telegram_id, steam_id64,
                steam_names, steam_url, is_system_admin, legacy_player_id
            ) VALUES (
                NEW.name,
                NEW.avatar_url,
                NEW.telegram_id,
                NEW.steam_id64,
                NEW.steam_names,
                NEW.steam_url,
                false,
                NEW.id
            )
            ON CONFLICT (legacy_player_id) DO UPDATE SET
                name        = COALESCE(EXCLUDED.name, users.name),
                avatar_url  = COALESCE(EXCLUDED.avatar_url, users.avatar_url),
                telegram_id = EXCLUDED.telegram_id,
                steam_id64  = COALESCE(EXCLUDED.steam_id64, users.steam_id64),
                steam_names = EXCLUDED.steam_names,
                steam_url   = EXCLUDED.steam_url;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_player_to_users
        AFTER INSERT OR UPDATE ON players
        FOR EACH ROW EXECUTE FUNCTION sync_player_to_users();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_web_user_to_users ON web_users;")
    op.execute("DROP TRIGGER IF EXISTS trg_sync_player_to_users ON players;")
    op.execute("DROP FUNCTION IF EXISTS sync_web_user_to_users();")
    op.execute("DROP FUNCTION IF EXISTS sync_player_to_users();")

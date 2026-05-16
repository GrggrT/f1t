"""Sprint 2 / PR 2.1 — schema + backfill + dual-write trigger tests.

These exercised the migration's contract while `web_users` and `players`
still existed alongside `users` and were kept in sync by triggers from
migrations 0013/0014. **PR 2.5 dropped both legacy tables and the
dual-write triggers** (migrations 0016/0017), so every test in this file
is now historic — they reference SQL objects that no longer exist.

The file is kept (rather than deleted) so the Sprint 2 spec checklist
remains greppable; the entire class is skipped at collection time.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tests.backend_integration_support import BackendIntegrationCase


@pytest.mark.skip(reason="PR 2.5 dropped web_users/players and the dual-write triggers these tests probe.")
class UserUnificationSchemaTests(BackendIntegrationCase):
    """Each test creates an isolated dataset inside the harness DB.

    The harness creates a fresh schema before the class, so we can rely on
    INSERTing into web_users/players directly and observing the trigger
    side-effects in users.
    """

    def _async(self, coro):
        return asyncio.run(coro)

    def _engine(self):
        return create_async_engine(self.harness.database_url, echo=False, future=True)

    def test_linked_pair_has_both_legacy_ids_and_player_wins_on_name(self):
        async def run():
            engine = self._engine()
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                async with sm() as s:
                    nonce = uuid.uuid4().hex[:6]
                    await s.execute(text(
                        "INSERT INTO players (name, telegram_id, steam_id64, avatar_url) "
                        f"VALUES ('player-{nonce}', 9990001, 'steam-{nonce}', 'http://p/avatar.png') "
                        "RETURNING id"
                    ))
                    p_id = (await s.execute(text(
                        f"SELECT id FROM players WHERE name = 'player-{nonce}'"
                    ))).scalar_one()
                    await s.execute(text(
                        "INSERT INTO web_users (email, name, hashed_password, picture, player_id) "
                        f"VALUES ('linked-{nonce}@example.com', 'web-name-{nonce}', "
                        f"        'x', 'http://w/pic.png', {p_id})"
                    ))
                    await s.commit()

                    row = (await s.execute(text(
                        "SELECT name, avatar_url, telegram_id, steam_id64, "
                        "       legacy_web_user_id, legacy_player_id "
                        f"FROM users WHERE legacy_player_id = {p_id}"
                    ))).one()

                name, avatar, tg, steam, legacy_w, legacy_p = row
                self.assertEqual(name, f"player-{nonce}", "Player.name must win over WebUser.name")
                self.assertEqual(avatar, "http://p/avatar.png")
                self.assertEqual(tg, 9990001)
                self.assertEqual(steam, f"steam-{nonce}")
                self.assertEqual(legacy_p, p_id)
                self.assertIsNotNone(legacy_w)
            finally:
                await engine.dispose()
        self._async(run())

    def test_web_only_user_has_no_telegram_no_legacy_player_id(self):
        async def run():
            engine = self._engine()
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                async with sm() as s:
                    nonce = uuid.uuid4().hex[:6]
                    await s.execute(text(
                        "INSERT INTO web_users (email, name, hashed_password) "
                        f"VALUES ('webonly-{nonce}@example.com', 'web-only-{nonce}', 'x')"
                    ))
                    await s.commit()

                    row = (await s.execute(text(
                        f"SELECT name, telegram_id, legacy_web_user_id, legacy_player_id "
                        f"FROM users WHERE email = 'webonly-{nonce}@example.com'"
                    ))).one()

                name, tg, legacy_w, legacy_p = row
                self.assertEqual(name, f"web-only-{nonce}")
                self.assertIsNone(tg)
                self.assertIsNotNone(legacy_w)
                self.assertIsNone(legacy_p)
            finally:
                await engine.dispose()
        self._async(run())

    def test_player_only_user_has_no_email_and_no_legacy_web_user_id(self):
        async def run():
            engine = self._engine()
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                async with sm() as s:
                    nonce = uuid.uuid4().hex[:6]
                    await s.execute(text(
                        "INSERT INTO players (name, telegram_id, steam_id64) "
                        f"VALUES ('only-player-{nonce}', 9990002, 'steam-only-{nonce}')"
                    ))
                    await s.commit()

                    row = (await s.execute(text(
                        "SELECT name, email, telegram_id, "
                        "       legacy_web_user_id, legacy_player_id "
                        f"FROM users WHERE telegram_id = 9990002"
                    ))).one()

                name, email, tg, legacy_w, legacy_p = row
                self.assertEqual(name, f"only-player-{nonce}")
                self.assertIsNone(email)
                self.assertEqual(tg, 9990002)
                self.assertIsNone(legacy_w)
                self.assertIsNotNone(legacy_p)
            finally:
                await engine.dispose()
        self._async(run())

    def test_update_player_name_propagates_to_users(self):
        async def run():
            engine = self._engine()
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                async with sm() as s:
                    nonce = uuid.uuid4().hex[:6]
                    await s.execute(text(
                        "INSERT INTO players (name, telegram_id) "
                        f"VALUES ('rename-me-{nonce}', 9990003)"
                    ))
                    await s.execute(text(
                        f"UPDATE players SET name = 'renamed-{nonce}' "
                        f"WHERE telegram_id = 9990003"
                    ))
                    await s.commit()

                    name = (await s.execute(text(
                        "SELECT name FROM users WHERE telegram_id = 9990003"
                    ))).scalar_one()

                self.assertEqual(name, f"renamed-{nonce}")
            finally:
                await engine.dispose()
        self._async(run())

    def test_player_first_then_linked_web_user_does_not_duplicate_or_conflict(self):
        """Regression for the trigger bug flagged during PR 2.1 review:

        INSERT player → trigger creates users row (legacy_player_id set,
        legacy_web_user_id NULL). Then INSERT web_user with player_id pointing
        at that same player. The naive trigger would try INSERT a second row
        with the same legacy_player_id and fail on the unique constraint;
        the fixed trigger detects the existing row and UPDATEs it in place.
        """
        async def run():
            engine = self._engine()
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                async with sm() as s:
                    nonce = uuid.uuid4().hex[:6]
                    await s.execute(text(
                        "INSERT INTO players (name, telegram_id) "
                        f"VALUES ('first-player-{nonce}', 9990004)"
                    ))
                    p_id = (await s.execute(text(
                        f"SELECT id FROM players WHERE telegram_id = 9990004"
                    ))).scalar_one()

                    # This INSERT must NOT raise UniqueViolation.
                    await s.execute(text(
                        "INSERT INTO web_users (email, name, hashed_password, player_id) "
                        f"VALUES ('first-linked-{nonce}@example.com', 'web-name-{nonce}', "
                        f"        'x', {p_id})"
                    ))
                    await s.commit()

                    rows = (await s.execute(text(
                        "SELECT email, name, telegram_id, legacy_web_user_id, legacy_player_id "
                        f"FROM users WHERE legacy_player_id = {p_id}"
                    ))).all()

                self.assertEqual(len(rows), 1, "should be a single merged row, not a duplicate")
                email, name, tg, legacy_w, legacy_p = rows[0]
                self.assertEqual(email, f"first-linked-{nonce}@example.com")
                self.assertEqual(name, f"first-player-{nonce}", "Player.name still wins")
                self.assertEqual(tg, 9990004)
                self.assertIsNotNone(legacy_w)
                self.assertEqual(legacy_p, p_id)
            finally:
                await engine.dispose()
        self._async(run())

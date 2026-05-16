"""Sprint 3 / PR 3.1 — identity-from-JWT enforcement.

After PR 3.1 the API does not read `web_user_id` / `requester_id` /
`player_id` from request bodies or query strings for purposes of
"who is the caller". Identity comes from the Bearer JWT only.

These tests assert that:
  1. A forged `web_user_id` in a POST body is silently dropped — the
     created resource is owned by the JWT user, not the forged id.
  2. A forged `?web_user_id=` query param on a list endpoint is ignored.
  3. `list_members` response no longer leaks the legacy `web_user_id`
     alias key (only `user_id`).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from tests.backend_integration_support import BackendIntegrationCase


class IdentityFromJwtTests(BackendIntegrationCase):
    def test_create_lobby_ignores_forged_web_user_id_in_body(self) -> None:
        """POST /api/lobby with a foreign `web_user_id` field still creates
        the lobby owned by the JWT user."""
        owner = self.register_user("ident-owner")
        forged_target = self.register_user("ident-victim")

        response = self.client.post(
            "/api/lobby",
            json={
                "name": f"ident lobby {uuid.uuid4().hex[:5]}",
                # Sprint 3: this field MUST be ignored. Before PR 3.1 the
                # backend never used it anyway (Pydantic schema dropped it),
                # but the regression test pins the behaviour.
                "web_user_id": forged_target["id"],
            },
            headers=self.auth_headers(owner["token"]),
        )
        self.assertEqual(response.status_code, 200, response.text)
        lobby_id = response.json()["id"]

        async def _load_creator(session):
            from backend.models.models import Lobby
            row = (await session.execute(
                select(Lobby).where(Lobby.id == lobby_id)
            )).scalars().first()
            return row.creator_user_id if row else None

        creator_user_id = self.harness.db_call(_load_creator)
        self.assertEqual(creator_user_id, owner["id"])
        self.assertNotEqual(creator_user_id, forged_target["id"])

    def test_list_lobbies_query_param_no_longer_honored(self) -> None:
        """GET /api/lobby?web_user_id=X used to return X's lobbies; after
        PR 3.1 the query param is gone, so the endpoint returns the
        public/anonymous listing (no `your_role` field)."""
        owner = self.register_user("ident-list")

        # Anonymous call (no Bearer) — should hit the public branch.
        anon = self.client.get(f"/api/lobby?web_user_id={owner['id']}")
        self.assertEqual(anon.status_code, 200, anon.text)
        for lobby in anon.json():
            # Public branch never sets `your_role` on rows.
            self.assertNotIn("your_role", lobby)

    def test_list_members_no_web_user_id_alias(self) -> None:
        """`/api/lobby/{id}/members` no longer emits the legacy
        `web_user_id` alias key."""
        owner = self.register_user("ident-members")
        lobby = self.client.post(
            "/api/lobby",
            json={"name": f"members lobby {uuid.uuid4().hex[:5]}"},
            headers=self.auth_headers(owner["token"]),
        ).json()

        members = self.client.get(
            f"/api/lobby/{lobby['id']}/members",
            headers=self.auth_headers(owner["token"]),
        )
        self.assertEqual(members.status_code, 200, members.text)
        payload = members.json()
        self.assertGreaterEqual(len(payload), 1)
        for row in payload:
            self.assertIn("user_id", row)
            self.assertNotIn("web_user_id", row)

from __future__ import annotations

import uuid

from tests.backend_integration_support import BackendIntegrationCase


class BackendLobbyIntegrationTests(BackendIntegrationCase):
    def _create_lobby(self, token: str, *, name: str | None = None) -> dict:
        response = self.client.post(
            "/api/lobby",
            json={
                "name": name or f"Lobby {uuid.uuid4().hex[:6]}",
                "description": "integration lobby",
            },
            headers=self.auth_headers(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_lobby_crud_join_leave_invite_and_settings_flow(self) -> None:
        host = self.register_user("lobby-host")
        guest = self.register_user("lobby-guest")

        lobby = self._create_lobby(host["token"])

        public_list = self.client.get("/api/lobby")
        self.assertEqual(public_list.status_code, 200, public_list.text)
        self.assertEqual(public_list.json()[0]["id"], lobby["id"])

        guest_list_before = self.client.get("/api/lobby", headers=self.auth_headers(guest["token"]))
        self.assertEqual(guest_list_before.status_code, 200, guest_list_before.text)
        self.assertEqual(guest_list_before.json(), [])

        wrong_join = self.client.post(
            f"/api/lobby/{lobby['id']}/join",
            json={"invite_code": "wrong-code"},
            headers=self.auth_headers(guest["token"]),
        )
        self.assertEqual(wrong_join.status_code, 403, wrong_join.text)

        join_response = self.client.post(
            f"/api/lobby/{lobby['id']}/join",
            json={"invite_code": lobby["invite_code"]},
            headers=self.auth_headers(guest["token"]),
        )
        self.assertEqual(join_response.status_code, 200, join_response.text)

        join_by_code = self.client.post(
            "/api/lobby/join-by-code",
            json={"invite_code": lobby["invite_code"]},
            headers=self.auth_headers(guest["token"]),
        )
        self.assertEqual(join_by_code.status_code, 200, join_by_code.text)
        self.assertEqual(join_by_code.json()["message"], "Already a member")

        guest_list_after = self.client.get("/api/lobby", headers=self.auth_headers(guest["token"]))
        self.assertEqual(guest_list_after.status_code, 200, guest_list_after.text)
        self.assertEqual(guest_list_after.json()[0]["id"], lobby["id"])

        detail_guest = self.client.get(
            f"/api/lobby/{lobby['id']}",
            headers=self.auth_headers(guest["token"]),
        )
        self.assertEqual(detail_guest.status_code, 200, detail_guest.text)
        self.assertEqual(detail_guest.json()["your_role"], "member")
        self.assertIsNone(detail_guest.json()["invite_code"])

        members = self.client.get(
            f"/api/lobby/{lobby['id']}/members",
            headers=self.auth_headers(guest["token"]),
        )
        self.assertEqual(members.status_code, 200, members.text)
        self.assertEqual(len(members.json()), 2)

        settings = self.client.put(
            f"/api/lobby/{lobby['id']}/settings",
            json={"name": "Updated Lobby", "description": "updated"},
            headers=self.auth_headers(host["token"]),
        )
        self.assertEqual(settings.status_code, 200, settings.text)
        self.assertEqual(settings.json()["name"], "Updated Lobby")

        new_invite = self.client.post(
            f"/api/lobby/{lobby['id']}/invite/reset",
            headers=self.auth_headers(host["token"]),
        )
        self.assertEqual(new_invite.status_code, 200, new_invite.text)
        self.assertNotEqual(new_invite.json()["invite_code"], lobby["invite_code"])

        leave_guest = self.client.delete(
            f"/api/lobby/{lobby['id']}/leave",
            headers=self.auth_headers(guest["token"]),
        )
        self.assertEqual(leave_guest.status_code, 200, leave_guest.text)

        leave_host = self.client.delete(
            f"/api/lobby/{lobby['id']}/leave",
            headers=self.auth_headers(host["token"]),
        )
        self.assertEqual(leave_host.status_code, 400, leave_host.text)

    def test_role_change_kick_and_host_seasons_permission_boundaries(self) -> None:
        host = self.register_user("perm-host")
        moderator = self.register_user("perm-moderator")
        target = self.register_user("perm-target")

        lobby = self._create_lobby(host["token"])

        for user in (moderator, target):
            join = self.client.post(
                f"/api/lobby/{lobby['id']}/join",
                json={"invite_code": lobby["invite_code"]},
                headers=self.auth_headers(user["token"]),
            )
            self.assertEqual(join.status_code, 200, join.text)

        forbidden_change = self.client.patch(
            f"/api/lobby/{lobby['id']}/members/{target['id']}/role",
            json={"new_role": "moderator"},
            headers=self.auth_headers(moderator["token"]),
        )
        self.assertEqual(forbidden_change.status_code, 403, forbidden_change.text)

        promote = self.client.patch(
            f"/api/lobby/{lobby['id']}/members/{moderator['id']}/role",
            json={"new_role": "moderator"},
            headers=self.auth_headers(host["token"]),
        )
        self.assertEqual(promote.status_code, 200, promote.text)

        create_season = self.client.post(
            f"/api/lobby/{lobby['id']}/seasons",
            json={"name": "Moderator Season"},
            headers=self.auth_headers(moderator["token"]),
        )
        self.assertEqual(create_season.status_code, 200, create_season.text)
        season_id = create_season.json()["id"]

        kick = self.client.delete(
            f"/api/lobby/{lobby['id']}/members/{target['id']}",
            headers=self.auth_headers(moderator["token"]),
        )
        self.assertEqual(kick.status_code, 200, kick.text)

        host_seasons = self.client.get("/api/lobby/host-seasons", headers=self.auth_headers(moderator["token"]))
        self.assertEqual(host_seasons.status_code, 200, host_seasons.text)
        self.assertEqual(host_seasons.json()[0]["id"], season_id)
        self.assertTrue(host_seasons.json()[0]["can_manage"])

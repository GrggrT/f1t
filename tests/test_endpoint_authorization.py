"""PR 1.1 — verifies the 16 endpoints listed in the roadmap reject
anonymous requests with HTTP 401.

A few rows also exercise the 403 branch (authenticated but lacking the
required role) — that's the second half of the smoke check.

Bodies are minimal but schema-valid so we don't get a 422 short-circuit
before the auth dependency runs (FastAPI parses the body alongside
dependencies; a malformed body could mask a real 401 by returning 422).
"""
from __future__ import annotations

import uuid

from tests.backend_integration_support import BackendIntegrationCase


# (method, path, body_or_None). Body must be schema-valid where required so
# the 401/403 check is not shadowed by a 422 validation error.
PROTECTED_ENDPOINTS: list[tuple[str, str, dict | None]] = [
    # system_admin only
    ("POST", "/api/players/register", {"name": "Test", "telegram_id": 9999000}),
    ("POST", "/api/players/add_steam", {"telegram_id": 9999000, "steam_input": "ignored"}),
    ("POST", "/api/players/map_steam", {"steam_name": "x", "player_id": 1, "race_id": 1}),
    ("PATCH", "/api/players/1", {"name": "renamed"}),
    # Authenticated (any user)
    ("POST", "/api/web/link-player", {"player_id": 1}),
    ("POST", "/api/web/launcher/auth", {"poll_id": "abc"}),
    ("POST", "/api/seasons/assistant", {"player_id": 1, "question": "summary"}),
    ("POST", "/api/telemetry/race-analysis/1/debrief", {}),
    ("POST", "/api/engineer/ask", {"question": "what now?"}),
    ("POST", "/api/predict/1", {}),
    ("POST", "/api/contracts/accept", {"player_id": 1, "team_id": 1, "new_season_id": 1}),
    # Lobby moderator+ for season (or lobby member)
    ("POST", "/api/contracts/generate/1", None),
    ("GET",  "/api/lobby/1/members", None),
    ("GET",  "/api/lobby/1/seasons", None),
    ("GET",  "/api/lobby/1/engineer", None),
    ("POST", "/api/lobby/1/engineer/ask", {"question": "what now?"}),
]


class AnonymousRequestsRejectedTests(BackendIntegrationCase):
    """Every protected endpoint must respond 401 without Authorization."""

    def test_no_bearer_token_returns_401(self):
        failures: list[str] = []
        for method, path, body in PROTECTED_ENDPOINTS:
            response = self.client.request(method, path, json=body)
            if response.status_code != 401:
                failures.append(
                    f"{method} {path}: expected 401, got {response.status_code} "
                    f"(body: {response.text[:160]})"
                )
        self.assertFalse(
            failures,
            "Endpoints not returning 401 for anonymous requests:\n" + "\n".join(failures),
        )


class AuthenticatedRoleChecksTests(BackendIntegrationCase):
    """Authenticated but role-deficient calls must return 403, not 200."""

    def _create_non_admin_user(self) -> str:
        prefix = f"role-test-{uuid.uuid4().hex[:6]}"
        u = self.register_user(prefix)
        login = self.client.post(
            "/api/web/launcher/login",
            json={"email": u["email"], "password": "Password123!"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["token"]

    def test_non_admin_cannot_hit_system_admin_endpoints(self):
        token = self._create_non_admin_user()
        headers = self.auth_headers(token)
        for method, path, body in [
            ("POST", "/api/players/register", {"name": "X", "telegram_id": 8888001}),
            ("POST", "/api/players/add_steam", {"telegram_id": 8888001, "steam_input": "x"}),
            ("PATCH", "/api/players/1", {"name": "x"}),
        ]:
            response = self.client.request(method, path, json=body, headers=headers)
            self.assertEqual(
                response.status_code, 403,
                f"{method} {path}: expected 403 for non-admin, got {response.status_code} ({response.text[:160]})",
            )

    def test_non_member_cannot_hit_lobby_scoped_endpoints(self):
        # Fresh user, no lobby membership.
        token = self._create_non_admin_user()
        headers = self.auth_headers(token)
        for method, path, body in [
            ("GET",  "/api/lobby/1/members", None),
            ("GET",  "/api/lobby/1/seasons", None),
            ("GET",  "/api/lobby/1/engineer", None),
            ("POST", "/api/lobby/1/engineer/ask", {"question": "?"}),
        ]:
            response = self.client.request(method, path, json=body, headers=headers)
            # Either 403 (correct role rejection) or 404 (lobby/season doesn't exist
            # — also acceptable since unprivileged user shouldn't even probe scope).
            self.assertIn(
                response.status_code, (403, 404),
                f"{method} {path}: expected 403/404 for non-member, got {response.status_code} ({response.text[:160]})",
            )

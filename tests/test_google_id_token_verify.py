"""PR 1.5 — Google id_token verification on /api/web/google.

Before this PR the endpoint trusted client-provided `google_id` and `email`
fields, so a forged POST could elevate to system_admin whenever the email
matched SYSTEM_ADMIN_EMAILS. After: the endpoint accepts only an `id_token`
field, which is verified against Google's keys via google.oauth2.id_token.

All tests mock google_id_token.verify_oauth2_token so they don't hit
Google's real JWKS endpoint.
"""
from __future__ import annotations

import os
import uuid
from unittest import mock

from tests.backend_integration_support import BackendIntegrationCase


_GOOGLE_VERIFY_PATCH = "backend.routers.web_auth.google_id_token.verify_oauth2_token"


class GoogleIdTokenVerifyTests(BackendIntegrationCase):
    def setUp(self):
        # Endpoint refuses 503 if GOOGLE_CLIENT_ID is not set; the integration
        # harness doesn't set it, so we inject one for the duration of each
        # test.
        self._env = mock.patch.dict(
            os.environ,
            {"GOOGLE_CLIENT_ID": "fake-google-client-id"},
            clear=False,
        )
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_old_payload_shape_is_rejected_with_422(self):
        # `google_id`/`email`/`name` are no longer accepted — without
        # `id_token` the request fails schema validation.
        response = self.client.post(
            "/api/web/google",
            json={
                "google_id": "forged-sub",
                "email": "anyone@example.com",
                "name": "Forged",
            },
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_fake_id_token_returns_401(self):
        with mock.patch(_GOOGLE_VERIFY_PATCH) as verify:
            verify.side_effect = ValueError("not a real JWT")
            response = self.client.post(
                "/api/web/google",
                json={"id_token": "definitely.not.real"},
            )
        self.assertEqual(response.status_code, 401, response.text)
        self.assertIn("Invalid", response.text)

    def test_unverified_email_returns_401(self):
        with mock.patch(_GOOGLE_VERIFY_PATCH) as verify:
            verify.return_value = {
                "sub": "google-sub-unverified",
                "email": "ghost@example.com",
                "email_verified": False,
                "name": "Ghost",
            }
            response = self.client.post(
                "/api/web/google",
                json={"id_token": "x.y.z"},
            )
        self.assertEqual(response.status_code, 401, response.text)
        self.assertIn("not verified", response.text.lower())

    def test_valid_token_creates_user_and_returns_backend_token(self):
        unique_email = f"google-user-{uuid.uuid4().hex[:8]}@example.com"
        with mock.patch(_GOOGLE_VERIFY_PATCH) as verify:
            verify.return_value = {
                "sub": f"google-sub-{uuid.uuid4().hex[:10]}",
                "email": unique_email,
                "email_verified": True,
                "name": "Google Smoke User",
                "picture": "https://example.com/pic.png",
            }
            response = self.client.post(
                "/api/web/google",
                json={"id_token": "x.y.z"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["email"], unique_email)
        self.assertTrue(payload.get("token"), payload)
        self.assertFalse(payload["is_system_admin"], "fresh email should not be admin")

    def test_system_admin_only_when_email_verified_and_in_allowlist(self):
        admin_email = "pr15-admin-allowed@example.com"
        with mock.patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "fake-google-client-id",
                "SYSTEM_ADMIN_EMAILS": admin_email,
            },
            clear=False,
        ):
            # The SYSTEM_ADMIN_EMAILS set is captured at module import in
            # web_auth.py; patch it directly so the test sees the allow-list.
            from backend.routers import web_auth

            with mock.patch.object(
                web_auth,
                "SYSTEM_ADMIN_EMAILS",
                {admin_email},
            ):
                with mock.patch(_GOOGLE_VERIFY_PATCH) as verify:
                    # Verified + on allowlist → admin.
                    verify.return_value = {
                        "sub": "admin-sub-verified",
                        "email": admin_email,
                        "email_verified": True,
                        "name": "PR15 Admin",
                    }
                    r_ok = self.client.post(
                        "/api/web/google",
                        json={"id_token": "x.y.z"},
                    )

                    # Same allow-listed email but Google didn't verify it →
                    # would have been blocked earlier. We separately check
                    # that a verified email NOT on the allow-list does not
                    # get promoted.
                    verify.return_value = {
                        "sub": f"non-admin-sub-{uuid.uuid4().hex[:6]}",
                        "email": f"not-on-list-{uuid.uuid4().hex[:6]}@example.com",
                        "email_verified": True,
                        "name": "Non Admin",
                    }
                    r_non_admin = self.client.post(
                        "/api/web/google",
                        json={"id_token": "x.y.z"},
                    )

        self.assertEqual(r_ok.status_code, 200, r_ok.text)
        self.assertTrue(r_ok.json()["is_system_admin"])
        self.assertEqual(r_non_admin.status_code, 200, r_non_admin.text)
        self.assertFalse(r_non_admin.json()["is_system_admin"])

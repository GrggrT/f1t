from __future__ import annotations

import asyncio
import sys
import unittest
from unittest import mock

sys.modules.setdefault("webview", mock.Mock())

from agent import telemetry_delivery, uploader
from agent.launcher import DEFAULT_CONFIG, LauncherAPI


class _ImmediateThread:
    def __init__(self, target=None, *args, **kwargs):
        self._target = target

    def start(self) -> None:
        if self._target:
            self._target()


class LauncherDeliveryRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._load_config_patch = mock.patch("agent.launcher.load_config", return_value=dict(DEFAULT_CONFIG))
        self._save_config_patch = mock.patch("agent.launcher.save_config_file")
        self._load_config_patch.start()
        self._save_config_patch.start()
        self.addCleanup(self._load_config_patch.stop)
        self.addCleanup(self._save_config_patch.stop)

    def tearDown(self) -> None:
        policy = asyncio.get_event_loop_policy()
        local_state = getattr(policy, "_local", None)
        loop = getattr(local_state, "_loop", None) if local_state is not None else None
        if loop and not loop.is_closed():
            loop.close()
        if local_state is not None and getattr(local_state, "_loop", None) is loop:
            local_state._loop = None
        asyncio.set_event_loop(None)

    def test_pending_delivery_snapshot_combines_uploads_and_telemetry(self) -> None:
        api = LauncherAPI()
        with mock.patch.object(api, "_pending_uploads_snapshot", return_value={"count": 1, "error": None}):
            with mock.patch.object(
                api,
                "_pending_telemetry_snapshot",
                return_value={"count": 2, "ready_to_flush": 1, "waiting_for_race_id": 1, "error": None},
            ):
                snapshot = api._pending_delivery_snapshot()

        self.assertEqual(snapshot["count"], 3)
        self.assertEqual(snapshot["pending_uploads"], 1)
        self.assertEqual(snapshot["pending_telemetry"], 2)
        self.assertEqual(snapshot["telemetry_ready_to_flush"], 1)
        self.assertEqual(snapshot["telemetry_waiting_for_race_id"], 1)
        self.assertEqual(snapshot["errors"], [])

    def test_retry_pending_uploads_now_runs_when_only_telemetry_is_buffered(self) -> None:
        api = LauncherAPI()
        calls: list[str] = []

        async def fake_retry_uploads(observer=None) -> None:
            calls.append("upload")

        async def fake_retry_telemetry(observer=None) -> None:
            calls.append("telemetry")

        with mock.patch.object(
            api,
            "_pending_delivery_snapshot",
            return_value={
                "count": 2,
                "pending_uploads": 0,
                "pending_telemetry": 2,
                "telemetry_ready_to_flush": 1,
                "telemetry_waiting_for_race_id": 1,
                "errors": [],
            },
        ):
            with mock.patch.object(api, "_refresh_upload_component"):
                with mock.patch.object(api, "_refresh_telemetry_component"):
                    with mock.patch.object(api, "_record_event"):
                        with mock.patch("agent.launcher.threading.Thread", side_effect=lambda *args, **kwargs: _ImmediateThread(*args, **kwargs)):
                            with mock.patch.object(uploader, "retry_pending_uploads", new=fake_retry_uploads):
                                with mock.patch.object(telemetry_delivery, "retry_pending", new=fake_retry_telemetry):
                                    result = api.retry_pending_uploads_now()

        self.assertTrue(result["ok"])
        self.assertTrue(result["started"])
        self.assertEqual(result["retried"], 2)
        self.assertEqual(result["retried_uploads"], 0)
        self.assertEqual(result["retried_telemetry"], 2)
        self.assertEqual(calls, ["upload", "telemetry"])


if __name__ == "__main__":
    unittest.main()

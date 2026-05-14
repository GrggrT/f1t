import unittest
from unittest import mock

from agent.personal_session_sync import _build_laps, _select_vehicle_index, sync_personal_session
from agent.telemetry_buffer import TelemetrySnapshot


class PersonalSessionSyncTests(unittest.TestCase):
    def test_select_vehicle_prefers_local_player(self):
        snapshot = TelemetrySnapshot(
            laps={
                0: {1: {"lap_time_ms": 90000, "samples": [{"t": 1.0}]}},
                3: {1: {"lap_time_ms": 91000, "samples": [{"t": 1.0}]}},
            }
        )

        vehicle_index = _select_vehicle_index(
            snapshot,
            participants=[
                {"vehicle_index": 3, "m_aiControlled": 0},
                {"vehicle_index": 0, "m_aiControlled": 0},
            ],
        )

        self.assertEqual(vehicle_index, 0)

    def test_build_laps_merges_history_and_snapshot(self):
        snapshot = TelemetrySnapshot(
            laps={
                0: {
                    1: {"lap_time_ms": 91234, "samples": [{"t": 1.0}]},
                    2: {"lap_time_ms": 90500, "samples": [{"t": 2.0}]},
                }
            },
            session_history={
                0: {
                    "vehicle_index": 0,
                    "num_laps": 2,
                    "best_lap_num": 2,
                    "best_s1_lap": 2,
                    "best_s2_lap": 2,
                    "best_s3_lap": 2,
                    "laps": [
                        {
                            "lap_number": 1,
                            "lap_time_ms": 91234,
                            "sector1_ms": 30000,
                            "sector2_ms": 31000,
                            "sector3_ms": 30234,
                            "lap_valid": True,
                        }
                    ],
                }
            },
        )

        laps = _build_laps(snapshot, 0)

        self.assertEqual(len(laps), 2)
        self.assertEqual(laps[0]["sector1_ms"], 30000)
        self.assertEqual(laps[1]["lap_time_ms"], 90500)
        self.assertTrue(laps[1]["valid"])

    def test_sync_personal_session_posts_session_laps_and_end(self):
        snapshot = TelemetrySnapshot(
            laps={0: {1: {"lap_time_ms": 90000, "samples": [{"t": 1.0}]}}},
        )

        created_response = mock.Mock(status_code=200)
        created_response.json.return_value = {"id": 77}
        added_response = mock.Mock(status_code=200)
        ended_response = mock.Mock(status_code=200)

        client = mock.Mock()
        client.post.side_effect = [created_response, added_response, ended_response]
        client_cm = mock.Mock()
        client_cm.__enter__ = mock.Mock(return_value=client)
        client_cm.__exit__ = mock.Mock(return_value=False)

        with mock.patch("agent.personal_session_sync.agent_config.AUTH_TOKEN", "token"), \
             mock.patch("agent.personal_session_sync.httpx.Client", return_value=client_cm):
            ok = sync_personal_session(
                123,
                snapshot,
                track_id=7,
                session_type=10,
                participants=[{"vehicle_index": 0, "m_aiControlled": 0}],
            )

        self.assertTrue(ok)
        self.assertEqual(client.post.call_count, 3)
        create_call = client.post.call_args_list[0]
        self.assertIn("/api/practice/sessions", create_call.args[0])
        self.assertEqual(create_call.kwargs["json"]["session_type"], "Race")


if __name__ == "__main__":
    unittest.main()

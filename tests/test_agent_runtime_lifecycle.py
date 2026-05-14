from __future__ import annotations

import struct
import time
import unittest
from unittest import mock

from agent.main import F1Agent
from agent.replay_harness import build_sample_packets
from agent.state_machine import AgentState, StateMachine
from agent.udp_listener import HEADER_FORMAT, HEADER_SIZE
from agent.ws_client import WSClient


def _packet_meta(raw: bytes) -> tuple[int, int, int]:
    header = struct.unpack(HEADER_FORMAT, raw[:HEADER_SIZE])
    return int(header[5]), int(header[6]), int(header[0])


def _feed_packet(agent: F1Agent, raw: bytes) -> None:
    packet_id, session_uid, packet_format = _packet_meta(raw)
    agent._on_packet(packet_id, session_uid, packet_format, raw)


def _make_agent() -> F1Agent:
    agent = F1Agent()
    agent.ws.send_status = lambda *args, **kwargs: None
    agent.ws.send_live = lambda *args, **kwargs: None
    agent.raw_log.start_session = lambda *args, **kwargs: None
    agent.raw_log.write = lambda *args, **kwargs: None
    agent.raw_log.stop = lambda *args, **kwargs: None
    agent._scanner._active = False
    return agent


class StateMachineTests(unittest.TestCase):
    def test_invalid_transition_is_rejected(self):
        sm = StateMachine()

        changed = sm.transition(AgentState.FINISHED, reason="invalid_test")

        self.assertFalse(changed)
        self.assertEqual(sm.state, AgentState.IDLE)


class AgentRuntimeLifecycleTests(unittest.TestCase):
    def test_duplicate_final_classification_starts_single_upload_worker(self):
        agent = _make_agent()
        upload_calls: list[tuple[int, dict]] = []
        agent._start_upload_worker = lambda session_uid, payload: upload_calls.append((session_uid, payload))

        packets = build_sample_packets(session_uid=101)
        for packet in packets[:3]:
            _feed_packet(agent, packet)

        self.assertEqual(agent.sm.state, AgentState.RACE)

        final_packet = packets[-1]
        _feed_packet(agent, final_packet)
        _feed_packet(agent, final_packet)

        self.assertEqual(agent.sm.state, AgentState.FINISHED)
        self.assertEqual(len(upload_calls), 1)
        self.assertIn(101, agent._uploading_uids)
        self.assertFalse(agent._telem._running)

    def test_failed_upload_resets_session_and_allows_next_race(self):
        agent = _make_agent()
        packets = build_sample_packets(session_uid=202)

        for packet in packets[:3]:
            _feed_packet(agent, packet)

        agent._start_upload_worker = lambda session_uid, payload: agent._upload_race(session_uid, payload)

        with mock.patch("agent.main.upload_race", return_value=(False, None)):
            _feed_packet(agent, packets[-1])

        self.assertEqual(agent.sm.state, AgentState.IDLE)
        self.assertEqual(agent._session_uid, 0)
        self.assertNotIn(202, agent._uploading_uids)

        next_waiting_packet = build_sample_packets(session_uid=303)[0]
        _feed_packet(agent, next_waiting_packet)

        self.assertEqual(agent._session_uid, 303)
        self.assertEqual(agent.sm.state, AgentState.WAITING)

    def test_stale_final_classification_is_ignored_after_session_rollover(self):
        agent = _make_agent()
        upload_calls: list[int] = []
        agent._start_upload_worker = lambda session_uid, payload: upload_calls.append(session_uid)

        first_session_packets = build_sample_packets(session_uid=111)
        for packet in first_session_packets[:3]:
            _feed_packet(agent, packet)

        self.assertEqual(agent.sm.state, AgentState.RACE)

        rollover_waiting_packet = build_sample_packets(session_uid=222)[0]
        _feed_packet(agent, rollover_waiting_packet)

        self.assertEqual(agent._session_uid, 222)
        self.assertEqual(agent.sm.state, AgentState.WAITING)

        stale_final_packet = first_session_packets[-1]
        _feed_packet(agent, stale_final_packet)

        self.assertEqual(agent._session_uid, 222)
        self.assertEqual(agent.sm.state, AgentState.WAITING)
        self.assertEqual(upload_calls, [])


class WSClientLifecycleTests(unittest.TestCase):
    def test_ws_client_prefers_agent_secret_token_for_backend_auth(self):
        with mock.patch("agent.ws_client.config.get_agent_secret_token", return_value="agent-secret"):
            with mock.patch("agent.ws_client.INVITE_TOKEN", "invite-token"):
                self.assertEqual(WSClient._auth_token(), "agent-secret")

    def test_stop_wakes_reconnect_backoff(self):
        with mock.patch("agent.ws_client.WS_AVAILABLE", True):
            with mock.patch("agent.ws_client.websockets.connect", side_effect=OSError("backend down"), create=True):
                client = WSClient()
                client.start()

                deadline = time.time() + 1.0
                while time.time() < deadline and client.state not in {"connecting", "error"}:
                    time.sleep(0.05)

                start = time.monotonic()
                client.stop()
                elapsed = time.monotonic() - start

                if client._thread is not None:
                    self.assertFalse(client._thread.is_alive())
                self.assertEqual(client.state, "stopped")
                self.assertLess(elapsed, 1.5)


if __name__ == "__main__":
    unittest.main()

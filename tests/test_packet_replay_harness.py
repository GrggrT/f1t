from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import f1.packets as f1_packets

from agent.packet_parser import extract_final_classification, parse_packet
from agent.replay_harness import analyze_raw_log, run_replay, write_sample_raw_log
from agent.udp_listener import PACKET_ID_FINAL_CLASSIF


class PacketReplayHarnessTests(unittest.TestCase):
    def test_manual_2025_packet_map_overrides_incorrect_resolve_mapping(self):
        packet = f1_packets.PacketFinalClassificationData()
        packet.header.packet_format = 2025
        packet.header.game_year = 25
        packet.header.game_major_version = 1
        packet.header.game_minor_version = 0
        packet.header.packet_version = 1
        packet.header.packet_id = PACKET_ID_FINAL_CLASSIF
        packet.header.session_uid = 111
        packet.num_cars = 1
        packet.classification_data[0].position = 1
        packet.classification_data[0].num_laps = 58
        packet.classification_data[0].best_lap_time_in_ms = 88_111
        packet.classification_data[0].result_status = 3

        raw = bytes(packet)

        with self.assertRaises(ValueError):
            f1_packets.resolve(raw)

        parsed = parse_packet(PACKET_ID_FINAL_CLASSIF, 2025, raw)
        classification = extract_final_classification(parsed)
        self.assertEqual(len(classification), 1)
        self.assertEqual(classification[0]["m_position"], 1)
        self.assertEqual(classification[0]["m_bestLapTimeInMS"], 88_111)

    def test_analyze_raw_log_reports_all_key_extractors(self):
        with tempfile.TemporaryDirectory(prefix="f1t_replay_test_") as tmp_dir:
            log_path = write_sample_raw_log(Path(tmp_dir) / "fixture_session_track10.bin")
            summary = analyze_raw_log(log_path)

        self.assertEqual(summary.total_packets, 12)
        self.assertFalse(summary.parse_failures)
        self.assertEqual(summary.packet_counts[1], 2)
        self.assertEqual(summary.packet_counts[11], 1)
        self.assertEqual(summary.extractor_hits["session_info"], 2)
        self.assertEqual(summary.extractor_hits["participants"], 1)
        self.assertEqual(summary.extractor_hits["event"], 1)
        self.assertEqual(summary.extractor_hits["lap_positions"], 1)
        self.assertEqual(summary.extractor_hits["final_classification"], 1)
        self.assertEqual(summary.extractor_hits["session_history"], 1)

    def test_replay_into_agent_populates_pipeline_state(self):
        with tempfile.TemporaryDirectory(prefix="f1t_replay_test_") as tmp_dir:
            log_path = write_sample_raw_log(Path(tmp_dir) / "fixture_session_track10.bin")
            summary = run_replay(log_path, include_agent=True)

        self.assertIsNotNone(summary.agent)
        assert summary.agent is not None
        self.assertEqual(summary.agent.final_state, "finished")
        self.assertEqual(summary.agent.participants, 2)
        self.assertEqual(summary.agent.events, 1)
        self.assertEqual(summary.agent.classification_entries, 2)
        self.assertGreaterEqual(summary.agent.live_entries, 2)
        self.assertGreaterEqual(summary.agent.telemetry_latest_entries, 2)
        self.assertGreaterEqual(summary.agent.telemetry_samples, 1)
        self.assertEqual(summary.agent.session_history_entries, 1)


if __name__ == "__main__":
    unittest.main()

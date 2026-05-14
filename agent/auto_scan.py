"""
One-time ID auto-scan for track/team/driver verification.

The scan runs only until the first session with participant data completes, then
it stores the discovered ids for later mapping review.
"""
from __future__ import annotations

import json

from agent.config import DATA_DIR


SCAN_FILE = DATA_DIR / "id_scan.json"
SCAN_DONE_FILE = DATA_DIR / "scan_done.flag"


class AutoScanner:
    def __init__(self):
        self._active = not SCAN_DONE_FILE.exists()
        self._data = {
            "track_ids": set(),
            "team_ids": set(),
            "driver_ids": set(),
            "names": set(),
        }
        if self._active:
            print("[SCAN] Auto-scan active - collecting F1 IDs for verification")

    @property
    def active(self) -> bool:
        return self._active

    def process_session(self, track_id: int | None) -> None:
        if not self._active or track_id is None:
            return
        self._data["track_ids"].add(track_id)
        self._save()

    def process_participants(self, participants: list[dict]) -> None:
        if not self._active:
            return
        for participant in participants:
            self._data["team_ids"].add(participant.get("m_teamId", -1))
            self._data["driver_ids"].add(participant.get("m_driverId", -1))
            name = participant.get("m_name", "").strip()
            if name:
                self._data["names"].add(name)
        self._save()

    def mark_done(self) -> None:
        SCAN_DONE_FILE.touch()
        self._active = False
        print(f"[SCAN] Done. Results saved to {SCAN_FILE}")
        self._print_summary()

    def _save(self) -> None:
        serializable = {key: sorted(values) for key, values in self._data.items()}
        SCAN_FILE.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def _print_summary(self) -> None:
        from shared.f1_mappings import DRIVERS, TEAMS, TRACKS

        print("\n[SCAN] === ID Verification ===")

        print("\nTrack IDs found:")
        for track_id in sorted(self._data["track_ids"]):
            known = TRACKS.get(track_id, "UNKNOWN")
            print(f"  {track_id:3d} -> {known}")

        print("\nTeam IDs found:")
        for team_id in sorted(self._data["team_ids"]):
            known = TEAMS.get(team_id, {}).get("name", "UNKNOWN")
            print(f"  {team_id:3d} -> {known}")

        print("\nDriver IDs found:")
        for driver_id in sorted(self._data["driver_ids"]):
            known = DRIVERS.get(driver_id, {}).get("name", "UNKNOWN")
            print(f"  {driver_id:3d} -> {known}")

        print("\nSteam names found:")
        for name in sorted(self._data["names"]):
            print(f"  {name}")
        print()


def reset_scan() -> None:
    if SCAN_DONE_FILE.exists():
        SCAN_DONE_FILE.unlink()
    if SCAN_FILE.exists():
        SCAN_FILE.unlink()
    print("[SCAN] Reset. Auto-scan will run on next session.")

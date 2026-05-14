"""
Telemetry buffering for high-rate race samples.

The buffer samples Motion + CarTelemetry + LapData at a fixed cadence during
race state. Snapshots are detached at session end and later flushed only after
the backend returns a race id.
"""
from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field
from typing import Any


SAMPLE_INTERVAL = 0.2


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _copy_laps(laps: list[dict] | None) -> list[dict]:
    if not laps:
        return []
    copied: list[dict] = []
    for lap in laps:
        if isinstance(lap, dict):
            copied.append(copy.deepcopy(lap))
    copied.sort(key=lambda lap: int(lap.get("lap_number", 0) or 0))
    return copied


def _copy_history(history: dict | None) -> dict:
    if not isinstance(history, dict):
        return {}
    return {
        "vehicle_index": int(history.get("vehicle_index", 0) or 0),
        "num_laps": int(history.get("num_laps", 0) or 0),
        "best_lap_num": int(history.get("best_lap_num", 0) or 0),
        "best_s1_lap": int(history.get("best_s1_lap", 0) or 0),
        "best_s2_lap": int(history.get("best_s2_lap", 0) or 0),
        "best_s3_lap": int(history.get("best_s3_lap", 0) or 0),
        "laps": _copy_laps(history.get("laps")),
    }


def _merge_history(existing: dict | None, incoming: dict | None) -> dict:
    current = _copy_history(existing)
    fresh = _copy_history(incoming)
    if not fresh:
        return current
    if not current:
        return fresh

    merged_laps: dict[int, dict] = {
        int(lap.get("lap_number", 0) or 0): dict(lap)
        for lap in current.get("laps", [])
        if int(lap.get("lap_number", 0) or 0) > 0
    }
    for lap in fresh.get("laps", []):
        lap_number = int(lap.get("lap_number", 0) or 0)
        if lap_number <= 0:
            continue
        existing_lap = merged_laps.get(lap_number, {})
        merged_laps[lap_number] = {
            "lap_number": lap_number,
            "lap_time_ms": _positive_int(lap.get("lap_time_ms")) or _positive_int(existing_lap.get("lap_time_ms")) or 0,
            "sector1_ms": _positive_int(lap.get("sector1_ms")) or _positive_int(existing_lap.get("sector1_ms")) or 0,
            "sector2_ms": _positive_int(lap.get("sector2_ms")) or _positive_int(existing_lap.get("sector2_ms")) or 0,
            "sector3_ms": _positive_int(lap.get("sector3_ms")) or _positive_int(existing_lap.get("sector3_ms")) or 0,
            "lap_valid": bool(lap.get("lap_valid", existing_lap.get("lap_valid", True))),
        }

    return {
        "vehicle_index": fresh.get("vehicle_index", current.get("vehicle_index", 0)),
        "num_laps": max(int(current.get("num_laps", 0) or 0), int(fresh.get("num_laps", 0) or 0), len(merged_laps)),
        "best_lap_num": int(fresh.get("best_lap_num", 0) or current.get("best_lap_num", 0) or 0),
        "best_s1_lap": int(fresh.get("best_s1_lap", 0) or current.get("best_s1_lap", 0) or 0),
        "best_s2_lap": int(fresh.get("best_s2_lap", 0) or current.get("best_s2_lap", 0) or 0),
        "best_s3_lap": int(fresh.get("best_s3_lap", 0) or current.get("best_s3_lap", 0) or 0),
        "laps": [merged_laps[key] for key in sorted(merged_laps)],
    }


@dataclass
class TelemetrySnapshot:
    laps: dict[int, dict[int, dict[str, Any]]] = field(default_factory=dict)
    session_history: dict[int, dict] = field(default_factory=dict)

    def has_data(self) -> bool:
        for laps in self.laps.values():
            for lap_entry in laps.values():
                if lap_entry.get("samples"):
                    return True
        return bool(self.session_history)

    def lap_count(self) -> int:
        return sum(len(laps) for laps in self.laps.values())

    def finalize(self) -> "TelemetrySnapshot":
        histories = {int(vidx): _copy_history(history) for vidx, history in self.session_history.items()}
        finalized_laps: dict[int, dict[int, dict[str, Any]]] = {}

        for vidx, laps in self.laps.items():
            history_map = {
                int(lap.get("lap_number", 0) or 0): lap
                for lap in histories.get(int(vidx), {}).get("laps", [])
            }
            finalized_vehicle_laps: dict[int, dict[str, Any]] = {}
            for lap_number, lap_entry in laps.items():
                number = int(lap_number or 0)
                if number <= 0:
                    continue
                raw_samples = lap_entry.get("samples", [])
                samples = [copy.deepcopy(sample) for sample in raw_samples if isinstance(sample, dict)]
                if not samples:
                    continue
                lap_time_ms = _positive_int(lap_entry.get("lap_time_ms"))
                if lap_time_ms is None:
                    lap_time_ms = _positive_int(history_map.get(number, {}).get("lap_time_ms"))
                finalized_vehicle_laps[number] = {
                    "lap_time_ms": lap_time_ms,
                    "samples": samples,
                }
            if finalized_vehicle_laps:
                finalized_laps[int(vidx)] = finalized_vehicle_laps

        self.laps = finalized_laps
        self.session_history = histories
        return self

    def to_payload(self) -> dict:
        finalized = self.finalize()
        return {
            "laps": [
                {
                    "vehicle_index": vidx,
                    "lap_number": lap_number,
                    "lap_time_ms": lap_entry.get("lap_time_ms"),
                    "samples": [copy.deepcopy(sample) for sample in lap_entry.get("samples", [])],
                }
                for vidx, laps in sorted(finalized.laps.items())
                for lap_number, lap_entry in sorted(laps.items())
            ],
            "session_history": [
                _copy_history(history)
                for _, history in sorted(finalized.session_history.items())
            ],
        }

    @classmethod
    def from_payload(cls, payload: dict | None) -> "TelemetrySnapshot":
        snapshot = cls()
        if not isinstance(payload, dict):
            return snapshot

        for lap_entry in payload.get("laps", []):
            if not isinstance(lap_entry, dict):
                continue
            vehicle_index = int(lap_entry.get("vehicle_index", 0) or 0)
            lap_number = int(lap_entry.get("lap_number", 0) or 0)
            if vehicle_index < 0 or lap_number <= 0:
                continue
            snapshot.laps.setdefault(vehicle_index, {})[lap_number] = {
                "lap_time_ms": _positive_int(lap_entry.get("lap_time_ms")),
                "samples": [copy.deepcopy(sample) for sample in lap_entry.get("samples", []) if isinstance(sample, dict)],
            }

        for history in payload.get("session_history", []):
            copied = _copy_history(history)
            vehicle_index = int(copied.get("vehicle_index", 0) or 0)
            snapshot.session_history[vehicle_index] = copied

        return snapshot.finalize()


class TelemetryBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        self._latest: dict[int, dict] = {}
        self._buffers: dict[int, dict[int, dict[str, Any]]] = {}
        self._session_history: dict[int, dict] = {}
        self._tyre_wear: dict[int, list[float]] = {}

    def start_collecting(self) -> None:
        """Start a fresh sampler for a new race session."""
        self.reset()
        self._running = True
        self._thread = threading.Thread(
            target=self._sampler_loop,
            daemon=True,
            name="TelemetrySampler",
        )
        self._thread.start()
        print("[TELEM] Collecting started")

    def stop(self) -> None:
        self._running = False
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1)
        self._thread = None

    def reset(self) -> None:
        self.stop()
        with self._lock:
            self._latest.clear()
            self._buffers.clear()
            self._session_history.clear()
            self._tyre_wear.clear()

    def stop_and_snapshot(self) -> TelemetrySnapshot:
        """Stop sampling and detach the current telemetry buffers."""
        self.stop()
        with self._lock:
            snapshot = TelemetrySnapshot(
                laps={
                    int(vidx): {
                        int(lap_number): {
                            "lap_time_ms": _positive_int(lap_entry.get("lap_time_ms")),
                            "samples": [copy.deepcopy(sample) for sample in lap_entry.get("samples", []) if isinstance(sample, dict)],
                        }
                        for lap_number, lap_entry in laps.items()
                    }
                    for vidx, laps in self._buffers.items()
                },
                session_history={
                    int(vidx): _copy_history(history)
                    for vidx, history in self._session_history.items()
                },
            ).finalize()
            self._buffers.clear()
            self._latest.clear()
            self._session_history.clear()
            self._tyre_wear.clear()
        return snapshot

    def update_telemetry(
        self,
        vidx: int,
        speed: int,
        throttle: float,
        brake: float,
        gear: int,
        drs: int,
        steer: float = 0.0,
    ) -> None:
        with self._lock:
            entry = self._latest.setdefault(vidx, {})
            entry.update(
                spd=speed,
                thr=throttle,
                brk=brake,
                gear=gear,
                drs=drs,
                steer=round(steer, 2),
            )

    def update_car_status(
        self,
        vidx: int,
        ers_deploy: float,
        ers_store: float,
        fuel: float = 0.0,
        fuel_laps: float = 0.0,
    ) -> None:
        with self._lock:
            entry = self._latest.setdefault(vidx, {})
            entry.update(
                ers_deploy=ers_deploy,
                ers_store=ers_store,
                fuel=fuel,
                fuel_laps=fuel_laps,
            )

    def update_car_damage(self, vidx: int, tyres_wear: list[float]) -> None:
        with self._lock:
            self._tyre_wear[vidx] = tyres_wear
            entry = self._latest.setdefault(vidx, {})
            entry["tyre_wear"] = round(sum(tyres_wear) / max(len(tyres_wear), 1), 1)

    def update_session_history(self, vidx: int, history: dict) -> None:
        with self._lock:
            merged = _merge_history(self._session_history.get(vidx), history)
            self._session_history[vidx] = merged

    def update_motion(self, vidx: int, world_x: float, world_z: float) -> None:
        with self._lock:
            entry = self._latest.setdefault(vidx, {})
            entry.update(x=round(world_x, 1), z=round(world_z, 1))

    def update_lap(
        self,
        vidx: int,
        lap_number: int,
        lap_distance: float,
        session_time: float,
        last_lap_ms: int | None = None,
    ) -> None:
        with self._lock:
            entry = self._latest.setdefault(vidx, {})
            entry.update(
                lap=lap_number,
                dist=round(lap_distance, 1),
                t=round(session_time, 2),
            )

            completed_lap = int(lap_number or 0) - 1
            completed_lap_ms = _positive_int(last_lap_ms)
            if completed_lap >= 1 and completed_lap_ms is not None:
                lap_entry = self._buffers.setdefault(vidx, {}).setdefault(
                    completed_lap,
                    {"lap_time_ms": None, "samples": []},
                )
                lap_entry["lap_time_ms"] = completed_lap_ms

    def _sampler_loop(self) -> None:
        while self._running:
            time.sleep(SAMPLE_INTERVAL)
            if not self._running:
                break

            with self._lock:
                for vidx, entry in self._latest.items():
                    lap = int(entry.get("lap") or 0)
                    if lap < 1:
                        continue
                    if "x" not in entry or "z" not in entry:
                        continue

                    sample = {
                        "t": entry.get("t", 0),
                        "x": entry["x"],
                        "z": entry["z"],
                        "spd": entry.get("spd", 0),
                        "thr": round(entry.get("thr", 0), 2),
                        "brk": round(entry.get("brk", 0), 2),
                        "gear": entry.get("gear", 0),
                        "drs": entry.get("drs", 0),
                        "dist": entry.get("dist", 0),
                        "ers": round(entry.get("ers_deploy", 0), 2),
                        "str": entry.get("steer", 0),
                        "fuel": round(entry.get("fuel", 0), 1),
                        "tw": entry.get("tyre_wear", 0),
                    }
                    lap_entry = self._buffers.setdefault(vidx, {}).setdefault(
                        lap,
                        {"lap_time_ms": None, "samples": []},
                    )
                    lap_entry["samples"].append(sample)

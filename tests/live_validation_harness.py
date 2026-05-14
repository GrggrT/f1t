from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import socket
import subprocess
import struct
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.backend_integration_support import BackendIntegrationHarness


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LocalBackendProcess:
    def __init__(self, *, database_url: str, agent_secret_token: str) -> None:
        self.port = _free_port()
        self.database_url = database_url
        self.agent_secret_token = agent_secret_token
        self._process: subprocess.Popen[str] | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": self.database_url,
                "NEXTAUTH_SECRET": "integration-nextauth-secret",
                "AGENT_SECRET_TOKEN": self.agent_secret_token,
                "BOT_NOTIFY_URL": "http://127.0.0.1:9/internal/race_uploaded",
                "BOT_NOTIFY_SECRET": "integration-bot-secret",
                "GROQ_API_KEY": "",
                "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
            }
        )
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "warning",
            ],
            cwd=str(ROOT_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        deadline = time.time() + 15
        while time.time() < deadline:
            if self._process.poll() is not None:
                output = ""
                if self._process.stdout is not None:
                    output = self._process.stdout.read()
                raise RuntimeError(f"Local backend process exited early: {output.strip()}")
            try:
                import httpx

                response = httpx.get(f"{self.base_url}/health", timeout=1)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.05)
        raise RuntimeError("Local backend process did not become healthy for live validation.")

    def close(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=10)
        self._process = None


@contextmanager
def _temporary_env(updates: dict[str, str]):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _reload_agent_modules() -> None:
    module_names = [
        "agent.config",
        "agent.local_cache",
        "agent.telemetry_buffer",
        "agent.telemetry_delivery",
        "agent.uploader",
        "agent.raw_logger",
        "agent.main",
        "agent.replay_harness",
        "agent.postmortem",
    ]
    for name in module_names:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)


def _packet_meta(raw: bytes) -> tuple[int, int, int]:
    from agent.udp_listener import HEADER_FORMAT, HEADER_SIZE

    header = struct.unpack(HEADER_FORMAT, raw[:HEADER_SIZE])
    return int(header[5]), int(header[6]), int(header[0])


def _create_season(harness: BackendIntegrationHarness) -> dict:
    email = f"live.validation.{uuid.uuid4().hex[:8]}@example.com"
    register_response = harness.client.post(
        "/api/web/register",
        json={"email": email, "password": "Password123!", "name": "live-validation"},
    )
    register_response.raise_for_status()
    token = register_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    lobby_response = harness.client.post(
        "/api/lobby",
        json={"name": f"Live Validation {uuid.uuid4().hex[:6]}", "description": "live validation"},
        headers=headers,
    )
    lobby_response.raise_for_status()
    lobby = lobby_response.json()

    season_response = harness.client.post(
        f"/api/lobby/{lobby['id']}/seasons",
        json={"name": f"Reliability Session {uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    season_response.raise_for_status()
    season = season_response.json()
    return {
        "token": token,
        "lobby_id": lobby["id"],
        "season_id": season["id"],
    }


def run_live_validation() -> dict:
    harness = BackendIntegrationHarness()
    server: LocalBackendProcess | None = None
    try:
        harness.start()
        season = _create_season(harness)
        server = LocalBackendProcess(
            database_url=harness.database_url,
            agent_secret_token=os.environ["AGENT_SECRET_TOKEN"],
        )
        server.start()

        with tempfile.TemporaryDirectory(prefix="f1t_live_validation_") as tmp_dir:
            udp_port = _free_port()
            env_updates = {
                "F1_SERVER_URL": server.base_url,
                "F1_WS_URL": f"ws://127.0.0.1:{server.port}/ws/agent",
                "F1_UDP_PORT": str(udp_port),
                "F1_SEASON_ID": str(season["season_id"]),
                "F1_DATA_DIR": tmp_dir,
                "AGENT_SECRET_TOKEN": os.environ["AGENT_SECRET_TOKEN"],
            }
            with _temporary_env(env_updates):
                _reload_agent_modules()

                from agent import local_cache, telemetry_delivery
                from agent.main import F1Agent
                from agent.postmortem import build_postmortem_report
                from agent.replay_harness import analyze_raw_log, build_sample_packets

                observed: list[dict] = []
                ws_messages: list[dict] = []
                ws_errors: list[str] = []
                ws_ready = threading.Event()
                ws_done = threading.Event()

                def observer(source: str, event: str, payload: dict) -> None:
                    observed.append({"source": source, "event": event, "payload": dict(payload or {})})

                def websocket_probe() -> None:
                    async def runner() -> None:
                        import websockets

                        client_url = f"ws://127.0.0.1:{server.port}/ws/client"
                        async with websockets.connect(client_url, open_timeout=10) as websocket:
                            ws_ready.set()
                            deadline = time.time() + 20
                            while time.time() < deadline and not ws_done.is_set():
                                try:
                                    raw = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                                except asyncio.TimeoutError:
                                    continue
                                ws_messages.append(json.loads(raw))
                                has_status = any(
                                    message.get("type") == "agent_status" and message.get("track_name")
                                    for message in ws_messages
                                )
                                has_live = any(
                                    message.get("type") == "live_data" and message.get("entries")
                                    for message in ws_messages
                                )
                                if has_status and has_live:
                                    ws_done.set()
                                    return

                    try:
                        asyncio.run(runner())
                    except Exception as exc:
                        ws_errors.append(str(exc) or exc.__class__.__name__)
                        ws_ready.set()
                        ws_done.set()

                session_uid = 960000 + int(uuid.uuid4().hex[:6], 16)
                agent = F1Agent(observer=observer)
                agent._scanner._active = False
                probe_thread = threading.Thread(target=websocket_probe, daemon=True, name="LiveValidationWSProbe")
                probe_thread.start()

                agent.start_runtime(retry_cached_uploads=False)
                try:
                    deadline = time.time() + 10
                    while time.time() < deadline:
                        ws_connected = any(
                            item["source"] == "ws" and item["event"] == "connected"
                            for item in observed
                        )
                        udp_listening = any(
                            item["source"] == "udp" and item["event"] == "listening"
                            for item in observed
                        )
                        if ws_connected and udp_listening and ws_ready.wait(timeout=0):
                            break
                        time.sleep(0.05)
                    else:
                        raise AssertionError("Agent runtime did not bring up UDP + websocket components in time.")

                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                        for raw in build_sample_packets(session_uid=session_uid):
                            packet_id, packet_session_uid, packet_format = _packet_meta(raw)
                            udp_socket.sendto(raw, ("127.0.0.1", udp_port))
                            observed.append(
                                {
                                    "source": "harness",
                                    "event": "udp_packet_sent",
                                    "payload": {
                                        "packet_id": packet_id,
                                        "session_uid": packet_session_uid,
                                        "packet_format": packet_format,
                                    },
                                }
                            )
                            time.sleep(0.03)

                    deadline = time.time() + 30
                    while time.time() < deadline:
                        if (
                            session_uid in agent._uploaded_uids
                            and agent._session_uid == 0
                            and not local_cache.load_all()
                            and not telemetry_delivery.load_all()
                            and ws_done.is_set()
                        ):
                            break
                        time.sleep(0.1)
                    else:
                        raise AssertionError("Agent did not finish runtime upload + telemetry flush within the timeout.")

                    if ws_errors:
                        raise AssertionError(f"Browser websocket probe failed: {ws_errors[-1]}")

                    raw_logs = sorted((Path(tmp_dir) / "raw_logs").glob("session_*.bin"))
                    if not raw_logs:
                        raise AssertionError("Live validation did not produce a raw log.")

                    raw_log_path = raw_logs[0]
                    raw_summary = analyze_raw_log(raw_log_path).to_dict()
                    postmortem = build_postmortem_report(data_dir=tmp_dir, max_raw_logs=10, analyze_raw_logs=True)

                    async def load_db_snapshot(session):
                        from sqlalchemy import func, select
                        from backend.models.models import LapTelemetry, Race, RaceSessionHistory

                        result = await session.execute(select(Race).where(Race.session_uid == session_uid))
                        race = result.scalars().first()
                        if race is None:
                            return None

                        lap_count_result = await session.execute(
                            select(func.count()).select_from(LapTelemetry).where(LapTelemetry.race_id == race.id)
                        )
                        history_count_result = await session.execute(
                            select(func.count()).select_from(RaceSessionHistory).where(RaceSessionHistory.race_id == race.id)
                        )
                        return {
                            "race_id": race.id,
                            "track_id": race.track_id,
                            "lap_rows": int(lap_count_result.scalar() or 0),
                            "session_history_rows": int(history_count_result.scalar() or 0),
                        }

                    db_snapshot = harness.db_call(load_db_snapshot)
                    if db_snapshot is None:
                        raise AssertionError("Live validation did not persist the race row.")

                    import httpx

                    best_lap_response = httpx.get(f"{server.base_url}/api/telemetry/{db_snapshot['race_id']}/0/best", timeout=10)
                    best_lap_response.raise_for_status()
                    session_history_response = httpx.get(
                        f"{server.base_url}/api/telemetry/{db_snapshot['race_id']}/session-history",
                        timeout=10,
                    )
                    session_history_response.raise_for_status()
                    live_snapshot_response = httpx.get(f"{server.base_url}/api/live/snapshot", timeout=10)
                    live_snapshot_response.raise_for_status()
                    live_status_response = httpx.get(f"{server.base_url}/api/live/status", timeout=10)
                    live_status_response.raise_for_status()
                    live_data_response = httpx.get(f"{server.base_url}/api/live/data", timeout=10)
                    live_data_response.raise_for_status()

                    ws_status = next(
                        (
                            message
                            for message in ws_messages
                            if message.get("type") == "agent_status" and message.get("track_name")
                        ),
                        None,
                    )
                    ws_live = next(
                        (
                            message
                            for message in ws_messages
                            if message.get("type") == "live_data" and message.get("entries")
                        ),
                        None,
                    )
                    if ws_status is None or ws_live is None:
                        raise AssertionError("Backend websocket relay did not publish both status and live snapshots.")

                    live_snapshot = live_snapshot_response.json()
                    live_status = live_status_response.json()
                    live_data = live_data_response.json()
                    if live_snapshot.get("status") != live_status:
                        raise AssertionError("Live snapshot status endpoint diverged from aggregate snapshot.")
                    if live_snapshot.get("live") != live_data:
                        raise AssertionError("Live data endpoint diverged from aggregate snapshot.")

                    return {
                        "all_passed": True,
                        "server_url": server.base_url,
                        "season_id": season["season_id"],
                        "session_uid": session_uid,
                        "race_id": db_snapshot["race_id"],
                        "udp_port": udp_port,
                        "db_snapshot": db_snapshot,
                        "best_lap": best_lap_response.json(),
                        "session_history": session_history_response.json(),
                        "ws_status": ws_status,
                        "ws_live": ws_live,
                        "live_snapshot": live_snapshot,
                        "live_status": live_status,
                        "live_data": live_data,
                        "raw_log_path": str(raw_log_path),
                        "raw_log_summary": raw_summary,
                        "postmortem_summary": postmortem["summary"],
                        "postmortem_sessions": postmortem["sessions"],
                        "observed_events": observed,
                    }
                finally:
                    ws_done.set()
                    probe_thread.join(timeout=5)
                    agent.shutdown(stop_overlay=False)
    finally:
        if server is not None:
            server.close()
        harness.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live validation against the real backend app + agent pipeline.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args()

    summary = run_live_validation()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("all_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
WebSocket hub for agent status and live race relay.
"""

import copy
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

_MAX_CLIENTS = 100

_agent_connections: dict[str, WebSocket] = {}
_client_connections: list[WebSocket] = []
_last_agent_msg: dict = {}


def _agent_secret() -> str:
    return os.getenv("AGENT_SECRET_TOKEN", "")


def _runtime_dir() -> Path:
    return Path(os.getenv("BACKEND_RUNTIME_DIR", Path.home() / "f1league_backend_runtime"))


def _snapshot_file() -> Path:
    return _runtime_dir() / "live_snapshot.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_persisted_snapshot() -> dict:
    path = _snapshot_file()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _persist_snapshot() -> None:
    snapshot = {
        "status": copy.deepcopy(_last_agent_msg.get("status")),
        "live": copy.deepcopy(_last_agent_msg.get("live")),
        "updated_at": _last_agent_msg.get("updated_at"),
    }
    path = _snapshot_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _clear_persisted_snapshot() -> None:
    path = _snapshot_file()
    if not path.exists():
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _current_snapshot() -> dict:
    snapshot = _load_persisted_snapshot()
    if _last_agent_msg.get("status") is not None:
        snapshot["status"] = copy.deepcopy(_last_agent_msg["status"])
    if _last_agent_msg.get("live") is not None:
        snapshot["live"] = copy.deepcopy(_last_agent_msg["live"])
    if _last_agent_msg.get("updated_at") is not None:
        snapshot["updated_at"] = _last_agent_msg["updated_at"]
    return snapshot


def reset_ws_state(*, clear_persisted: bool = True) -> None:
    _agent_connections.clear()
    _client_connections.clear()
    _last_agent_msg.clear()
    if clear_persisted:
        _clear_persisted_snapshot()


async def _broadcast(payload: dict) -> None:
    dead = []
    for client in _client_connections:
        try:
            await client.send_json(payload)
        except Exception:
            dead.append(client)
    for client in dead:
        if client in _client_connections:
            _client_connections.remove(client)


@router.websocket("/ws/agent")
async def agent_ws(websocket: WebSocket, token: str = ""):
    secret = _agent_secret()
    if secret and not hmac.compare_digest(token, secret):
        await websocket.close(code=4001, reason="Invalid agent token")
        return

    await websocket.accept()
    _agent_connections[token] = websocket
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue

            msg_type = data.get("type", "status")
            if msg_type == "status":
                out = {
                    "type": "agent_status",
                    "state": data.get("state", "IDLE"),
                    "track_name": data.get("track_name"),
                    "label": data.get("label", ""),
                    "track_id": data.get("track_id"),
                }
                _last_agent_msg["status"] = out
                _last_agent_msg["updated_at"] = _now_iso()
                _persist_snapshot()
                await _broadcast(out)
            elif msg_type == "live_data":
                out = {"type": "live_data", "entries": data.get("entries", [])}
                _last_agent_msg["live"] = out
                _last_agent_msg["updated_at"] = _now_iso()
                _persist_snapshot()
                await _broadcast(out)
    except WebSocketDisconnect:
        _agent_connections.pop(token, None)


@router.websocket("/ws/client")
async def client_ws(websocket: WebSocket):
    if len(_client_connections) >= _MAX_CLIENTS:
        await websocket.close(code=4002, reason="Too many connections")
        return

    await websocket.accept()
    _client_connections.append(websocket)

    snapshot = _current_snapshot()
    if snapshot.get("status") is not None:
        await websocket.send_json(snapshot["status"])
    if snapshot.get("live") is not None:
        await websocket.send_json(snapshot["live"])

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _client_connections:
            _client_connections.remove(websocket)


@router.get("/api/live/snapshot")
async def get_live_snapshot():
    snapshot = _current_snapshot()
    return {
        "status": snapshot.get("status"),
        "live": snapshot.get("live"),
        "updated_at": snapshot.get("updated_at"),
    }


@router.get("/api/live/status")
async def get_live_status():
    status = _current_snapshot().get("status")
    if status is None:
        raise HTTPException(404, "No agent status available")
    return status


@router.get("/api/live/data")
async def get_live_data():
    live = _current_snapshot().get("live")
    if live is None:
        raise HTTPException(404, "No live data available")
    return live

from __future__ import annotations

"""
F1 League Agent Launcher.

pywebview-based control center for:
- authentication
- agent lifecycle
- lobby management
- overlay/HUD configuration
- diagnostics and operator tooling
"""

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
import webview


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    os.chdir(BASE_DIR)
else:
    BASE_DIR = Path(__file__).parent

UI_DIR = BASE_DIR / "launcher_ui"
CONFIG_DIR = Path.home() / "f1league_agent"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "launcher_config.json"


DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_FRONTEND_URL = "http://localhost:3000"
DEFAULT_WS_URL = "ws://localhost:8000/ws/agent"
DEFAULT_UDP_PORT = "20777"
RECENT_EVENT_LIMIT = 60
PENDING_UPLOAD_PREVIEW = 6
WIDGET_KEYS = ["timing", "session", "delta", "speed", "pedals", "tyres", "ers", "engineer"]


DEFAULT_CONFIG = {
    "server_url": DEFAULT_SERVER_URL,
    "frontend_url": DEFAULT_FRONTEND_URL,
    "ws_url": DEFAULT_WS_URL,
    "season_id": "1",
    "udp_port": DEFAULT_UDP_PORT,
    "agent_mode": "personal",
    "overlay_enabled": False,
    "overlay_opacity": 85,
    "widgets": [True] * len(WIDGET_KEYS),
    "widget_positions": None,
}


def _normalize_http_url(url: str | None, fallback: str) -> str:
    raw = (url or fallback).strip()
    if not raw:
        raw = fallback
    if "://" not in raw:
        raw = f"http://{raw}"

    parsed = urlparse(raw)
    try:
        parsed.port
    except ValueError:
        return fallback
    scheme = parsed.scheme or urlparse(fallback).scheme or "http"
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    normalized = urlunparse((scheme, netloc.rstrip("/"), path.rstrip("/"), "", "", ""))
    return normalized.rstrip("/")


def _normalize_ws_url(url: str | None, fallback: str) -> str:
    raw = (url or fallback).strip()
    if not raw:
        raw = fallback
    if "://" not in raw:
        raw = f"ws://{raw}"

    parsed = urlparse(raw)
    try:
        parsed.port
    except ValueError:
        return fallback
    scheme = parsed.scheme or urlparse(fallback).scheme or "ws"
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    if not path:
        path = "/ws/agent"
    normalized = urlunparse((scheme, netloc.rstrip("/"), path.rstrip("/"), "", "", ""))
    return normalized.rstrip("/")


def _normalize_udp_port(value, fallback: str = DEFAULT_UDP_PORT, strict: bool = False) -> str:
    raw = str(value if value is not None else fallback).strip()
    if not raw:
        raw = fallback

    try:
        port = int(raw)
    except (TypeError, ValueError):
        if strict:
            raise ValueError("UDP-порт должен быть числом от 1 до 65535.")
        return fallback

    if not 1 <= port <= 65535:
        if strict:
            raise ValueError("UDP-порт должен быть числом от 1 до 65535.")
        return fallback

    return str(port)


def _validate_url_input(url: str | None, label: str, ws: bool = False) -> None:
    raw = (url or "").strip()
    if not raw:
        return
    if "://" not in raw:
        raw = f"{'ws' if ws else 'http'}://{raw}"

    parsed = urlparse(raw)
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError(f"URL для {label} содержит некорректный порт.") from exc


def _derive_urls(server_url: str) -> dict:
    server_url = _normalize_http_url(server_url, DEFAULT_SERVER_URL)
    parsed = urlparse(server_url)
    host = parsed.hostname or "localhost"
    scheme = parsed.scheme or "http"
    ws_scheme = "wss" if scheme == "https" else "ws"

    try:
        backend_port = parsed.port
    except ValueError:
        backend_port = urlparse(DEFAULT_SERVER_URL).port
    frontend_port = 3000
    if backend_port not in (None, 8000):
        frontend_port = backend_port

    frontend_netloc = host
    if frontend_port not in (80, 443):
        frontend_netloc = f"{host}:{frontend_port}"
    frontend_scheme = "https" if scheme == "https" and frontend_port == 443 else "http"
    frontend_url = f"{frontend_scheme}://{frontend_netloc}"

    ws_netloc = host
    if backend_port:
        ws_netloc = f"{host}:{backend_port}"
    ws_url = f"{ws_scheme}://{ws_netloc}/ws/agent"

    return {
        "server_url": server_url,
        "frontend_url": frontend_url,
        "ws_url": ws_url,
    }


def _normalize_widget_positions(positions) -> list[dict] | None:
    if not positions:
        return None
    normalized = []
    for pos in positions[: len(WIDGET_KEYS)]:
        if not isinstance(pos, dict):
            normalized.append({"x": 0, "y": 0})
            continue
        try:
            x = float(pos.get("x", 0))
            y = float(pos.get("y", 0))
        except (TypeError, ValueError):
            x = 0
            y = 0
        normalized.append({
            "x": round(max(0.0, min(100.0, x)), 1),
            "y": round(max(0.0, min(100.0, y)), 1),
        })
    return normalized


def _normalize_config(cfg: dict | None) -> dict:
    merged = {**DEFAULT_CONFIG, **(cfg or {})}
    derived = _derive_urls(merged.get("server_url"))

    merged["server_url"] = _normalize_http_url(merged.get("server_url"), DEFAULT_SERVER_URL)
    merged["frontend_url"] = _normalize_http_url(
        merged.get("frontend_url") or derived["frontend_url"],
        derived["frontend_url"],
    )
    merged["ws_url"] = _normalize_ws_url(
        merged.get("ws_url") or derived["ws_url"],
        derived["ws_url"],
    )
    merged["season_id"] = str(merged.get("season_id", "1") or "1")
    merged["udp_port"] = _normalize_udp_port(merged.get("udp_port"), DEFAULT_UDP_PORT)
    merged["agent_mode"] = merged.get("agent_mode", "personal") if merged.get("agent_mode") in {"personal", "lobby"} else "personal"
    merged["overlay_enabled"] = bool(merged.get("overlay_enabled", False))
    merged["overlay_opacity"] = max(20, min(100, int(merged.get("overlay_opacity", 85) or 85)))

    widgets = merged.get("widgets")
    if not isinstance(widgets, list):
        widgets = [True] * len(WIDGET_KEYS)
    widgets = [bool(v) for v in widgets[: len(WIDGET_KEYS)]]
    while len(widgets) < len(WIDGET_KEYS):
        widgets.append(True)
    merged["widgets"] = widgets
    merged["widget_positions"] = _normalize_widget_positions(merged.get("widget_positions"))
    return merged


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            normalized = _normalize_config(raw)
            if normalized != raw:
                save_config_file(normalized)
            return normalized
        except Exception:
            pass
    default_config = _normalize_config(DEFAULT_CONFIG)
    save_config_file(default_config)
    return default_config


def save_config_file(cfg: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(_normalize_config(cfg), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fmt_lap(ms) -> str:
    if not ms or ms <= 0:
        return "-"
    mins = int(ms // 60000)
    secs = (ms % 60000) / 1000
    return f"{mins}:{secs:06.3f}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _friendly_error(error) -> str | None:
    if error is None:
        return None

    raw = str(error).strip()
    if not raw:
        return None

    lowered = raw.lower()
    if "only one usage of each socket address" in lowered or "address already in use" in lowered:
        return "Порт уже занят другим процессом."
    if "unpack_udp_packet" in raw and "f1.packets" in raw:
        return "Установленный пакет f1-packets не совпадает с версией парсера, которую ожидает этот билд лаунчера."
    if "websockets" in lowered and "not installed" in lowered:
        return "Python-пакет 'websockets' не установлен."
    return raw


def _safe_console_text(error) -> str:
    return str(error).encode("ascii", "backslashreplace").decode("ascii")


class LauncherAPI:
    def __init__(self):
        self.config = load_config()
        self.token: str | None = self.config.get("auth_token")
        self.user: dict | None = None
        self.agent_running = False
        self.agent_instance = None
        self.agent_thread: threading.Thread | None = None
        self._window: webview.Window | None = None
        self._overlay_server = None
        self._agent_error: str | None = None
        self._agent_started_at: float | None = None
        self._pending_retry_running = False
        self._recent_events = deque(maxlen=RECENT_EVENT_LIMIT)

        now = _now_iso()
        overlay_enabled = bool(self.config.get("overlay_enabled"))
        self._lifecycle = {
            "phase": "stopped",
            "status": "Остановлен",
            "label": "Лаунчер готов",
            "updated_at": now,
        }
        self._components = {
            "startup": {"state": "idle", "message": "Лаунчер готов", "updated_at": now, "last_error": None},
            "udp": {"state": "idle", "message": "Ожидание запуска агента", "updated_at": now, "last_error": None},
            "ws": {"state": "idle", "message": "Ожидание запуска агента", "updated_at": now, "last_error": None},
            "upload": {"state": "idle", "message": "Проверка отложенных загрузок", "updated_at": now, "last_error": None},
            "telemetry": {"state": "idle", "message": "Проверка очереди telemetry", "updated_at": now, "last_error": None},
            "overlay": {
                "state": "stopped" if overlay_enabled else "disabled",
                "message": "Оверлей готов, но не запущен" if overlay_enabled else "Автозапуск оверлея отключён",
                "updated_at": now,
                "last_error": None,
            },
        }
        self._refresh_upload_component()
        self._refresh_telemetry_component()

    def _record_event(self, level: str, source: str, message: str, detail: str | None = None, data: dict | None = None) -> None:
        self._recent_events.appendleft({
            "at": _now_iso(),
            "level": level,
            "source": source,
            "message": message,
            "detail": detail,
            "data": data or {},
        })

    def _set_lifecycle(self, phase: str, status: str, label: str, record_event: bool = False, level: str = "info") -> None:
        self._lifecycle = {
            "phase": phase,
            "status": status,
            "label": label,
            "updated_at": _now_iso(),
        }
        if record_event:
            self._record_event(level, "startup", status, label)

    def _set_component_state(
        self,
        name: str,
        state: str,
        message: str,
        *,
        error=None,
        clear_error: bool = False,
        record_event: bool = False,
        level: str | None = None,
        **extra,
    ) -> dict:
        current = dict(self._components.get(name, {}))
        updated = {
            **current,
            **extra,
            "state": state,
            "message": message,
            "updated_at": _now_iso(),
        }

        if clear_error:
            updated["last_error"] = None
        elif error is not None:
            updated["last_error"] = {"message": _friendly_error(error), "at": _now_iso()}
        else:
            updated["last_error"] = current.get("last_error")

        self._components[name] = updated

        if record_event:
            detail = updated["last_error"]["message"] if error is not None and updated.get("last_error") else None
            self._record_event(level or ("error" if error else "info"), name, message, detail, data=extra or None)

        return updated

    def _component_snapshot(self) -> dict:
        return {name: dict(value) for name, value in self._components.items()}

    def _pending_uploads_snapshot(self, limit: int = PENDING_UPLOAD_PREVIEW) -> dict:
        try:
            from agent import local_cache
            from shared.f1_mappings import get_track_name

            pending = list(local_cache.load_all())
        except Exception as exc:
            return {"count": 0, "entries": [], "error": _friendly_error(exc)}

        entries = []
        payloads = [] if limit <= 0 else list(reversed(pending[-limit:]))
        for entry in payloads:
            payload = local_cache.get_payload(entry)
            track_id = payload.get("track_id") or 0
            entries.append({
                "session_uid": payload.get("session_uid"),
                "season_id": payload.get("season_id"),
                "track_name": get_track_name(track_id) if track_id else "Неизвестная трасса",
                "saved_at": entry.get("saved_at"),
                "last_attempt_at": entry.get("last_attempt_at"),
                "attempt_count": entry.get("attempt_count", 0),
                "last_error": entry.get("last_error"),
                "last_outcome": entry.get("last_outcome"),
                "participants_count": len(payload.get("participants") or []),
                "total_laps": payload.get("total_laps"),
            })

        return {
            "count": len(pending),
            "entries": entries,
            "error": None,
        }

    def _pending_telemetry_snapshot(self, limit: int = PENDING_UPLOAD_PREVIEW) -> dict:
        try:
            from agent import telemetry_delivery

            pending = list(telemetry_delivery.load_all())
        except Exception as exc:
            return {
                "count": 0,
                "entries": [],
                "ready_to_flush": 0,
                "waiting_for_race_id": 0,
                "error": _friendly_error(exc),
            }

        entries = []
        payloads = [] if limit <= 0 else list(reversed(pending[-limit:]))
        ready_to_flush = 0
        waiting_for_race_id = 0
        for entry in pending:
            if entry.get("race_id"):
                ready_to_flush += 1
            else:
                waiting_for_race_id += 1

        for entry in payloads:
            snapshot = entry.get("snapshot") or {}
            laps = [lap for lap in snapshot.get("laps", []) if isinstance(lap, dict)]
            session_history = [item for item in snapshot.get("session_history", []) if isinstance(item, dict)]
            sample_count = sum(len(lap.get("samples") or []) for lap in laps)
            entries.append({
                "session_uid": entry.get("session_uid"),
                "race_id": entry.get("race_id"),
                "saved_at": entry.get("saved_at"),
                "updated_at": entry.get("updated_at"),
                "last_attempt_at": entry.get("last_attempt_at"),
                "attempt_count": entry.get("attempt_count", 0),
                "last_error": entry.get("last_error"),
                "last_outcome": entry.get("last_outcome"),
                "lap_count": len(laps),
                "sample_count": sample_count,
                "vehicle_history_count": len(session_history),
                "waiting_for_race_id": not bool(entry.get("race_id")),
            })

        return {
            "count": len(pending),
            "entries": entries,
            "ready_to_flush": ready_to_flush,
            "waiting_for_race_id": waiting_for_race_id,
            "error": None,
        }

    def _pending_delivery_snapshot(self, limit: int = PENDING_UPLOAD_PREVIEW) -> dict:
        upload = self._pending_uploads_snapshot(limit=limit)
        telemetry = self._pending_telemetry_snapshot(limit=limit)
        return {
            "count": upload.get("count", 0) + telemetry.get("count", 0),
            "pending_uploads": upload.get("count", 0),
            "pending_telemetry": telemetry.get("count", 0),
            "telemetry_ready_to_flush": telemetry.get("ready_to_flush", 0),
            "telemetry_waiting_for_race_id": telemetry.get("waiting_for_race_id", 0),
            "errors": [error for error in [upload.get("error"), telemetry.get("error")] if error],
        }

    def _refresh_upload_component(self, log_event: bool = False) -> dict:
        snapshot = self._pending_uploads_snapshot()
        if snapshot.get("error"):
            return self._set_component_state(
                "upload",
                "error",
                "Не удалось прочитать кеш отложенных загрузок",
                error=snapshot["error"],
                record_event=log_event,
                entries=[],
                pending_uploads=0,
                retry_running=self._pending_retry_running,
            )

        count = snapshot["count"]
        if self._pending_retry_running:
            return self._set_component_state(
                "upload",
                "retrying",
                f"Повторная загрузка {count} сохранённых пакетов",
                record_event=log_event,
                entries=snapshot["entries"],
                pending_uploads=count,
                retry_running=True,
            )
        if count:
            return self._set_component_state(
                "upload",
                "pending",
                f"{count} сохранённых пакетов ждут восстановления backend",
                record_event=log_event,
                entries=snapshot["entries"],
                pending_uploads=count,
                retry_running=False,
            )
        return self._set_component_state(
            "upload",
            "ready",
            "Нет отложенных загрузок",
            clear_error=True,
            record_event=log_event,
            entries=[],
            pending_uploads=0,
            retry_running=False,
        )

    def _refresh_telemetry_component(self, log_event: bool = False) -> dict:
        snapshot = self._pending_telemetry_snapshot()
        if snapshot.get("error"):
            return self._set_component_state(
                "telemetry",
                "error",
                "Не удалось прочитать очередь telemetry",
                error=snapshot["error"],
                record_event=log_event,
                entries=[],
                pending_telemetry=0,
                ready_to_flush=0,
                waiting_for_race_id=0,
                retry_running=self._pending_retry_running,
            )

        count = snapshot["count"]
        ready_to_flush = snapshot["ready_to_flush"]
        waiting_for_race_id = snapshot["waiting_for_race_id"]

        if self._pending_retry_running and count:
            return self._set_component_state(
                "telemetry",
                "retrying",
                f"Повторная доставка {count} telemetry-снимков",
                record_event=log_event,
                entries=snapshot["entries"],
                pending_telemetry=count,
                ready_to_flush=ready_to_flush,
                waiting_for_race_id=waiting_for_race_id,
                retry_running=True,
            )

        if count:
            if ready_to_flush and waiting_for_race_id:
                message = (
                    f"{count} telemetry-снимков буферизовано "
                    f"({ready_to_flush} готовы к доставке, {waiting_for_race_id} ждут race_id)"
                )
            elif ready_to_flush:
                message = f"{count} telemetry-снимков ждут повтора flush на backend"
            else:
                message = f"{count} telemetry-снимков ждут race_id от загруженной гонки"

            return self._set_component_state(
                "telemetry",
                "pending",
                message,
                record_event=log_event,
                entries=snapshot["entries"],
                pending_telemetry=count,
                ready_to_flush=ready_to_flush,
                waiting_for_race_id=waiting_for_race_id,
                retry_running=False,
            )

        return self._set_component_state(
            "telemetry",
            "ready",
            "Очередь telemetry flush пустая",
            clear_error=True,
            record_event=log_event,
            entries=[],
            pending_telemetry=0,
            ready_to_flush=0,
            waiting_for_race_id=0,
            retry_running=False,
        )

    def _observe_runtime_event(self, source: str, event: str, payload: dict | None = None) -> None:
        payload = payload or {}

        if source == "ws":
            if event in {"starting", "connecting"}:
                delay = payload.get("retry_delay_s")
                message = "Подключение websocket агента к backend"
                if delay:
                    message = f"Подключение websocket агента к backend (повтор через {delay} c при необходимости)"
                self._set_component_state("ws", "connecting", message, url=payload.get("url") or self.websocket_url)
            elif event == "connected":
                self._set_component_state(
                    "ws",
                    "connected",
                    "WebSocket агента подключён",
                    clear_error=True,
                    record_event=True,
                    url=payload.get("url") or self.websocket_url,
                )
            elif event in {"connect_failed", "send_failed"}:
                action = "Ошибка подключения WebSocket" if event == "connect_failed" else "Ошибка отправки по WebSocket"
                self._set_component_state(
                    "ws",
                    "error",
                    action,
                    error=payload.get("error"),
                    record_event=True,
                    level="warn",
                    retry_delay_s=payload.get("retry_delay_s"),
                    url=payload.get("url") or self.websocket_url,
                )
            elif event == "unavailable":
                self._set_component_state("ws", "error", "Поддержка WebSocket недоступна", error=payload.get("error"), record_event=True)
            elif event in {"stopping", "stopped"}:
                self._set_component_state("ws", "stopped", "WebSocket агента остановлен")

        elif source == "udp":
            if event == "starting":
                self._set_component_state(
                    "udp",
                    "starting",
                    f"Привязка UDP-слушателя на {payload.get('host')}:{payload.get('port')}",
                    host=payload.get("host"),
                    port=payload.get("port"),
                )
            elif event == "listening":
                self._set_component_state(
                    "udp",
                    "listening",
                    f"Слушаем F1-телеметрию на {payload.get('host')}:{payload.get('port')}",
                    clear_error=True,
                    record_event=True,
                    host=payload.get("host"),
                    port=payload.get("port"),
                )
                if self._lifecycle["phase"] == "starting":
                    self._set_component_state("startup", "ready", "Runtime агента в сети", clear_error=True, record_event=True)
                    self._set_lifecycle("running", "Запущен", "Телеметрический агент готов и ждёт пакеты")
            elif event == "first_packet":
                self._set_component_state(
                    "udp",
                    "receiving",
                    "Пакеты телеметрии поступают",
                    host=payload.get("host"),
                    port=payload.get("port"),
                    packets_received=payload.get("packets_received"),
                )
                self._record_event("info", "udp", "Получен первый пакет телеметрии")
            elif event in {"bind_failed", "receive_failed", "callback_failed"}:
                self._set_component_state(
                    "udp",
                    "error",
                    "UDP-слушатель сообщил об ошибке",
                    error=payload.get("error"),
                    record_event=True,
                    host=payload.get("host"),
                    port=payload.get("port"),
                    packet_id=payload.get("packet_id"),
                )
                if event == "bind_failed":
                    self._abort_agent_runtime(
                        "Ошибка запуска",
                        "UDP-слушатель не смог привязаться к настроенному порту телеметрии",
                        payload.get("error"),
                    )
            elif event == "stopped":
                self._set_component_state(
                    "udp",
                    "stopped",
                    "UDP-слушатель остановлен",
                    host=payload.get("host"),
                    port=payload.get("port"),
                    packets_received=payload.get("packets_received"),
                )

        elif source == "overlay":
            if event == "starting":
                self._set_component_state("overlay", "starting", "Запуск браузерных сервисов оверлея")
            elif event in {"http_ready", "ws_ready"}:
                phase = "starting"
                message = "Сервисы оверлея поднимаются"
                if self._overlay_server and getattr(self._overlay_server, "http_ready", False) and getattr(self._overlay_server, "ws_ready", False):
                    phase = "running"
                    message = "Браузерная точка оверлея запущена"
                self._set_component_state("overlay", phase, message)
            elif event == "running":
                self._set_component_state(
                    "overlay",
                    "running",
                    "Браузерная точка оверлея запущена",
                    clear_error=True,
                    record_event=True,
                )
            elif event in {"http_error", "ws_error", "unavailable"}:
                self._set_component_state(
                    "overlay",
                    "error",
                    "Сервис оверлея завершился ошибкой",
                    error=payload.get("error"),
                    record_event=True,
                    level="warn",
                )
            elif event == "stopping":
                self._set_component_state("overlay", "stopping", "Остановка сервисов оверлея")
            elif event == "stopped":
                state = "stopped" if self.config.get("overlay_enabled") else "disabled"
                message = "Оверлей готов, но не запущен" if self.config.get("overlay_enabled") else "Автозапуск оверлея отключён"
                self._set_component_state("overlay", state, message)
            elif event in {"client_connected", "client_disconnected"}:
                self._set_component_state(
                    "overlay",
                    "running",
                    "Браузерная точка оверлея запущена",
                    clients=payload.get("clients", 0),
                )

        elif source == "upload":
            if event == "retry_scan_complete":
                self._refresh_upload_component()
            elif event in {"retry_queue_loaded", "retrying_cached", "attempt", "retry_scheduled"}:
                count = payload.get("pending_uploads", self._pending_uploads_count())
                self._set_component_state(
                    "upload",
                    "retrying",
                    f"Повторная загрузка сохранённых пакетов ({count} ожидают)",
                    entries=self._pending_uploads_snapshot()["entries"],
                    pending_uploads=count,
                    retry_running=self._pending_retry_running,
                )
            elif event == "cached":
                count = payload.get("pending_uploads", self._pending_uploads_count())
                self._set_component_state(
                    "upload",
                    "pending",
                    f"Гонка сохранена локально для безопасного повтора ({count} ожидают)",
                    record_event=True,
                    entries=self._pending_uploads_snapshot()["entries"],
                    pending_uploads=count,
                    retry_running=self._pending_retry_running,
                )
            elif event == "succeeded":
                self._record_event(
                    "success",
                    "upload",
                    "Сохранённая загрузка успешно доставлена",
                    data={"session_uid": payload.get("session_uid"), "race_id": payload.get("race_id")},
                )
                self._refresh_upload_component()
            elif event in {"attempt_failed", "exhausted", "retry_deferred", "missing_participants"}:
                count = payload.get("pending_uploads", self._pending_uploads_count())
                self._set_component_state(
                    "upload",
                    "error" if event != "retry_deferred" else "pending",
                    "Повторная загрузка не удалась; гонка остаётся сохранённой локально",
                    error=payload.get("error"),
                    record_event=True,
                    level="warn",
                    entries=self._pending_uploads_snapshot()["entries"],
                    pending_uploads=count,
                    retry_running=self._pending_retry_running,
                    session_uid=payload.get("session_uid"),
                    track_name=payload.get("track_name"),
                )
            self._refresh_upload_component()

        elif source == "telemetry":
            if event == "retry_scan_complete":
                self._refresh_telemetry_component()
            elif event in {"attempt", "retry_scheduled"}:
                snapshot = self._pending_telemetry_snapshot()
                count = payload.get("pending_flushes", snapshot.get("count", 0))
                self._set_component_state(
                    "telemetry",
                    "retrying",
                    f"Повторная доставка telemetry ({count} ожидают)",
                    entries=snapshot["entries"],
                    pending_telemetry=count,
                    ready_to_flush=snapshot.get("ready_to_flush", 0),
                    waiting_for_race_id=snapshot.get("waiting_for_race_id", 0),
                    retry_running=self._pending_retry_running,
                )
            elif event == "succeeded":
                self._record_event(
                    "success",
                    "telemetry",
                    "Telemetry успешно доставлена",
                    data={"session_uid": payload.get("session_uid"), "race_id": payload.get("race_id")},
                )
            elif event == "blocked_no_race_id":
                snapshot = self._pending_telemetry_snapshot()
                self._set_component_state(
                    "telemetry",
                    "pending",
                    "Telemetry ждёт race_id от результата гонки",
                    error=payload.get("error"),
                    record_event=bool(payload.get("error")),
                    level="warn",
                    entries=snapshot["entries"],
                    pending_telemetry=snapshot.get("count", 0),
                    ready_to_flush=snapshot.get("ready_to_flush", 0),
                    waiting_for_race_id=snapshot.get("waiting_for_race_id", 0),
                    retry_running=self._pending_retry_running,
                )
            elif event in {"attempt_failed", "exhausted"}:
                snapshot = self._pending_telemetry_snapshot()
                self._set_component_state(
                    "telemetry",
                    "error",
                    "Повторная доставка telemetry не удалась; снимок остаётся локально",
                    error=payload.get("error"),
                    record_event=True,
                    level="warn",
                    entries=snapshot["entries"],
                    pending_telemetry=snapshot.get("count", 0),
                    ready_to_flush=snapshot.get("ready_to_flush", 0),
                    waiting_for_race_id=snapshot.get("waiting_for_race_id", 0),
                    retry_running=self._pending_retry_running,
                )
            self._refresh_telemetry_component()

        elif source == "personal_session":
            if event == "succeeded":
                self._record_event(
                    "success",
                    "profile",
                    "Личная сессия сохранена в историю",
                    data={
                        "session_uid": payload.get("session_uid"),
                        "session_id": payload.get("session_id"),
                        "track_name": payload.get("track_name"),
                        "session_type": payload.get("session_type"),
                    },
                )
            elif event == "failed":
                self._record_event(
                    "warn",
                    "profile",
                    "Не удалось сохранить личную сессию в историю",
                    payload.get("error"),
                    data={
                        "session_uid": payload.get("session_uid"),
                        "track_name": payload.get("track_name"),
                        "session_type": payload.get("session_type"),
                    },
                )

        elif source == "agent":
            if event == "state_changed":
                self._record_event("info", "agent", f"Состояние агента изменилось на {payload.get('state')}", payload.get("label"))
            elif event == "track_detected":
                self._record_event("info", "agent", "Трасса определена", payload.get("track_name"))
            elif event == "final_classification_received":
                self._record_event("info", "agent", "Получена финальная классификация; загрузка запущена")
            elif event == "session_reset":
                self._record_event("info", "agent", "Сессия агента сброшена и готова к следующей гонке")

    def _build_recovery_actions(self, diagnostics: dict) -> list[dict]:
        actions: list[dict] = []
        cache = diagnostics.get("cache", {})
        components = diagnostics.get("components", {})
        agent = diagnostics.get("agent", {})

        if not diagnostics.get("backend", {}).get("ok"):
            actions.append({
                "severity": "error",
                "title": "Backend недоступен",
                "summary": f"Лаунчер не может достучаться до {self.base_url}. Загрузки останутся локальными, пока backend не вернётся.",
                "action": "Запусти backend-стек или исправь Backend URL в настройках, затем повтори отложенные загрузки или перезапусти агента.",
            })

        if not diagnostics.get("frontend", {}).get("ok"):
            actions.append({
                "severity": "warn",
                "title": "Frontend недоступен",
                "summary": "Ссылки на сайт и вход через браузер могут не работать, но локальный захват агента всё ещё возможен, если backend доступен.",
                "action": "Подними frontend на настроенном Frontend URL или продолжай работу только из интерфейса лаунчера.",
            })

        startup_error = ((components.get("startup") or {}).get("last_error") or {}).get("message")
        if startup_error or agent.get("state") == "error":
            actions.append({
                "severity": "error",
                "title": "Не удалось запустить агента",
                "summary": startup_error or agent.get("error") or "Агент остановился во время запуска.",
                "action": "Исправь блокирующую ошибку ниже и затем запусти агента снова. Неудачный запуск не удаляет сохранённые гоночные данные.",
            })

        ws_error = ((components.get("ws") or {}).get("last_error") or {}).get("message")
        if ws_error:
            actions.append({
                "severity": "warn",
                "title": "Связь по WebSocket нарушена",
                "summary": ws_error,
                "action": "Проверь backend URL и маршрут websocket. Захват сессии может продолжаться локально; после восстановления backend перезапусти агента, если live-статус не вернулся.",
            })

        if cache.get("pending_uploads"):
            actions.append({
                "severity": "warn",
                "title": "Отложенные загрузки безопасно лежат на диске",
                "summary": f"{cache['pending_uploads']} гонок сохранено в {CONFIG_DIR}. Они не потеряны.",
                "action": "Верни backend в онлайн, затем используй повтор отложенных загрузок или перезапусти агента, чтобы отправить их заново.",
            })

        pending_telemetry = cache.get("pending_telemetry", 0)
        if pending_telemetry:
            waiting_for_race_id = cache.get("telemetry_waiting_for_race_id", 0)
            ready_to_flush = cache.get("telemetry_ready_to_flush", 0)
            if waiting_for_race_id and not ready_to_flush:
                actions.append({
                    "severity": "warn",
                    "title": "Telemetry ждёт race_id",
                    "summary": f"{waiting_for_race_id} telemetry-снимков сохранено локально, но они ещё не привязаны к race_id.",
                    "action": "Проверь результат загрузки гонки для этого session_uid. Если запись гонки не появилась на backend, используй raw log и replay harness для восстановления цепочки.",
                })
            else:
                actions.append({
                    "severity": "warn",
                    "title": "Telemetry flush ждёт повтора",
                    "summary": f"{pending_telemetry} telemetry-снимков лежат в локальном буфере ({ready_to_flush} готовы к отправке, {waiting_for_race_id} ждут race_id).",
                    "action": "После восстановления backend запусти ручной повтор отложенной доставки или перезапусти агента, чтобы догрузить telemetry.",
                })

        overlay_error = ((components.get("overlay") or {}).get("last_error") or {}).get("message")
        if overlay_error:
            actions.append({
                "severity": "warn",
                "title": "Не удалось запустить оверлей",
                "summary": overlay_error,
                "action": "Закрой процесс, занимающий порты 8080/8081, или отключи автозапуск оверлея. Захват гонки продолжит работать и без оверлея.",
            })

        if not actions:
            actions.append({
                "severity": "ok",
                "title": "Блокирующих проблем не найдено",
                "summary": "Диагностика лаунчера сейчас не видит блокеров по запуску, websocket, загрузке или оверлею.",
                "action": "Если проблема проявляется не всегда, воспроизведи её ещё раз и сразу открой раздел «Недавние события».",
            })

        return actions[:5]

    def _abort_agent_runtime(self, status: str, label: str, error=None) -> None:
        self._agent_error = _friendly_error(error) or str(error or label)
        self._set_component_state("startup", "error", status, error=self._agent_error, record_event=True)
        self._set_lifecycle("error", status, label, record_event=True, level="error")
        self.agent_running = False
        if self.agent_instance:
            try:
                self.agent_instance.shutdown()
            except Exception:
                pass

    @property
    def base_url(self) -> str:
        return self.config["server_url"]

    @property
    def frontend_url(self) -> str:
        return self.config["frontend_url"]

    @property
    def websocket_url(self) -> str:
        return self.config["ws_url"]

    def _headers(self, auth: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, body: dict | None = None, auth: bool = True, timeout: int = 10):
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            json=body,
            headers=self._headers(auth=auth),
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _get(self, path: str, auth: bool = True, timeout: int = 10):
        return self._request("GET", path, auth=auth, timeout=timeout)

    def _post(self, path: str, body: dict | None = None, auth: bool = True, timeout: int = 10):
        return self._request("POST", path, body=body, auth=auth, timeout=timeout)

    def _persist_session(self, data: dict) -> dict:
        self.token = data.get("token")
        self.user = data
        self.config["auth_token"] = self.token
        self.config["user_id"] = data.get("id")
        save_config_file(self.config)
        return data

    def _clear_session(self) -> None:
        self.token = None
        self.user = None
        self.config.pop("auth_token", None)
        self.config.pop("user_id", None)
        save_config_file(self.config)

    def _pending_uploads_count(self) -> int:
        return self._pending_uploads_snapshot(limit=0)["count"]

    def _pending_telemetry_count(self) -> int:
        return self._pending_telemetry_snapshot(limit=0)["count"]

    def _ensure_overlay_server(self):
        if self.agent_instance:
            if self._overlay_server and self.agent_instance._overlay is not self._overlay_server:
                self.agent_instance._overlay = self._overlay_server
            self._overlay_server = self.agent_instance._overlay
            return self._overlay_server

        if not self._overlay_server:
            from agent.overlay_server import OverlayServer

            self._overlay_server = OverlayServer(observer=lambda event, payload=None: self._observe_runtime_event("overlay", event, payload or {}))
        return self._overlay_server

    def _telemetry_snapshot(self) -> dict:
        if not self.agent_instance:
            return {}

        agent = self.agent_instance
        live = dict(getattr(agent, "_live_data", {}).get(0, {}) or {})
        telem = dict(getattr(getattr(agent, "_telem", None), "_latest", {}).get(0, {}) or {})
        snapshot = {**live}
        snapshot.update({
            "speed": telem.get("spd"),
            "throttle": telem.get("thr"),
            "brake": telem.get("brk"),
            "gear": telem.get("gear"),
            "drs": telem.get("drs"),
            "fuel": telem.get("fuel"),
            "fuel_laps": telem.get("fuel_laps"),
            "ers_store": telem.get("ers_store"),
            "tyre_wear_avg": telem.get("tyre_wear"),
        })
        return snapshot

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> dict:
        try:
            response = httpx.post(
                f"{self.base_url}/api/web/launcher/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            if response.status_code == 401:
                return {"error": "Неверный email или пароль."}
            if response.status_code >= 400:
                return {"error": f"Ошибка сервера: HTTP {response.status_code}"}
            return self._persist_session(response.json())
        except httpx.ConnectError:
            return {"error": f"Не удалось подключиться к backend: {self.base_url}"}
        except Exception as exc:
            return {"error": f"Не удалось выполнить вход: {exc}"}

    def auto_login(self) -> dict | None:
        if not self.token:
            return None
        try:
            data = self._get("/api/web/me/by-token", auth=True, timeout=8)
            self.user = data
            return data
        except Exception:
            self._clear_session()
            return None

    def logout(self) -> dict:
        self._clear_session()
        return {"ok": True}

    def start_google_login(self) -> dict:
        try:
            import uuid

            poll_id = str(uuid.uuid4())[:8]
            login_url = f"{self.frontend_url}/login?launcher={poll_id}"
            webbrowser.open(login_url)
            return {"url": login_url, "poll_id": poll_id}
        except Exception as exc:
            return {"error": f"Не удалось открыть браузер: {exc}"}

    def check_google_login(self, poll_id: str) -> dict | None:
        try:
            response = httpx.get(
                f"{self.base_url}/api/web/launcher/poll/{poll_id}",
                timeout=5,
            )
            if response.status_code != 200:
                return None
            data = response.json()
            if data.get("token"):
                return self._persist_session(data)
        except Exception:
            pass
        return None

    def open_website(self, path: str = "") -> dict:
        try:
            url = f"{self.frontend_url}{path}" if path else self.frontend_url
            webbrowser.open(url)
            return {"ok": True, "url": url}
        except Exception as exc:
            return {"error": f"Не удалось открыть браузер: {exc}"}

    # ------------------------------------------------------------------
    # Lobbies
    # ------------------------------------------------------------------

    def get_lobbies(self) -> list:
        try:
            lobbies = self._get("/api/lobby")
            return [
                {
                    "id": lb.get("id"),
                    "name": lb.get("name", ""),
                    "description": lb.get("description", ""),
                    "member_count": lb.get("members", 0),
                    "seasons_count": lb.get("seasons", 0),
                    "role": lb.get("your_role", lb.get("role", "member")),
                }
                for lb in lobbies
            ]
        except Exception:
            return []

    def get_lobby(self, lobby_id: int) -> dict:
        data = self._get(f"/api/lobby/{lobby_id}")
        invite_code = data.get("invite_code") or ""
        invite_link = f"{self.frontend_url}/lobby/join?code={invite_code}" if invite_code else ""
        return {
            "id": data.get("id"),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "role": data.get("your_role", "member"),
            "invite_code": invite_code,
            "invite_link": invite_link,
            "members_count": data.get("members_count", 0),
            "creator_name": data.get("creator_name"),
            "can_manage": bool(data.get("can_manage", False)),
            "can_create_season": bool(data.get("can_create_season", False)),
            "can_reset_invite": bool(data.get("can_reset_invite", False)),
        }

    def get_host_seasons(self) -> list:
        try:
            seasons = self._get("/api/lobby/host-seasons")
            return [
                {
                    "id": season.get("id"),
                    "name": season.get("name", ""),
                    "status": season.get("status", "active"),
                    "races_count": season.get("races_played", 0),
                    "total_rounds": season.get("total_rounds", 0),
                    "created_at": season.get("created_at"),
                    "lobby_id": season.get("lobby_id"),
                    "lobby_name": season.get("lobby_name", ""),
                    "lobby_description": season.get("lobby_description", ""),
                    "role": season.get("role", "member"),
                    "can_manage": bool(season.get("can_manage", False)),
                }
                for season in seasons
            ]
        except Exception:
            return []

    def get_lobby_seasons(self, lobby_id: int) -> list:
        try:
            seasons = self._get(f"/api/lobby/{lobby_id}/seasons")
            return [
                {
                    "id": season.get("id"),
                    "name": season.get("name", ""),
                    "status": season.get("status", "active"),
                    "races_count": season.get("races_played", 0),
                    "total_rounds": season.get("total_rounds", 0),
                }
                for season in seasons
            ]
        except Exception:
            return []

    def get_lobby_members(self, lobby_id: int) -> list:
        try:
            members = self._get(f"/api/lobby/{lobby_id}/members")
            return [
                {
                    "name": member.get("name", "Неизвестный"),
                    "role": member.get("role", "member"),
                    "picture": member.get("picture"),
                }
                for member in members
            ]
        except Exception:
            return []

    def create_season(self, lobby_id: int, name: str) -> dict:
        return self._post(f"/api/lobby/{lobby_id}/seasons", {"name": name})

    def create_lobby(self, name: str, description: str | None = None) -> dict:
        return self._post("/api/lobby", {"name": name, "description": description or None})

    def reset_lobby_invite(self, lobby_id: int) -> dict:
        result = self._post(f"/api/lobby/{lobby_id}/invite/reset")
        invite_code = result.get("invite_code") or ""
        result["invite_link"] = f"{self.frontend_url}/lobby/join?code={invite_code}" if invite_code else ""
        return result

    def join_lobby(self, code: str) -> dict:
        return self._post("/api/lobby/join-by-code", {"invite_code": code})

    # ------------------------------------------------------------------
    # Profile / practice
    # ------------------------------------------------------------------

    def get_profile(self) -> dict:
        user_id = self.config.get("user_id") or (self.user or {}).get("id")
        if not user_id:
            return {}

        try:
            me = self._get(f"/api/web/me/{user_id}")
            result = {
                "name": me.get("name", ""),
                "email": me.get("email", ""),
                "picture": me.get("picture"),
                "player": me.get("player"),
            }
            player = me.get("player")
            if player:
                full = self._get(f"/api/player/{player['id']}/full-profile")
                result["rating"] = {
                    "value": full.get("glicko", {}).get("rating", "-"),
                    "rank": full.get("glicko", {}).get("rank", ""),
                }
                quick_stats = full.get("quick_stats", {})
                result["stats"] = {
                    "races": quick_stats.get("total_races", 0),
                    "wins": quick_stats.get("wins", 0),
                    "podiums": quick_stats.get("podiums", 0),
                    "best_finish": quick_stats.get("best_finish", "-"),
                }
            result["sessions"] = self.get_practice_sessions()[:5]
            return result
        except Exception:
            return {}

    def get_practice_sessions(self) -> list:
        try:
            sessions = self._get("/api/practice/sessions")
            return [
                {
                    "track": session.get("track_name", "Неизвестная трасса"),
                    "session_type": session.get("session_type", ""),
                    "laps": session.get("total_laps", 0),
                    "best_lap_ms": session.get("best_lap_ms"),
                    "best_time": fmt_lap(session.get("best_lap_ms")),
                    "date": (session.get("created_at") or "")[:10],
                }
                for session in sessions
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # AI engineer
    # ------------------------------------------------------------------

    def ask_engineer(self, question: str) -> dict:
        telemetry_ctx = self._get_live_telemetry_context()
        system_prompt = (
            "Ты гоночный инженер Формулы-1 высшего уровня. Говори как настоящий инженер по радио: "
            "спокойно, точно, коротко и по делу. Используй тот же язык, что и пилот. "
            "Держи ответ в пределах 220 слов, если пользователь не попросил подробный разбор. "
            "Предпочитай прямые советы по скорости и исполнению, а не общие наставления. "
            "Когда доступна телеметрия, опирайся на неё в ответе."
        )

        if telemetry_ctx:
            user_msg = (
                f"=== LIVE-КОНТЕКСТ ===\n{telemetry_ctx}\n"
                f"====================\n\n"
                f"Вопрос пилота: {question}"
            )
            context = "Живая телеметрия"
        else:
            user_msg = (
                "[Живая телеметрия недоступна. Дай совет, опираясь на технику пилотирования в F1 25, "
                "гоночную борьбу, работу с шинами, ERS и настройки машины.]\n\n"
                f"Вопрос пилота: {question}"
            )
            context = "Общие рекомендации"

        try:
            response = self._post(
                "/api/engineer/ask",
                {"question": user_msg, "system_prompt": system_prompt},
            )
            return {"answer": response.get("answer", "Ответ не получен."), "context": context}
        except Exception:
            return self._ask_groq_direct(system_prompt, user_msg, context)

    def _get_live_telemetry_context(self) -> str:
        if not self.agent_running or not self.agent_instance:
            return ""

        try:
            from shared.f1_mappings import get_track_name

            agent = self.agent_instance
            parts: list[str] = []

            if getattr(agent, "_track_id", None) is not None:
                parts.append(f"Трасса: {get_track_name(agent._track_id)}")
            if agent.sm and getattr(agent.sm, "state", None):
                parts.append(f"Состояние: {agent.sm.state.value}")

            session_info = getattr(agent, "_session_info", {}) or {}
            if session_info.get("weather_start") is not None:
                parts.append(f"Погода: {session_info.get('weather_end', session_info.get('weather_start'))}")
            if session_info.get("total_laps"):
                parts.append(f"Всего кругов: {session_info['total_laps']}")

            snap = self._telemetry_snapshot()
            if snap.get("position"):
                parts.append(f"Позиция: P{snap['position']}")
            if snap.get("lap"):
                parts.append(f"Круг: {snap['lap']}")
            if snap.get("last_lap_ms"):
                parts.append(f"Последний круг: {fmt_lap(snap['last_lap_ms'])}")
            if snap.get("best_lap_ms"):
                parts.append(f"Лучший круг: {fmt_lap(snap['best_lap_ms'])}")
            if snap.get("speed") is not None:
                parts.append(f"Скорость: {int(snap['speed'])} км/ч")
            if snap.get("throttle") is not None:
                parts.append(f"Газ: {int(float(snap['throttle']) * 100)}%")
            if snap.get("brake") is not None:
                parts.append(f"Тормоз: {int(float(snap['brake']) * 100)}%")
            if snap.get("gear") is not None:
                parts.append(f"Передача: {snap['gear']}")
            if snap.get("drs_active") is not None:
                parts.append(f"DRS доступен: {'да' if snap['drs_active'] else 'нет'}")
            if snap.get("fuel_laps") is not None:
                parts.append(f"Запас топлива: {round(float(snap['fuel_laps']), 1)} круга")
            if snap.get("tyre"):
                parts.append(f"Состав: {snap['tyre']}")
            if snap.get("tyre_wear_avg") is not None:
                parts.append(f"Средний износ шин: {round(float(snap['tyre_wear_avg']), 1)}%")

            return "\n".join(parts)
        except Exception:
            return ""

    def _ask_groq_direct(self, system: str, user: str, context: str) -> dict:
        groq_key = os.getenv("GROQ_API_KEY", "") or self.config.get("groq_api_key", "")
        if not groq_key:
            return {"answer": "Гоночный инженер недоступен. GROQ_API_KEY не настроен.", "context": context}

        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.7,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "answer": data["choices"][0]["message"]["content"],
                "context": context,
            }
        except Exception as exc:
            return {"answer": f"Резервный запрос к инженеру не удался: {exc}", "context": context}

    # ------------------------------------------------------------------
    # Agent control
    # ------------------------------------------------------------------

    def get_agent_status(self) -> dict:
        self._refresh_upload_component()
        self._refresh_telemetry_component()
        pending_uploads = self._components.get("upload", {}).get("pending_uploads", 0)
        pending_telemetry = self._components.get("telemetry", {}).get("pending_telemetry", 0)
        startup_error = ((self._components.get("startup") or {}).get("last_error") or {}).get("message")
        result = {
            "running": False,
            "state": "stopped",
            "status": "Остановлен",
            "label": "Лаунчер готов",
            "mode": self.config.get("agent_mode", "personal"),
            "season_id": self.config.get("season_id"),
            "track_name": None,
            "pending_uploads": pending_uploads,
            "pending_telemetry": pending_telemetry,
            "error": startup_error or self._agent_error,
            "uptime_s": int(time.time() - self._agent_started_at) if self._agent_started_at else 0,
            "lifecycle": dict(self._lifecycle),
            "last_errors": {
                name: ((component.get("last_error") or {}).get("message"))
                for name, component in self._components.items()
            },
        }

        if self._lifecycle["phase"] == "starting":
            result.update({
                "running": True,
                "state": "booting",
                "status": self._lifecycle["status"],
                "label": self._lifecycle["label"],
            })
            return result

        if self._lifecycle["phase"] == "stopping":
            result.update({
                "running": True,
                "state": "stopping",
                "status": self._lifecycle["status"],
                "label": self._lifecycle["label"],
            })
            return result

        if self.agent_running and self.agent_instance:
            from shared.f1_mappings import get_track_name

            state = self.agent_instance.sm.state
            status_map = {
                "idle": "Ожидание",
                "waiting": "Трасса определена",
                "qualifying": "Квалификация",
                "race": "Гонка идёт",
                "finished": "Загрузка результатов",
                "uploaded": "Загружено",
            }
            result.update({
                "running": True,
                "state": state.value,
                "status": status_map.get(state.value, state.value),
                "label": self.agent_instance.sm.label(),
                "track_name": get_track_name(self.agent_instance._track_id) if self.agent_instance._track_id is not None else None,
                "error": None,
            })
            return result

        if self._lifecycle["phase"] == "error" or self._agent_error:
            result.update({
                "state": "error",
                "status": self._lifecycle.get("status") or "Ошибка запуска",
                "label": self._lifecycle.get("label") or "Агент остановился после ошибки",
            })

        return result

    def get_live_session(self) -> dict:
        status = self.get_agent_status()
        if not self.agent_instance:
            return {"active": False, "status": status}

        snap = self._telemetry_snapshot()
        session_info = getattr(self.agent_instance, "_session_info", {}) or {}
        return {
            "active": status["state"] in {"waiting", "qualifying", "race", "finished", "uploaded"},
            "state": status["state"],
            "track_name": status.get("track_name"),
            "weather": session_info.get("weather_end", session_info.get("weather_start")),
            "lap": snap.get("lap"),
            "position": snap.get("position"),
            "last_lap": fmt_lap(snap.get("last_lap_ms")),
            "best_lap": fmt_lap(snap.get("best_lap_ms")),
            "speed": int(snap["speed"]) if snap.get("speed") is not None else None,
            "gear": snap.get("gear"),
            "throttle": int(float(snap["throttle"]) * 100) if snap.get("throttle") is not None else None,
            "brake": int(float(snap["brake"]) * 100) if snap.get("brake") is not None else None,
            "fuel_laps": round(float(snap["fuel_laps"]), 1) if snap.get("fuel_laps") is not None else None,
            "tyre": snap.get("tyre"),
            "tyre_wear_avg": round(float(snap["tyre_wear_avg"]), 1) if snap.get("tyre_wear_avg") is not None else None,
        }

    def start_agent(self, mode: str = "personal", season_id: str | None = None) -> dict:
        if self.agent_running:
            return {"ok": False, "error": "Агент уже запущен."}

        if mode not in {"personal", "lobby"}:
            mode = "personal"
        if mode == "lobby" and not season_id:
            return {"ok": False, "error": "Перед запуском режима хоста выбери сезон лобби."}
        if mode == "lobby":
            selected_host_season = None
            for host_season in self.get_host_seasons():
                if str(host_season.get("id")) == str(season_id):
                    selected_host_season = host_season
                    break
            if not selected_host_season:
                return {
                    "ok": False,
                    "error": "Выбранный хост-сезон недоступен в текущих лобби.",
                }

        self.config["agent_mode"] = mode
        if season_id:
            self.config["season_id"] = str(season_id)
        self.config = _normalize_config(self.config)
        save_config_file(self.config)

        os.environ["F1_SERVER_URL"] = self.base_url
        os.environ["F1_WS_URL"] = self.websocket_url
        os.environ["F1_SEASON_ID"] = self.config["season_id"]
        os.environ["F1_UDP_PORT"] = self.config["udp_port"]
        os.environ["F1_AGENT_MODE"] = mode
        if self.token:
            os.environ["F1_AUTH_TOKEN"] = self.token
        else:
            os.environ.pop("F1_AUTH_TOKEN", None)

        self._agent_error = None
        self._agent_started_at = time.time()
        self._set_lifecycle("starting", "Запуск", "Подготовка runtime лаунчера", record_event=True)
        self._set_component_state("startup", "starting", "Подготовка runtime лаунчера", clear_error=True)
        self._set_component_state("udp", "idle", "Ожидание запуска UDP-слушателя", clear_error=True)
        self._set_component_state("ws", "idle", "Ожидание запуска websocket", clear_error=True)
        overlay_state = "stopped" if self.config.get("overlay_enabled") else "disabled"
        overlay_message = "Оверлей будет запущен вместе с агентом" if self.config.get("overlay_enabled") else "Автозапуск оверлея отключён"
        self._set_component_state("overlay", overlay_state, overlay_message, clear_error=True)
        self._refresh_upload_component()
        self._refresh_telemetry_component()
        self._record_event("info", "startup", "Запрошен запуск агента", data={"mode": mode, "season_id": self.config.get("season_id")})
        self.agent_running = True
        self.agent_thread = threading.Thread(target=self._run_agent, daemon=True, name="LauncherAgent")
        self.agent_thread.start()
        time.sleep(0.15)

        if not self.agent_running and self._agent_error:
            return {"ok": False, "error": self._agent_error}
        return {"ok": True}

    def _run_agent(self) -> None:
        try:
            import asyncio
            import importlib

            import agent.config as acfg

            self._set_component_state("startup", "starting", "Перезагрузка конфигурации агента")
            importlib.reload(acfg)

            from agent.main import F1Agent
            from agent.telemetry_delivery import retry_pending as retry_pending_telemetry
            from agent.uploader import retry_pending_uploads

            self._set_lifecycle("starting", "Запуск", "Повторная отправка сохранённых загрузок перед стартом агента")
            self._set_component_state("startup", "starting", "Повторная отправка сохранённых загрузок перед стартом агента")
            self._pending_retry_running = True
            self._refresh_upload_component()
            self._refresh_telemetry_component()
            asyncio.run(retry_pending_uploads(observer=lambda event, payload=None: self._observe_runtime_event("upload", event, payload or {})))
            asyncio.run(retry_pending_telemetry(observer=lambda event, payload=None: self._observe_runtime_event("telemetry", event, payload or {})))
            self._pending_retry_running = False
            self._refresh_upload_component()
            self._refresh_telemetry_component()

            self._set_lifecycle("starting", "Запуск", "Создание runtime агента")
            self._set_component_state("startup", "starting", "Создание runtime агента")
            self.agent_instance = F1Agent(observer=self._observe_runtime_event)

            if self._overlay_server and self.agent_instance._overlay is not self._overlay_server:
                self.agent_instance._overlay = self._overlay_server

            if self.config.get("overlay_enabled"):
                self._set_lifecycle("starting", "Запуск", "Запуск сервисов оверлея")
                overlay = self._ensure_overlay_server()
                self.agent_instance._overlay_enabled = True
                if not overlay._running:
                    overlay.start()
            else:
                self._set_component_state("overlay", "disabled", "Автозапуск оверлея отключён", clear_error=True)

            self._set_lifecycle("starting", "Запуск", "Подключение websocket и UDP-телеметрии")
            self._set_component_state("startup", "starting", "Подключение websocket и UDP-телеметрии")
            self.agent_instance.start_runtime(retry_cached_uploads=False)

            while self.agent_running:
                time.sleep(0.5)
        except Exception as exc:
            self._agent_error = _friendly_error(exc) or str(exc)
            self._set_component_state("startup", "error", "Сбой запуска агента", error=self._agent_error, record_event=True)
            self._set_lifecycle("error", "Ошибка запуска", "Агент остановился во время запуска", record_event=True, level="error")
            print(f"[LAUNCHER] agent error: {_safe_console_text(self._agent_error)}")
            if self.agent_instance:
                try:
                    self.agent_instance.shutdown()
                except Exception:
                    pass
        finally:
            self._pending_retry_running = False
            self._refresh_upload_component()
            self._refresh_telemetry_component()
            self.agent_running = False

    def stop_agent(self) -> dict:
        self._set_lifecycle("stopping", "Остановка", "Остановка телеметрического агента", record_event=True)
        self.agent_running = False
        if self.agent_instance:
            try:
                self._set_lifecycle("stopping", "Остановка", "Остановка UDP-слушателя")
                self.agent_instance.shutdown()
                self._set_lifecycle("stopping", "Остановка", "Остановка websocket-моста")
                self._set_lifecycle("stopping", "Остановка", "Остановка сервисов оверлея")
            except Exception as exc:
                self._record_event("warn", "startup", "Ошибка при остановке агента", _friendly_error(exc))
            self.agent_instance = None

        if self.agent_thread and self.agent_thread.is_alive():
            self.agent_thread.join(timeout=2)
        self.agent_thread = None
        self._agent_started_at = None
        self._set_component_state("startup", "idle", "Лаунчер готов", clear_error=True)
        self._set_component_state("udp", "stopped", "UDP-слушатель остановлен", clear_error=True)
        self._set_component_state("ws", "stopped", "WebSocket агента остановлен", clear_error=True)
        overlay_state = "stopped" if self.config.get("overlay_enabled") else "disabled"
        overlay_message = "Оверлей готов, но не запущен" if self.config.get("overlay_enabled") else "Автозапуск оверлея отключён"
        self._set_component_state("overlay", overlay_state, overlay_message, clear_error=True)
        self._set_lifecycle("stopped", "Остановлен", "Лаунчер готов", record_event=True)
        return {"ok": True}

    # ------------------------------------------------------------------
    # Settings / diagnostics
    # ------------------------------------------------------------------

    def derive_connection_urls(self, server_url: str | None = None) -> dict:
        return _derive_urls(server_url or self.base_url)

    def get_config(self) -> dict:
        return {
            "server_url": self.config["server_url"],
            "frontend_url": self.config["frontend_url"],
            "ws_url": self.config["ws_url"],
            "udp_port": self.config["udp_port"],
            "season_id": self.config["season_id"],
            "agent_mode": self.config.get("agent_mode", "personal"),
            "overlay_enabled": self.config.get("overlay_enabled", False),
            "overlay_opacity": self.config.get("overlay_opacity", 85),
            "widgets": self.config.get("widgets", [True] * len(WIDGET_KEYS)),
            "widget_positions": self.config.get("widget_positions"),
            "data_dir": str(CONFIG_DIR),
        }

    def save_config(self, cfg: dict) -> dict:
        cfg = cfg or {}

        try:
            if "server_url" in cfg:
                _validate_url_input(cfg.get("server_url"), "Backend")
                self.config["server_url"] = _normalize_http_url(cfg.get("server_url"), self.base_url)
            if cfg.get("sync_urls"):
                derived = _derive_urls(self.config["server_url"])
                self.config["frontend_url"] = derived["frontend_url"]
                self.config["ws_url"] = derived["ws_url"]
            if "frontend_url" in cfg:
                _validate_url_input(cfg.get("frontend_url"), "Frontend")
                self.config["frontend_url"] = _normalize_http_url(cfg.get("frontend_url"), self.frontend_url)
            if "ws_url" in cfg:
                _validate_url_input(cfg.get("ws_url"), "WebSocket", ws=True)
                self.config["ws_url"] = _normalize_ws_url(cfg.get("ws_url"), self.websocket_url)
            if "udp_port" in cfg:
                self.config["udp_port"] = _normalize_udp_port(cfg.get("udp_port"), DEFAULT_UDP_PORT, strict=True)
            if "season_id" in cfg:
                self.config["season_id"] = str(cfg.get("season_id") or "1")
            if "agent_mode" in cfg:
                self.config["agent_mode"] = cfg.get("agent_mode") if cfg.get("agent_mode") in {"personal", "lobby"} else "personal"
            if "overlay_enabled" in cfg:
                self.config["overlay_enabled"] = bool(cfg["overlay_enabled"])
            if "overlay_opacity" in cfg:
                self.config["overlay_opacity"] = int(cfg["overlay_opacity"])
            if "widgets" in cfg:
                self.config["widgets"] = cfg["widgets"]
            if "widget_positions" in cfg:
                self.config["widget_positions"] = cfg["widget_positions"]
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        self.config = _normalize_config(self.config)
        save_config_file(self.config)

        if self.agent_instance:
            overlay = self._ensure_overlay_server()
            self.agent_instance._overlay_enabled = self.config["overlay_enabled"]
            if self.config["overlay_enabled"] and not overlay._running:
                overlay.start()
            if not self.config["overlay_enabled"] and overlay._running:
                overlay.stop()

        overlay_state = "stopped" if self.config["overlay_enabled"] else "disabled"
        overlay_message = "Оверлей готов, но не запущен" if self.config["overlay_enabled"] else "Автозапуск оверлея отключён"
        self._set_component_state("overlay", overlay_state, overlay_message, clear_error=not self.config["overlay_enabled"])

        return {"ok": True, "config": self.get_config()}

    def open_overlay(self, draft: dict | None = None) -> dict:
        try:
            overlay = self._ensure_overlay_server()
            if not overlay._running:
                overlay.start()
                time.sleep(0.4)

            overlay_cfg = _normalize_config({**self.config, **(draft or {})})
            params = {
                "opacity": str(round(overlay_cfg.get("overlay_opacity", 85) / 100, 2)),
                "api": overlay_cfg.get("server_url", self.base_url),
                "pedals": "1",
            }
            widgets = overlay_cfg.get("widgets", [True] * len(WIDGET_KEYS))
            for index, key in enumerate(WIDGET_KEYS):
                if index < len(widgets) and not widgets[index]:
                    params[key] = "0"
            positions = overlay_cfg.get("widget_positions")
            if positions:
                params["positions"] = json.dumps(positions)

            url = f"http://localhost:8080/overlay.html?{urlencode(params)}"
            webbrowser.open(url)
            return {"ok": True, "url": url}
        except Exception as exc:
            return {"error": f"Не удалось открыть оверлей: {exc}"}

    def open_data_folder(self) -> dict:
        try:
            target = CONFIG_DIR
            if os.name == "nt":
                os.startfile(target)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
            return {"ok": True, "path": str(target)}
        except Exception as exc:
            return {"error": f"Не удалось открыть папку данных: {exc}"}

    def retry_pending_uploads_now(self) -> dict:
        if self._pending_retry_running:
            return {"ok": False, "error": "Повтор отложенных загрузок уже выполняется."}

        snapshot = self._pending_delivery_snapshot()
        if snapshot["errors"]:
            self._refresh_upload_component()
            self._refresh_telemetry_component()
            return {"ok": False, "error": "; ".join(snapshot["errors"])}

        if not snapshot["count"]:
            self._refresh_upload_component()
            self._refresh_telemetry_component()
            return {"ok": True, "started": False, "retried": 0, "retried_uploads": 0, "retried_telemetry": 0}

        def worker() -> None:
            try:
                import asyncio

                from agent.telemetry_delivery import retry_pending as retry_pending_telemetry
                from agent.uploader import retry_pending_uploads

                self._pending_retry_running = True
                self._refresh_upload_component(log_event=True)
                self._refresh_telemetry_component(log_event=True)
                self._record_event(
                    "info",
                    "upload",
                    "Запущен ручной повтор отложенной доставки",
                    data={
                        "count": snapshot["count"],
                        "pending_uploads": snapshot["pending_uploads"],
                        "pending_telemetry": snapshot["pending_telemetry"],
                    },
                )
                asyncio.run(retry_pending_uploads(observer=lambda event, payload=None: self._observe_runtime_event("upload", event, payload or {})))
                asyncio.run(retry_pending_telemetry(observer=lambda event, payload=None: self._observe_runtime_event("telemetry", event, payload or {})))
            except Exception as exc:
                self._set_component_state("upload", "error", "Ручной повтор отложенной доставки завершился сбоем", error=exc, record_event=True)
                self._set_component_state("telemetry", "error", "Ручной повтор отложенной доставки завершился сбоем", error=exc, record_event=True)
            finally:
                self._pending_retry_running = False
                self._refresh_upload_component()
                self._refresh_telemetry_component()

        threading.Thread(target=worker, daemon=True, name="LauncherPendingRetry").start()
        return {
            "ok": True,
            "started": True,
            "retried": snapshot["count"],
            "retried_uploads": snapshot["pending_uploads"],
            "retried_telemetry": snapshot["pending_telemetry"],
        }

    def get_diagnostics(self) -> dict:
        self._refresh_upload_component()
        self._refresh_telemetry_component()
        diagnostics = {
            "config": self.get_config(),
            "backend": {"ok": False, "message": "Не проверено", "latency_ms": None},
            "frontend": {"ok": False, "message": "Не проверено", "latency_ms": None},
            "auth": {"signed_in": bool(self.token), "ok": False, "message": "Вход не выполнен"},
            "cache": {
                "pending_uploads": self._components["upload"].get("pending_uploads", 0),
                "entries": self._components["upload"].get("entries", []),
                "upload_entries": self._components["upload"].get("entries", []),
                "retry_running": self._components["upload"].get("retry_running", False),
                "pending_telemetry": self._components["telemetry"].get("pending_telemetry", 0),
                "telemetry_entries": self._components["telemetry"].get("entries", []),
                "telemetry_ready_to_flush": self._components["telemetry"].get("ready_to_flush", 0),
                "telemetry_waiting_for_race_id": self._components["telemetry"].get("waiting_for_race_id", 0),
            },
            "overlay": {
                "enabled": bool(self.config.get("overlay_enabled")),
                "running": bool(self._overlay_server and self._overlay_server._running),
                "state": (self._components.get("overlay") or {}).get("state"),
                "message": (self._components.get("overlay") or {}).get("message"),
            },
            "agent": self.get_agent_status(),
            "live": self.get_live_session(),
            "components": self._component_snapshot(),
            "recent_events": list(self._recent_events),
        }

        start = time.perf_counter()
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=4)
            latency = int((time.perf_counter() - start) * 1000)
            diagnostics["backend"] = {
                "ok": response.status_code == 200,
                "message": f"HTTP {response.status_code}",
                "latency_ms": latency,
            }
        except Exception as exc:
            diagnostics["backend"] = {"ok": False, "message": str(exc), "latency_ms": None}

        start = time.perf_counter()
        try:
            response = httpx.get(self.frontend_url, timeout=4, follow_redirects=True)
            latency = int((time.perf_counter() - start) * 1000)
            diagnostics["frontend"] = {
                "ok": response.status_code < 500,
                "message": f"HTTP {response.status_code}",
                "latency_ms": latency,
            }
        except Exception as exc:
            diagnostics["frontend"] = {"ok": False, "message": str(exc), "latency_ms": None}

        if self.token:
            try:
                user = self._get("/api/web/me/by-token", timeout=5)
                diagnostics["auth"] = {
                    "signed_in": True,
                    "ok": True,
                    "message": user.get("email") or user.get("name") or "Вход выполнен",
                }
            except Exception as exc:
                diagnostics["auth"] = {"signed_in": True, "ok": False, "message": str(exc)}

        diagnostics["recovery"] = self._build_recovery_actions(diagnostics)
        return diagnostics


def main():
    api = LauncherAPI()

    window = webview.create_window(
        "Лаунчер F1 League",
        str(UI_DIR / "index.html"),
        js_api=api,
        width=1360,
        height=860,
        min_size=(1120, 720),
        background_color="#0b0a08",
    )
    api._window = window

    def on_loaded():
        try:
            user = api.auto_login()
            if user and user.get("id"):
                payload = json.dumps(user, ensure_ascii=False)
                window.evaluate_js(
                    "if (window.bootstrapFromPython) { "
                    f"window.bootstrapFromPython({payload}); "
                    "} else { "
                    f"window.__launcherBootUser = {payload};"
                    "}"
                )
        except Exception as exc:
            print(f"[LAUNCHER] auto-login error: {_safe_console_text(exc)}")

    window.events.loaded += on_loaded
    debug_enabled = str(os.environ.get("F1_LAUNCHER_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}
    webview.start(debug=debug_enabled)


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
import unittest
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Awaitable, Callable, TypeVar
from urllib.parse import quote_plus

import psycopg2
from fastapi.testclient import TestClient
from psycopg2 import sql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]

T = TypeVar("T")


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


@dataclass(slots=True)
class PostgresConfig:
    user: str
    password: str
    host: str = "127.0.0.1"
    port: int = 5432

    @classmethod
    def from_repo(cls) -> "PostgresConfig":
        repo_env = _read_env_file(ROOT_DIR / ".env")
        return cls(
            user=os.getenv("BACKEND_TEST_POSTGRES_USER", repo_env.get("POSTGRES_USER", "f1league")),
            password=os.getenv("BACKEND_TEST_POSTGRES_PASSWORD", repo_env.get("POSTGRES_PASSWORD", "f1league")),
            host=os.getenv("BACKEND_TEST_POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("BACKEND_TEST_POSTGRES_PORT", "5432")),
        )

    def admin_connect(self, dbname: str = "postgres"):
        return psycopg2.connect(
            dbname=dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            connect_timeout=5,
        )

    def async_database_url(self, db_name: str) -> str:
        return (
            "postgresql+asyncpg://"
            f"{quote_plus(self.user)}:{quote_plus(self.password)}@{self.host}:{self.port}/{db_name}"
        )


@dataclass(slots=True)
class CapturedHTTPRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes

    def json(self) -> dict | list | None:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))


class LocalHTTPCaptureServer:
    def __init__(self) -> None:
        self._requests: list[CapturedHTTPRequest] = []
        self._responses: dict[str, list[tuple[int, dict]]] = {}
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            return
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self, method: str) -> None:
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length) if content_length > 0 else b""
                captured = CapturedHTTPRequest(
                    method=method,
                    path=self.path,
                    headers={key: value for key, value in self.headers.items()},
                    body=body,
                )
                with server._lock:
                    server._requests.append(captured)
                    response_queue = server._responses.get(self.path, [])
                    if response_queue:
                        status_code, payload = response_queue.pop(0)
                    else:
                        status_code, payload = 200, {"ok": True}

                payload_bytes = json.dumps(payload).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload_bytes)))
                self.end_headers()
                self.wfile.write(payload_bytes)

            def do_GET(self) -> None:  # noqa: N802
                self._handle("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._handle("POST")

            def do_PUT(self) -> None:  # noqa: N802
                self._handle("PUT")

            def do_PATCH(self) -> None:  # noqa: N802
                self._handle("PATCH")

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> "LocalHTTPCaptureServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("Capture server is not running.")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def set_json_response(self, path: str, payload: dict, *, status_code: int = 200) -> None:
        with self._lock:
            self._responses.setdefault(path, []).append((status_code, payload))

    def requests_for(self, path: str) -> list[CapturedHTTPRequest]:
        with self._lock:
            return [request for request in self._requests if request.path == path]

    def all_requests(self) -> list[CapturedHTTPRequest]:
        with self._lock:
            return list(self._requests)

    def clear_requests(self) -> None:
        with self._lock:
            self._requests.clear()


def _docker_ready() -> bool:
    result = subprocess.run(
        ["docker", "ps"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _start_docker_best_effort() -> None:
    if _docker_ready():
        return

    if os.name == "nt":
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Start-Service com.docker.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        desktop = Path("C:/Program Files/Docker/Docker/Docker Desktop.exe")
        if desktop.exists():
            subprocess.Popen([str(desktop)])

    deadline = time.time() + 90
    while time.time() < deadline:
        if _docker_ready():
            return
        time.sleep(3)
    raise RuntimeError("Docker daemon is not ready for backend integration tests.")


def ensure_postgres_available(config: PostgresConfig) -> None:
    try:
        with config.admin_connect():
            return
    except psycopg2.Error:
        pass

    _start_docker_best_effort()
    subprocess.run(
        ["docker", "compose", "up", "-d", "postgres"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=True,
    )

    deadline = time.time() + 90
    last_error = "unknown"
    while time.time() < deadline:
        try:
            with config.admin_connect():
                return
        except psycopg2.Error as exc:
            last_error = str(exc)
            time.sleep(2)
    raise RuntimeError(f"Postgres is not reachable for backend integration tests: {last_error}")


def create_temp_database(config: PostgresConfig) -> str:
    db_name = f"f1t_integration_{uuid.uuid4().hex[:10]}"
    conn = config.admin_connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    finally:
        conn.close()
    return db_name


def drop_temp_database(config: PostgresConfig, db_name: str) -> None:
    conn = config.admin_connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (db_name,),
            )
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
    finally:
        conn.close()


class BackendIntegrationHarness:
    def __init__(self) -> None:
        self.postgres = PostgresConfig.from_repo()
        self.database_name: str | None = None
        self.database_url: str | None = None
        self.app = None
        self.client: TestClient | None = None
        self._client_cm = None
        self._env_backup: dict[str, str | None] = {}

    def start(self) -> None:
        ensure_postgres_available(self.postgres)
        self.database_name = create_temp_database(self.postgres)
        self.database_url = self.postgres.async_database_url(self.database_name)
        self._apply_env(
            {
                "DATABASE_URL": self.database_url,
                "NEXTAUTH_SECRET": "integration-nextauth-secret",
                "AGENT_SECRET_TOKEN": "integration-agent-secret",
                "BOT_NOTIFY_URL": "http://127.0.0.1:9/internal/race_uploaded",
                "BOT_NOTIFY_SECRET": "integration-bot-secret",
                "GROQ_API_KEY": "",
                "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
            }
        )

        from backend.app_factory import BackendAppConfig, create_app
        from backend.db.base import configure_database

        configure_database(self.database_url)
        self.app = create_app(BackendAppConfig(database_url=self.database_url, strict_startup=True))
        self._client_cm = TestClient(self.app)
        self.client = self._client_cm.__enter__()

        achievement_count = self.db_call(self._count_achievements)
        if achievement_count <= 0:
            raise AssertionError("FastAPI lifespan did not seed achievements in the integration database.")

    def close(self) -> None:
        try:
            if self._client_cm is not None:
                self._client_cm.__exit__(None, None, None)
        finally:
            if self.database_name:
                drop_temp_database(self.postgres, self.database_name)
            self._restore_env()

    def _apply_env(self, values: dict[str, str]) -> None:
        for key, value in values.items():
            if key not in self._env_backup:
                self._env_backup[key] = os.environ.get(key)
            os.environ[key] = value

    def _restore_env(self) -> None:
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._env_backup.clear()

    async def _count_achievements(self, session) -> int:
        from sqlalchemy import func, select
        from backend.models.models import Achievement

        result = await session.execute(select(func.count()).select_from(Achievement))
        return int(result.scalar() or 0)

    def db_call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        async def runner() -> T:
            if not self.database_url:
                raise RuntimeError("Integration database is not initialized.")

            engine = create_async_engine(self.database_url, echo=False)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with session_factory() as session:
                    return await func(session, *args, **kwargs)
            finally:
                await engine.dispose()

        return asyncio.run(runner())


class BackendIntegrationCase(unittest.TestCase):
    harness: BackendIntegrationHarness

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.harness = BackendIntegrationHarness()
        cls.harness.start()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.harness.close()
        finally:
            super().tearDownClass()

    @property
    def client(self) -> TestClient:
        assert self.harness.client is not None
        return self.harness.client

    def auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def agent_headers(self) -> dict[str, str]:
        return {"X-Agent-Token": os.environ["AGENT_SECRET_TOKEN"]}

    def register_user(self, prefix: str, *, password: str = "Password123!") -> dict:
        email = f"{prefix}.{uuid.uuid4().hex[:8]}@example.com"
        response = self.client.post(
            "/api/web/register",
            json={"email": email, "password": password, "name": prefix},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.db import base as db_base
from backend.db.base import configure_database
from backend.routers import (
    achievements,
    admin,
    analytics,
    contracts,
    lobby,
    players,
    players_admin,
    practice,
    races,
    seasons,
    standings,
    stewards,
    telemetry,
    web_auth,
    ws,
)
from backend.routers import health as health_router

StartupHook = Callable[[FastAPI], Awaitable[None]]


@dataclass(slots=True)
class BackendAppConfig:
    database_url: str | None = None
    run_migrations: bool = True
    seed_achievements: bool = True
    strict_startup: bool = True
    cors_origins: list[str] | None = None
    startup_hooks: Sequence[StartupHook] = field(default_factory=tuple)
    static_dir: Path | None = None


def _default_cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]


def _run_alembic_upgrade(config: BackendAppConfig) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    alembic_ini = Path(__file__).resolve().with_name("alembic.ini")
    env = os.environ.copy()
    env["DATABASE_URL"] = configure_database(config.database_url)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=env,
        check=False,
    )
    if result.returncode == 0:
        print("[STARTUP] Alembic migrations applied")
        return

    message = (result.stderr or result.stdout or "unknown Alembic failure").strip()
    if config.strict_startup:
        raise RuntimeError(f"Alembic startup migration failed: {message}")
    print(f"[STARTUP] Alembic warning: {message}")


async def _seed_achievements() -> None:
    from backend.services.achievement_definitions import seed_achievements

    async with db_base.AsyncSessionLocal() as db:
        await seed_achievements(db)


def create_app(config: BackendAppConfig | None = None) -> FastAPI:
    resolved_config = config or BackendAppConfig()
    configure_database(resolved_config.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            if resolved_config.run_migrations:
                _run_alembic_upgrade(resolved_config)
            if resolved_config.seed_achievements:
                await _seed_achievements()
            for hook in resolved_config.startup_hooks:
                await hook(app)
            yield
        finally:
            await db_base.dispose_database_engines()

    app = FastAPI(title="F1 League API", version="1.0.0", lifespan=lifespan)
    app.state.backend_config = resolved_config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_config.cors_origins or _default_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    app.include_router(health_router.router)
    app.include_router(races.router)
    app.include_router(standings.router)
    app.include_router(players.router)
    app.include_router(players_admin.router)
    app.include_router(admin.router)
    app.include_router(stewards.router)
    app.include_router(achievements.router)
    app.include_router(ws.router)
    app.include_router(contracts.router)
    app.include_router(telemetry.router)
    app.include_router(web_auth.router)
    app.include_router(seasons.router)
    app.include_router(lobby.router)
    app.include_router(analytics.router)
    app.include_router(practice.router)

    static_dir = resolved_config.static_dir or Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/engineer/ask")
    async def engineer_ask(request_data: dict):
        """Proxy to Groq API for AI race engineer (used by launcher)."""
        import httpx as hx

        groq_key = os.getenv("GROQ_API_KEY", "")
        groq_url = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
        groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        if not groq_key:
            return {"answer": "Race engineer unavailable â€” GROQ_API_KEY not set on server."}
        question = request_data.get("question", "")
        system_prompt = request_data.get("system_prompt", "")

        if not system_prompt or len(system_prompt) < 50:
            system_prompt = (
                "You are a world-class Formula 1 race engineer â€” think Peter 'Bono' Bonnington "
                "or Gianpiero Lambiase. Communicate like a real engineer on the radio: calm, precise, "
                "confident. Use specific numbers, reference corners by name. "
                "Encourage the driver while being honest about issues. "
                "Answer in the same language the driver uses. Keep under 200 words."
            )

        try:
            async with hx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    groq_url,
                    headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                    json={
                        "model": groq_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": question},
                        ],
                        "max_tokens": 500,
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return {"answer": data["choices"][0]["message"]["content"]}
        except Exception as exc:
            print(f"[ENGINEER] Error: {exc}")
            return {"answer": "Radio failure â€” engineer temporarily unavailable."}

    @app.get("/agent/download")
    async def download_agent():
        from fastapi import HTTPException
        from fastapi.responses import FileResponse

        exe_path = static_dir / "F1LeagueAgent.exe"
        if not exe_path.exists():
            raise HTTPException(404, "Agent exe not found on server")
        return FileResponse(
            path=str(exe_path),
            filename="F1LeagueAgent.exe",
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.get("/agent/installer")
    async def download_installer():
        from fastapi import HTTPException
        from fastapi.responses import FileResponse

        installer_path = static_dir / "Setup_F1LeagueAgent.exe"
        if not installer_path.exists():
            raise HTTPException(404, "Installer not found on server")
        return FileResponse(
            path=str(installer_path),
            filename="Setup_F1LeagueAgent.exe",
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    return app

from __future__ import annotations

import os
from threading import Lock

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DEFAULT_DATABASE_URL = "postgresql+asyncpg://f1league:f1league@localhost:5432/f1league"

_DATABASE_LOCK = Lock()
_orphaned_engines: list[AsyncEngine] = []


def _build_engine(database_url: str) -> AsyncEngine:
    kwargs: dict[str, object] = {"echo": False}
    if database_url.startswith("postgresql"):
        kwargs.update(
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
        )
    return create_async_engine(database_url, **kwargs)


DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
engine = _build_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    return DATABASE_URL


def configure_database(database_url: str | None = None) -> str:
    global DATABASE_URL, engine, AsyncSessionLocal

    resolved = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    os.environ["DATABASE_URL"] = resolved

    with _DATABASE_LOCK:
        if resolved == DATABASE_URL:
            return resolved

        old_engine = engine
        DATABASE_URL = resolved
        engine = _build_engine(resolved)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
        if old_engine is not None:
            _orphaned_engines.append(old_engine)

    return resolved


async def dispose_database_engines() -> None:
    stale, current = [], None
    with _DATABASE_LOCK:
        stale = list(_orphaned_engines)
        _orphaned_engines.clear()
        current = engine

    for item in stale:
        await item.dispose()
    if current is not None:
        await current.dispose()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

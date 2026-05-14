"""Pytest fixtures for backend tests.

Uses isolated postgres-test container, not SQLite — because the schema
relies on JSONB, ARRAY, and partial unique indexes that SQLite doesn't support.
"""
import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import confirmed in discovery Task 5.
from backend.db.base import Base

# Importing the models module registers every ORM class against
# `Base.metadata` so that `create_all` actually emits CREATE TABLE.
import backend.models.models  # noqa: F401  -- side-effect import


TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@postgres-test:5432/test",
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Per-test isolated DB session.

    Drops + recreates schema each test (fast for small schema).
    Switch to a transactional fixture later if setup grows.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    SessionMaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionMaker() as session:
        yield session
    await engine.dispose()

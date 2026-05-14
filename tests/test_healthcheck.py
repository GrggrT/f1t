"""Verifies the SELECT 1 readiness pattern used by /readyz."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_readyz_pattern(db_session):
    """The same query that /readyz executes against the live DB."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1

"""Read-only analysis report for the WebUser+Player → User merge.

Run BEFORE the 0013/0014 migrations. Writes a Markdown report to
backups/user_player_merge_analysis_<timestamp>.md and exits non-zero
if conflicts that would block the merge are found.

Usage (from repo root):
    docker compose exec -T backend python scripts/analyze_user_player_merge.py

Checks (per Sprint 2 spec):
    1. Counts: web-only / linked / player-only.
    2. WebUsers without email (expected 0 for new schema, allowed elsewhere).
    3. Multiple WebUsers pointing at the same player_id (CONFLICT — block).
    4. Steam ID mismatch between linked pair (CONFLICT — block).
    5. Name mismatches between linked pair (informational).
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


REPORT_DIR = Path(__file__).resolve().parents[1] / "backups"


async def _run(session) -> tuple[list[str], bool]:
    lines: list[str] = []
    blocked = False

    def section(title: str) -> None:
        lines.append(f"\n## {title}\n")

    section("Counts")
    row = (await session.execute(text("SELECT COUNT(*) FROM web_users"))).first()
    lines.append(f"- `web_users` total: **{row[0]}**")
    row = (await session.execute(text("SELECT COUNT(*) FROM players"))).first()
    lines.append(f"- `players` total: **{row[0]}**")
    row = (await session.execute(text("SELECT COUNT(*) FROM web_users WHERE player_id IS NOT NULL"))).first()
    linked = row[0]
    lines.append(f"- linked pairs (web_users.player_id IS NOT NULL): **{linked}**")
    row = (await session.execute(text("SELECT COUNT(*) FROM web_users WHERE player_id IS NULL"))).first()
    lines.append(f"- web-only (web_user without player): **{row[0]}**")
    row = (await session.execute(text(
        "SELECT COUNT(*) FROM players p "
        "WHERE p.id NOT IN (SELECT player_id FROM web_users WHERE player_id IS NOT NULL)"
    ))).first()
    lines.append(f"- player-only (player without web_user): **{row[0]}**")

    section("Web users with NULL email")
    rows = (await session.execute(text(
        "SELECT id, name, google_id, steam_id64, player_id FROM web_users WHERE email IS NULL"
    ))).all()
    if not rows:
        lines.append("- ✅ none")
    else:
        lines.append(f"- ⚠️ {len(rows)} row(s) (informational, not blocking):")
        for r in rows:
            lines.append(f"  - id={r[0]} name={r[1]!r} google={r[2]} steam={r[3]} player_id={r[4]}")

    section("Multiple WebUsers per player_id (BLOCKER if any)")
    rows = (await session.execute(text(
        "SELECT player_id, COUNT(*) AS n, array_agg(id) AS web_user_ids "
        "FROM web_users WHERE player_id IS NOT NULL "
        "GROUP BY player_id HAVING COUNT(*) > 1"
    ))).all()
    if not rows:
        lines.append("- ✅ none")
    else:
        blocked = True
        for r in rows:
            lines.append(f"- 🔴 player_id={r[0]} has {r[1]} web_users: {list(r[2])}")

    section("Steam ID mismatch on linked pairs (BLOCKER if any)")
    rows = (await session.execute(text(
        "SELECT w.id AS web_user_id, w.steam_id64 AS web_steam, "
        "       p.id AS player_id, p.steam_id64 AS player_steam "
        "FROM web_users w "
        "JOIN players p ON w.player_id = p.id "
        "WHERE w.steam_id64 IS NOT NULL "
        "  AND p.steam_id64 IS NOT NULL "
        "  AND w.steam_id64 != p.steam_id64"
    ))).all()
    if not rows:
        lines.append("- ✅ none")
    else:
        blocked = True
        for r in rows:
            lines.append(
                f"- 🔴 web_user={r[0]} steam={r[1]!r} vs player={r[2]} steam={r[3]!r}"
            )

    section("Name mismatches on linked pairs (informational)")
    rows = (await session.execute(text(
        "SELECT w.id, w.name AS web_name, p.id, p.name AS player_name "
        "FROM web_users w "
        "JOIN players p ON w.player_id = p.id "
        "WHERE w.name IS DISTINCT FROM p.name"
    ))).all()
    if not rows:
        lines.append("- ✅ none — names align across linked pairs")
    else:
        lines.append(f"- ℹ️  {len(rows)} pair(s) — Player.name wins per spec COALESCE:")
        for r in rows:
            lines.append(f"  - web_user={r[0]} web_name={r[1]!r} → player={r[2]} player_name={r[3]!r}")

    section("Expected user count after merge")
    web_only_row = (await session.execute(text(
        "SELECT COUNT(*) FROM web_users WHERE player_id IS NULL"
    ))).first()
    player_only_row = (await session.execute(text(
        "SELECT COUNT(*) FROM players p "
        "WHERE p.id NOT IN (SELECT player_id FROM web_users WHERE player_id IS NOT NULL)"
    ))).first()
    total = linked + web_only_row[0] + player_only_row[0]
    lines.append(f"- linked ({linked}) + web-only ({web_only_row[0]}) + player-only ({player_only_row[0]}) = **{total}**")

    return lines, blocked


async def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    engine = create_async_engine(db_url, echo=False, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_path = REPORT_DIR / f"user_player_merge_analysis_{ts}.md"

    header = [
        "# WebUser + Player → User merge analysis",
        f"",
        f"Generated at: {ts} UTC",
        f"Database URL: `{db_url.split('@')[-1] if '@' in db_url else db_url}`",
    ]

    try:
        async with sm() as session:
            body, blocked = await _run(session)
    finally:
        await engine.dispose()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(header + body) + "\n", encoding="utf-8")
    print(f"Report written: {report_path}")
    if blocked:
        print("BLOCKED: at least one conflict prevents the merge.", file=sys.stderr)
        return 1
    print("OK: no blocking conflicts. Safe to proceed to 0013/0014.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

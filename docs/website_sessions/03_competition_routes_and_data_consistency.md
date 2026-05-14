# Step 03 - Competition Routes And Data Consistency

## Status

Planned

## Goal

Harden the public/competition path:

- home
- seasons
- season overview
- standings
- calendar
- live
- races archive
- race results

## Why This Matters

This is the core public product path. Data counts, links, and CTA chains must agree with each other and with backend reality.

## Mandatory Workflow

1. Read `C:\f1t\MEMORY.md` and this file.
2. Update `C:\f1t\MEMORY.md` during the work.
3. Append the final report to `Session Log` in this file.
4. If subagents are used, transfer their findings into memory and this file.

## What To Do

- Audit `frontend/app/page.tsx`, `frontend/app/seasons`, `frontend/app/season/[id]`, `frontend/app/races`, `frontend/app/race/[id]`, and related data loaders.
- Verify the canonical path model `Home -> Seasons -> Season -> Race`.
- Confirm that legacy redirect routes stay thin and do not introduce alternate business logic.
- Check that counts, latest race blocks, next race blocks, standings, and archive links are internally consistent.
- Fix mismatches between `site-data.ts`, `api.ts`, and page assumptions.
- Add honest empty/degraded states instead of ambiguous copy when data is missing.

## Deliverables

- reliable public competition browsing path
- consistent route/data behavior
- better empty/degraded states
- updated memory and `Session Log`

## Verification

- no broken canonical path between home, season, and race
- redirects land on the correct new routes
- standings/calendar/race archive data agree with backend responses
- empty seasons/races behave honestly

## Session Log

- 2026-03-27: file created as the third website hardening task.

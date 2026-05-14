# Step 04 - Telemetry Pipeline Integrity

## Status

Completed

## Goal

Verify telemetry pipeline integrity after race result upload:

- agent-side sampling and buffering
- race upload -> race_id known -> telemetry flush sequencing
- lap/session history persistence
- backend compare/best/session-history telemetry contracts

## Why This Is A Separate Step

Telemetry can look fine on the happy path and still fail on the edges:
missed laps, inconsistent lap numbering, partial session history, `race_id`
timing issues, and broken compare output.

## Required Workflow

1. Read `C:\f1t\MEMORY.md` and this file first.
2. Record all integrity gaps in `C:\f1t\MEMORY.md`.
3. Write the outcome into `Session Log` in this file.
4. If subagents are used, copy their results into both memory and this file.

## Scope

- Inspect `agent/telemetry_buffer.py` and `backend/routers/telemetry.py`.
- Verify the `race upload -> race_id known -> telemetry flush` chain.
- Ensure telemetry is not lost because of timing or race_id ordering.
- Ensure backend endpoints stay consistent for:
  - race telemetry
  - best lap
  - compare
  - session history
- If gaps exist, fix the contract or sequencing.

## Deliverables

- an end-to-end telemetry pipeline with safer sequencing
- reduced silent data-corruption risk

## Validation

- telemetry endpoints return non-contradictory results
- laps and session history do not disappear without an explicit reason

## Session Log

- 2026-03-27: Task file created for the telemetry integrity session.
- 2026-03-27: Reworked `agent/telemetry_buffer.py` so buffered laps now keep `lap_time_ms`, completed laps inherit `last_lap_ms`, and final snapshots backfill missing lap times from session history before flush.
- 2026-03-27: Added `agent/telemetry_delivery.py` plus `TELEMETRY_CACHE_FILE`; telemetry snapshots are now cached by `session_uid`, survive restart, get bound to `race_id` after race upload success, and retry delivery on the next runtime start if flush fails.
- 2026-03-27: Updated `agent/main.py`, `agent/uploader.py`, and `agent/replay_harness.py` to use the new persistent telemetry snapshot path instead of the older in-memory-only flush flow.
- 2026-03-27: Reworked `backend/routers/telemetry.py` so lap telemetry and session history are idempotent, missing `lap_time_ms` values are backfilled in either arrival order, `/best` and `/compare` use effective lap-time fallback, and explicit GET session-history endpoints now exist.
- 2026-03-27: Aligned `backend/models/models.py` with the existing migration-level unique indexes for `lap_telemetry` and `race_session_history`.
- 2026-03-27: Added `tests/test_telemetry_pipeline_integrity.py` covering buffer finalization, persistent telemetry retry after race upload, lap-time backfill on submit, session-history merge/backfill, and compare/best fallback contracts.
- 2026-03-27: Validation passed:
  - `python -m py_compile agent/telemetry_buffer.py agent/telemetry_delivery.py agent/main.py agent/uploader.py agent/config.py backend/routers/telemetry.py backend/models/models.py tests/test_telemetry_pipeline_integrity.py agent/replay_harness.py`
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency tests.test_telemetry_pipeline_integrity`
  - `python -m agent.replay_harness --self-test --json`
- 2026-03-27: Late sequencing fix: `agent/launcher.py` now runs telemetry retry together with race-result retry in the launcher pre-start path and manual retry path, so pending telemetry flushes are not stranded when launcher starts `F1Agent` with `retry_cached_uploads=False`.
- 2026-03-27: Post-fix validation passed:
  - `python -m py_compile agent/launcher.py`
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency tests.test_telemetry_pipeline_integrity`
- 2026-03-27: Remaining gaps:
  - launcher UX still exposes only the race-result cache and not the separate telemetry flush queue
  - replay still reports the older fixed-car-count live structures (`live_entries=20`)
  - a live backend chaos pass with real telemetry and forced HTTP failures is still pending

# Step 04 - Deep Analysis Truthfulness And Fallbacks

## Status

Planned

## Goal

Audit and harden deep-analysis surfaces:

- telemetry
- compare
- replay
- race analysis
- season engineer

## Why This Matters

Deep-analysis pages create the strongest "product depth" impression, but they also create the most trust damage when they look finished while only half-working.

## Mandatory Workflow

1. Read `C:\f1t\MEMORY.md` and this file.
2. Update `C:\f1t\MEMORY.md` during meaningful discoveries or milestones.
3. Append the final report to `Session Log` in this file.
4. If subagents are used, carry their outcomes into both memory and this file.

## What To Do

- Audit `frontend/app/telemetry/[race_id]`, `frontend/app/compare/[race_id]`, `frontend/app/race/[id]/analysis`, `frontend/app/race/[id]/replay`, and `frontend/app/season/[id]/engineer`.
- Verify backend contract assumptions for telemetry/analysis/replay data.
- Decide page by page:
  - production-ready and should be fixed/completed now
  - not production-ready and should show a truthful limited/degraded state
- Remove misleading "finished" presentation when the data is partial, missing, or unreliable.
- Improve user guidance so the site explains what data is unavailable and why.

## Deliverables

- honest deep-analysis surfaces
- fewer misleading half-working states
- updated memory and `Session Log`

## Verification

- pages either work reliably or degrade explicitly
- telemetry/analysis contracts match backend reality
- missing data does not present as a fake-success UX

## Session Log

- 2026-03-27: file created as the fourth website hardening task.

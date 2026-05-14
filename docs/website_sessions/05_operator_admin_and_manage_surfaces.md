# Step 05 - Operator Admin And Manage Surfaces

## Status

Planned

## Goal

Harden operator-sensitive web surfaces:

- admin
- season manage
- lobby manage / moderator tools
- permission gating

## Why This Matters

Operator pages are high-risk because silent failure or bad permission handling can cause real league-management mistakes.

## Mandatory Workflow

1. Read `C:\f1t\MEMORY.md` and this file.
2. Update `C:\f1t\MEMORY.md` as risks, milestones, or plan changes appear.
3. Append the final report to `Session Log` in this file.
4. If subagents are used, propagate their useful findings into both memory and this file.

## What To Do

- Audit `frontend/app/admin/page.tsx`, `frontend/app/season/[id]/manage/page.tsx`, and related operator actions.
- Verify permission checks in UI against backend truth.
- Remove silent failures from operator actions.
- Make dangerous or role-sensitive actions explicit.
- Ensure state refresh after mutations is reliable and visible.
- Confirm that access-denied states are accurate and not just client assumptions.

## Deliverables

- reliable operator/manage surfaces
- correct permission-aware UX
- explicit mutation success/failure behavior
- updated memory and `Session Log`

## Verification

- non-operators do not see or trigger operator actions incorrectly
- operators get reliable success/failure feedback
- refreshed data matches the performed mutation

## Session Log

- 2026-03-27: file created as the fifth website hardening task.

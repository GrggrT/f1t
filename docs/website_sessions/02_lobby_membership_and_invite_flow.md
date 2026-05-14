# Step 02 - Lobby Membership And Invite Flow

## Status

Planned

## Goal

Make lobby/member flows reliable and understandable:

- lobby page
- invite join flow
- lobby membership fetches
- season creation from lobby surface
- role-aware actions

## Why This Matters

Lobby/member flow is the bridge between account entry and actual competition participation. If it fails, the site stops feeling like a working league product.

## Mandatory Workflow

1. Read `C:\f1t\MEMORY.md` and this file.
2. Update `C:\f1t\MEMORY.md` when risks, plan changes, or milestones appear.
3. Append the final report to `Session Log` in this file.
4. If subagents are used, carry their results into both memory and this task file.

## What To Do

- Audit `frontend/app/lobby/[id]/page.tsx`, `frontend/app/lobby/join/page.tsx`, and related membership fetch paths.
- Verify:
  - invite-code entry
  - join success/failure states
  - lobby member list
  - active season selection
  - create season from lobby when role allows it
- Replace silent failures with explicit state.
- Make sure role-gated CTA buttons only appear when they can work.
- Confirm that lobby pages do not pretend success after failed network calls.

## Deliverables

- stable invite/join/member flow
- correct role-aware lobby behavior
- explicit error/degraded states
- updated memory and `Session Log`

## Verification

- join by invite code works or fails honestly
- lobby membership and season data are consistent
- season creation from lobby has reliable success/failure handling
- role-gated actions do not mislead the user

## Session Log

- 2026-03-27: file created as the second website hardening task.

# Step 01 - Auth Workspace And Launcher Handoff

## Status

Planned

## Goal

Stabilize the website entry flow for real users:

- login
- register
- OAuth entry points
- launcher auth handoff
- workspace landing
- `me` account surface
- player-profile linking

## Why This Is First

The user explicitly called out `login` as unstable. If auth and account entry are weak, the rest of the website feels broken even when deeper pages exist.

## Mandatory Workflow

1. Read `C:\f1t\MEMORY.md` and this file.
2. Update `C:\f1t\MEMORY.md` during the work when a new risk, contract mismatch, or milestone appears.
3. At the end of the session, append a report to `Session Log` in this file.
4. If subagents are used, copy their useful findings into both `C:\f1t\MEMORY.md` and this file.

## What To Do

- Audit `frontend/app/login/page.tsx`, `frontend/app/workspace/page.tsx`, and `frontend/app/me/page.tsx`.
- Verify real behavior for:
  - credential login
  - register -> login transition
  - Google / Steam entry points
  - launcher `poll_id` handoff path
  - unauthenticated redirects
  - linked vs unlinked player states
- Remove fake success / fake empty states.
- Add explicit degraded/error states where backend calls fail.
- Improve the login UX if it currently feels brittle or confusing, but do not prioritize visual polish over correctness.
- Verify that post-login routing is deterministic and does not fight between client redirects and launcher handoff logic.

## Deliverables

- reliable auth/member entry flow
- honest error/degraded states
- improved launcher handoff behavior
- updated memory and `Session Log`

## Verification

- successful credential login flow
- failed login shows correct error
- register flow does not leave the UI in a broken state
- launcher handoff path behaves predictably
- workspace/me surfaces reflect backend truth instead of masking errors

## Session Log

- 2026-03-27: file created as the first website hardening task because the user explicitly reported that login currently behaves poorly.

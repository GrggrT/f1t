# Website Session Prompts

Below are ready-to-paste prompts for separate website sessions.

Every prompt requires the agent to:

- read `C:\f1t\MEMORY.md` first
- then read the specific task file
- keep updating `C:\f1t\MEMORY.md` during the work
- append `Session Log` in the same task file
- carry subagent findings into both memory and the task file
- continue through implementation and verification instead of stopping at analysis

---

## Session 01

Task file: `C:\f1t\docs\website_sessions\01_auth_workspace_and_launcher_handoff.md`

```text
Work on the task from C:\f1t\docs\website_sessions\01_auth_workspace_and_launcher_handoff.md.

Mandatory rules:
1. First read C:\f1t\MEMORY.md.
2. Then read C:\f1t\docs\website_sessions\01_auth_workspace_and_launcher_handoff.md.
3. During the work, always update C:\f1t\MEMORY.md when:
   - a new risk is found
   - the plan changes
   - a meaningful milestone is completed
   - an earlier assumption about the auth/member flow turns out to be wrong
4. At the end, append Session Log in C:\f1t\docs\website_sessions\01_auth_workspace_and_launcher_handoff.md.
5. If you use subagents, carry their findings into both C:\f1t\MEMORY.md and the Session Log of this task file.
6. Do not stop at analysis. Implement fixes, verify them, and leave the flow in a materially better state.

Focus of this session:
- login
- register
- Google / Steam entry
- launcher auth handoff
- workspace landing
- me/account page
- player linking

Important user context:
- the user explicitly said the current login flow feels broken and needs real work
- prioritize correctness, explicit errors, deterministic routing, and honest degraded states over cosmetic polish

At the end:
- update C:\f1t\MEMORY.md
- update Session Log in the task file
- briefly report what was fixed, what was verified, and what still remains risky
```

---

## Session 02

Task file: `C:\f1t\docs\website_sessions\02_lobby_membership_and_invite_flow.md`

```text
Work on the task from C:\f1t\docs\website_sessions\02_lobby_membership_and_invite_flow.md.

Mandatory rules:
1. First read C:\f1t\MEMORY.md.
2. Then read C:\f1t\docs\website_sessions\02_lobby_membership_and_invite_flow.md.
3. During the work, always update C:\f1t\MEMORY.md when a new risk, plan change, milestone, or contract mismatch is found.
4. At the end, append Session Log in C:\f1t\docs\website_sessions\02_lobby_membership_and_invite_flow.md.
5. If you use subagents, carry their findings into both memory and the Session Log.
6. Do not stop at analysis. Implement and verify practical fixes.

Focus of this session:
- lobby page
- invite join flow
- membership fetches
- role-aware actions
- create season from lobby

At the end:
- update C:\f1t\MEMORY.md
- update Session Log in the task file
- briefly report what was fixed, what was verified, and what still remains risky
```

---

## Session 03

Task file: `C:\f1t\docs\website_sessions\03_competition_routes_and_data_consistency.md`

```text
Work on the task from C:\f1t\docs\website_sessions\03_competition_routes_and_data_consistency.md.

Mandatory rules:
1. First read C:\f1t\MEMORY.md.
2. Then read C:\f1t\docs\website_sessions\03_competition_routes_and_data_consistency.md.
3. During the work, keep updating C:\f1t\MEMORY.md for new risks, plan changes, milestones, or corrected assumptions.
4. At the end, append Session Log in C:\f1t\docs\website_sessions\03_competition_routes_and_data_consistency.md.
5. If you use subagents, copy their useful findings into both memory and the Session Log.
6. Do not stop at route review. Fix real behavior and verify it.

Focus of this session:
- home
- seasons
- season overview
- standings
- calendar
- live
- races archive
- race results
- canonical route model consistency

At the end:
- update C:\f1t\MEMORY.md
- update Session Log in the task file
- briefly report what was fixed, what was verified, and what still remains risky
```

---

## Session 04

Task file: `C:\f1t\docs\website_sessions\04_deep_analysis_truthfulness_and_fallbacks.md`

```text
Work on the task from C:\f1t\docs\website_sessions\04_deep_analysis_truthfulness_and_fallbacks.md.

Mandatory rules:
1. First read C:\f1t\MEMORY.md.
2. Then read C:\f1t\docs\website_sessions\04_deep_analysis_truthfulness_and_fallbacks.md.
3. During the work, update C:\f1t\MEMORY.md for new risks, milestones, or revised assumptions about deep-analysis surfaces.
4. At the end, append Session Log in C:\f1t\docs\website_sessions\04_deep_analysis_truthfulness_and_fallbacks.md.
5. If you use subagents, carry their findings into both memory and the Session Log.
6. Do not stop at diagnosis. Either complete the surface or make it honestly degrade.

Focus of this session:
- telemetry
- compare
- replay
- race analysis
- season engineer
- truthful unavailable/degraded states

At the end:
- update C:\f1t\MEMORY.md
- update Session Log in the task file
- briefly report what was fixed, what was verified, and what still remains risky
```

---

## Session 05

Task file: `C:\f1t\docs\website_sessions\05_operator_admin_and_manage_surfaces.md`

```text
Work on the task from C:\f1t\docs\website_sessions\05_operator_admin_and_manage_surfaces.md.

Mandatory rules:
1. First read C:\f1t\MEMORY.md.
2. Then read C:\f1t\docs\website_sessions\05_operator_admin_and_manage_surfaces.md.
3. During the work, update C:\f1t\MEMORY.md for permission risks, operator-flow findings, plan changes, and milestones.
4. At the end, append Session Log in C:\f1t\docs\website_sessions\05_operator_admin_and_manage_surfaces.md.
5. If you use subagents, copy their useful findings into both memory and the Session Log.
6. Do not stop at review. Implement and verify the operator-surface fixes.

Focus of this session:
- admin
- season manage
- lobby manage / moderator tools
- permission gating
- mutation feedback and refresh behavior

At the end:
- update C:\f1t\MEMORY.md
- update Session Log in the task file
- briefly report what was fixed, what was verified, and what still remains risky
```

---

## Session 06

Task file: `C:\f1t\docs\website_sessions\06_frontend_regression_and_release_readiness.md`

```text
Work on the task from C:\f1t\docs\website_sessions\06_frontend_regression_and_release_readiness.md.

Mandatory rules:
1. First read C:\f1t\MEMORY.md.
2. Then read C:\f1t\docs\website_sessions\06_frontend_regression_and_release_readiness.md.
3. During the work, update C:\f1t\MEMORY.md when the regression strategy changes, a new risk is found, or a milestone is completed.
4. At the end, append Session Log in C:\f1t\docs\website_sessions\06_frontend_regression_and_release_readiness.md.
5. If you use subagents, copy their useful findings into both memory and the Session Log.
6. Do not stop at planning. Add practical coverage, run validation, and leave a clear release/readiness state.

Focus of this session:
- regression coverage for the most valuable website flows
- release-style validation
- docs/handoff updates
- residual-risk map

At the end:
- update C:\f1t\MEMORY.md
- update Session Log in the task file
- briefly report what was verified, what coverage was added, and what still remains risky
```

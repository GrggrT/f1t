# Website Sessions

This folder breaks website hardening into separate sessions.

## Scope

The website already has a stronger shell, route model, and Russian-first presentation.
The next phase is product correctness:

- fix broken or partial user flows
- align frontend behavior with backend reality
- remove fake-empty states and silent failures
- make operator/member/deep-analysis surfaces honest and reliable

## Mandatory Rules For Every Session

1. Before starting, read:
   - `C:\f1t\MEMORY.md`
   - the selected task file from this folder
2. During the work, always update `C:\f1t\MEMORY.md` when:
   - a new risk is found
   - the plan changes
   - a meaningful milestone is completed
   - an earlier assumption about the website/backend contract turns out to be wrong
3. Keep the report in the same `.md` task file used for the session.
4. If subagents are used, the main agent must:
   - tell them to keep memory/task reporting in mind
   - copy their useful findings into `C:\f1t\MEMORY.md`
   - add their outcome to the task file `Session Log`
5. Do not delete old log entries. Only append.
6. Do not stop at analysis when the task can be carried through to code changes and verification.

## Recommended Order

1. `01_auth_workspace_and_launcher_handoff.md`
2. `02_lobby_membership_and_invite_flow.md`
3. `03_competition_routes_and_data_consistency.md`
4. `04_deep_analysis_truthfulness_and_fallbacks.md`
5. `05_operator_admin_and_manage_surfaces.md`
6. `06_frontend_regression_and_release_readiness.md`

## Why This Order

- Session 01 is first because `login` is currently a user-reported weak spot and the auth/member entry flow affects the rest of the product.
- Sessions 02 and 03 stabilize the main member and competition paths.
- Session 04 removes half-working deep-analysis experiences.
- Session 05 hardens operator surfaces and permission-sensitive tools.
- Session 06 closes the package with regression coverage and release confidence.

## End-Of-Session Log Format

Append to `Session Log`:

- date and time
- what was done
- which files changed
- what was verified
- what remains / blockers / residual risks

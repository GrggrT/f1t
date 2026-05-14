# Launcher Release Handoff (2026-03-27)

## Status

Launcher shell/UI pass is product-grade, and the current release artifacts now include the late real-runtime fixes discovered after a live personal-mode race.

The remaining work is no longer architectural or visual. It is limited to confirmatory live game/runtime validation with a real F1 25 session on the rebuilt launcher artifact.

## What Was Finished

- Rebuilt the main launcher shell into a race-control desktop tool:
  - `Race Control`
  - `Lobbies`
  - `Profile`
  - `Race Engineer`
  - `Settings`
- Completed a live `pywebview` runtime QA pass, not just mock HTML validation.
- Fixed runtime-specific issues that only appeared in the real launcher window:
  - source launcher no longer opens Chromium DevTools by default
  - login is now an operator-first access screen instead of a hero-style landing page
  - sidebar identity area handles long values cleanly
  - dashboard operations card was simplified so headline and next action stay readable in the real window
- Fixed the `Race Engineer` flicker caused by poll-driven full-page rerenders; engineer polling now patches the live view in place instead of rebuilding the whole shell every 2.5 seconds.
- Fixed a real personal-mode history gap discovered after a finished career race:
  - live telemetry worked
  - post-session `Profile` history stayed empty
  - the agent now writes completed personal sessions into `/api/practice/sessions` using the authenticated launcher user's bearer token
  - launcher profile history now shows honest recent session entries with `session_type`
- Rebuilt and published fresh launcher artifacts into `backend/static`.

## Runtime Note

Source/dev launcher debug is now opt-in.

Use:

```powershell
$env:F1_LAUNCHER_DEBUG = '1'
python -m agent.launcher
```

Without `F1_LAUNCHER_DEBUG`, the launcher starts without DevTools.

## Release Artifacts

Built on 2026-03-27.

### Files

- `C:\f1t\agent\dist\F1LeagueAgent.exe`
- `C:\f1t\agent\installer_output\Setup_F1LeagueAgent.exe`
- `C:\f1t\backend\static\F1LeagueAgent.exe`
- `C:\f1t\backend\static\Setup_F1LeagueAgent.exe`

### Sizes

- `F1LeagueAgent.exe`: `31,091,332` bytes
- `Setup_F1LeagueAgent.exe`: `32,757,951` bytes

### SHA256

- `F1LeagueAgent.exe`: `2E1BC4D6E9553CF22BCB21031C5DC58886A4DB9C88B8D353DC51737F96DB2E53`
- `Setup_F1LeagueAgent.exe`: `51806C47E274A2FEB4C545AB6F3E47E61D50A4A1EAA41F737A59095B239733EC`

## Website Distribution

Verified against the local backend:

- `GET http://localhost:8000/agent/download` -> `200`
- `GET http://localhost:8000/agent/installer` -> `200`

Expected public launcher URLs remain:

- installer: `http://YOUR_SERVER_IP:8000/agent/installer`
- portable exe: `http://YOUR_SERVER_IP:8000/agent/download`

## Validation Completed

- `python -m py_compile C:\f1t\agent\launcher.py`
- `python -m py_compile C:\f1t\agent\config.py C:\f1t\agent\personal_session_sync.py C:\f1t\agent\main.py C:\f1t\agent\launcher.py C:\f1t\tests\test_personal_session_sync.py`
- `python -m unittest C:\f1t\tests\test_personal_session_sync.py`
- `node --check C:\f1t\agent\launcher_ui\dashboard.js`
- `node --check C:\f1t\agent\launcher_ui\shell.js`
- extracted inline JS from `C:\f1t\agent\launcher_ui\index.html`; `node --check`
- source launcher runtime smoke start
- packaged launcher runtime smoke start from `agent\dist\F1LeagueAgent.exe`
- backend download endpoint check for both release URLs
- lightweight `GET` verification of both download endpoints with current artifact lengths:
  - `GET http://localhost:8000/agent/download` -> `200` (`Content-Length: 31091332`)
  - `GET http://localhost:8000/agent/installer` -> `200` (`Content-Length: 32757951`)

## What Still Needs To Be Done

This is the only meaningful launcher follow-up left.

1. Run one confirmatory real F1 25 session in `Personal` mode on the rebuilt launcher and confirm:
   - `Race Control` transitions through waiting/live/finish correctly
   - completed session appears in `Profile` history after finish
2. Run one real overlay pass on the actual monitor and DPI setup to confirm placement, readability, and widget sizing.
3. Run one real `Lobby Host` flow with explicit season binding and confirm:
   - host season selection
   - agent start in host mode
   - session detection
   - telemetry arrival
   - post-session upload/flush behavior

## Non-Blocking Notes

- Existing `%USERPROFILE%\f1league_agent\launcher_config.json` may still contain environment-specific URLs. This is intentional and should not be auto-overwritten during release prep.
- The launcher is now honest about degraded backend/profile states; some screens intentionally show degraded mode instead of pretending the data is empty.
- The already completed personal-mode race that exposed the history gap could not be backfilled automatically because the checked local `telemetry_flush_cache.json` and `raw_logs` were empty by the time the issue was diagnosed.

## Command Used For This Release

```powershell
cmd /c agent\build_launcher.bat
```

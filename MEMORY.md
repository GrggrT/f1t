# Project Memory

## Current Focus

- Area: launcher late-runtime follow-ups are being closed after the first real F1 25 personal-mode validation pass; once the rebuilt launcher is revalidated, the next primary focus remains website implementation hardening and fixing incomplete or broken product flows across the frontend/backend contract
- Goal: keep release artifacts and launcher/runtime behavior aligned with real usage while preserving the website hardening track as the next major delivery area
- User request: after real launcher usage exposed remaining runtime/product gaps, fix them, keep memory/docs synced, and rebuild the installer/site binaries

## Latest Context

- `docs/core_reliability_sessions/01-06` are completed, and the local memory already contains their implementation and validation results.
- Additional follow-up `docs/core_reliability_sessions/05_1_backend_integration_coverage.md` is also completed.
- Launcher release hardening, packaging, backend delivery artifacts, and website shell/localization addenda were already landed on `2026-03-27`.
- A later real launcher pass surfaced two additional launcher-specific product/runtime issues:
  - `Race Engineer` visibly flickered because polling triggered a full page rerender every 2.5 seconds
  - a real personal-mode career race produced live telemetry but no visible session history in `Profile`
- Both launcher issues were fixed in source, and fresh release artifacts were rebuilt/copied into `backend/static` on `2026-03-27`.
- The next workstream should still be website-focused once one confirmatory live pass validates the rebuilt launcher behavior.
- Added `docs/website_sessions` with a dedicated website hardening session pack and ready-to-paste prompts.
- Website Session 01 is intentionally focused on `login`, `workspace`, `me`, and launcher auth handoff because the user explicitly reported that the current login flow still behaves poorly.

## Website Workstreams

1. Product-flow audit and route normalization:
   - verify the canonical path model `Home -> Seasons -> Season -> Race`
   - keep legacy redirects thin and eliminate behavior drift between old and new routes
2. Account/member/workspace correctness:
   - login, register, launcher handoff, workspace, `me`, player linking, lobby membership, and invite flow
   - replace fake-empty states with explicit degraded/error states where backend contracts fail
3. Competition surfaces:
   - seasons, standings, calendar, race pages, live state, and race archive consistency
   - ensure page data, counts, links, and CTA chains agree with backend reality
4. Deep-analysis surfaces:
   - telemetry, compare, replay, engineer, and race analysis
   - decide which areas are production-ready and which need honest limited/unavailable states
5. Operator surfaces:
   - lobby manage, season manage, admin tools, and permission gating
   - ensure operator actions are explicit and do not fail silently
6. Frontend regression coverage:
   - add targeted tests/smoke checks for the highest-value website flows after contract cleanup

## Confirmed Problems

- Launcher/backend contract is inconsistent for lobbies and seasons
- Status polling in JS expects fields that Python does not return
- Start/stop flows can report success even when Python returned an error
- `server_url`, `ws_url`, and `frontend_url` are not managed coherently
- Current defaults are hardcoded to an old LAN IP and break first-run usability
- Overlay can conflict with the agent because the launcher may start a second overlay server
- Dashboard hides real state and mostly shows a binary running/stopped view
- AI engineer context depends too much on overlay data instead of agent live state
- UI styling is generic and does not feel intentional or trustworthy

## Planned Changes

1. Fix Python API contract and config normalization.
2. Redesign the launcher UI into a race-control style dashboard.
3. Add diagnostics and operator tooling:
   - backend/frontend health check
   - pending upload visibility
   - open data folder
   - better live session summary
4. Improve overlay handling so the same server instance is reused.
5. Improve AI engineer live context extraction.
6. For core reliability session 01, add a reproducible parser/replay harness that runs on `RawLogger`-style binary logs and local fixtures without a live race.
7. Validate parser behavior against the installed `f1-packets==2025.1.1` structures and document any packet-type coverage gaps.

## Constraints

- Keep updating this file after major steps to preserve context.
- Figma-related skills exist on disk, but they are not declared as available in the current session instructions, so the launcher redesign is being done directly in code.

## Progress Update

- Closed the local core reliability package end-to-end: packet parser + replay harness, agent runtime/state machine hardening, upload idempotency/cache recovery, telemetry pipeline integrity, backend contracts/regression coverage, and live validation/postmortem tooling are all marked `Completed` in `docs/core_reliability_sessions`.
- Confirmed the extra follow-up `docs/core_reliability_sessions/05_1_backend_integration_coverage.md` is also `Completed`.
- Project sequencing is now explicit: launcher stabilization and core reliability are done; website implementation/correctness is the next major delivery area.
- Added `agent/replay_harness.py`, which can generate a `RawLogger`-format fixture log, replay any raw log through `parse_packet(...)`, and optionally smoke-replay the same bytes through `F1Agent._on_packet(...)` without a live race.
- Hardened `agent/packet_parser.py` for the installed `f1-packets==2025.1.1` by bypassing the library's incompatible built-in 2025 packet-id map with a manual 2025 class map before unpacking.
- Reworked `agent/packet_parser.py` normalization so `ctypes` arrays become plain Python lists, `c_char` buffers become decoded strings, and `snake_case` packet fields are converted back into the legacy `m_*` contract expected by the rest of the agent.
- Fixed `agent/packet_parser.py` extractor coverage for the current library shapes: `Event` now selects the active union payload by event code, `SessionHistory` recomposes sector times from minute/ms parts, `LapPositions` now reads the flat `position_for_vehicle_idx` buffer, and `CarTelemetry` exposes tyre surface temperatures.
- Fixed `shared/packet_format.py` so 2024/2025 compatibility quirks now apply to nested `m_lapData` / `m_participants` entries instead of incorrectly touching only the top-level packet dict.
- Fixed `agent/state_machine.py` to use ASCII transition logging (`->`) instead of a Unicode arrow that can crash replay/runtime flows on cp1250-style Windows consoles.
- Updated `agent/packet_parser.py` to support both legacy `unpack_udp_packet(...)` and current `f1.packets.resolve(...)`, which restores real telemetry parsing with the installed `f1-packets==2025.1.1`.
- Fixed `_to_dict()` in `agent/packet_parser.py` so nested dict fields are preserved instead of being degraded into lists of keys during packet normalization.
- Rebuilt the launcher dashboard around a viewport-first desktop layout: fixed-height shell, dashboard-specific grid zones, equal-height card rows, compact metrics row, and scrollable panel bodies only where content can exceed the allocated space.
- Tightened the dashboard into a predictable spacing system using shared shell/panel/control tokens and added compact desktop height rules for 1600x900 and 1366x768-style windows.
- Reworked launcher packaging around a stable `agent/F1LeagueAgent.spec` with relative paths instead of a hardcoded `C:/f1t` build root.
- Replaced the legacy Windows build/install scripts so they now target the launcher flow, copy release artifacts into `backend/static`, and can compile the Inno Setup installer from the same command.
- Cleaned installer defaults for first-run distribution: per-user install path under LocalAppData, no stale `nip.io` metadata URL, and firewall rule creation now removes old duplicates before re-adding the UDP rule.
- Updated launcher config loading so first launch writes a normalized `%USERPROFILE%\f1league_agent\launcher_config.json` with localhost defaults instead of relying on an implicit in-memory-only config.
- Removed the stale LAN IP from backend fallback CORS defaults; cross-machine access now depends on explicit environment configuration instead of an old hardcoded local network value.
- Updated `QUICKSTART.md` to document the real launcher-first install/start flow (`/agent/installer`, `/agent/download`, launcher-side backend target) and moved Python source setup into a separate dev path.
- Rebuilt `agent/launcher.py` around normalized config and derived URLs.
- Fixed launcher/backend mapping for lobbies and seasons.
- Added richer agent status and live session summary.
- Added diagnostics endpoints for backend/frontend/auth/cache/overlay.
- Added operator action to open the local launcher data folder.
- Reworked overlay lifecycle so the launcher reuses the same overlay server instance instead of blindly starting another one.
- Replaced `agent/launcher_ui/index.html` with a new race-control style UI.
- Added launcher-side diagnostics, dashboard control flow, lobby detail view, profile surface, improved engineer screen, and a rewritten settings/overlay lab.
- Aligned `agent/overlay/overlay.html` custom position mapping with the new launcher widget model.
- Finalized overlay sync contract around 8 widgets: `timing`, `session`, `delta`, `speed`, `pedals`, `tyres`, `ers`, `engineer`.
- Rebuilt `agent/overlay/overlay.html` into a stronger race-presentation HUD using the same layout map as the launcher overlay lab.
- Reworked launcher overlay lab so preview opacity, drag positions, double-click visibility toggles, save, reset, and `Open Overlay` all use the same current draft state.
- Updated `agent/overlay_server.py` so new browser overlay clients immediately receive the latest timing, car, session, and delta snapshots instead of waiting for the next packet.
- Added a dedicated backend host-season catalog at `GET /api/lobby/host-seasons` so the launcher no longer assembles host mode season choices with N+1 lobby requests.
- Added launcher-side host operations for lobby creation and invite reset, and rewired the host workflow around that richer contract.
- Hardened lobby host start validation so a stale saved `season_id` can no longer start host mode unless it still exists in the current user's lobby memberships.
- Reworked launcher host UI so the selected season is explicit on the dashboard, host mode stays blocked without a valid season, and lobby detail pages can directly select a season for host mode.
- Added launcher-side runtime observability with recent events, component health snapshots, richer startup/shutdown phases, recovery guidance, and manual retry for cached uploads.
- Added explicit launcher surfacing for websocket, UDP, upload, and overlay failures instead of collapsing everything into a single generic agent error.
- Hardened console-side error logging for localized Windows socket exceptions so observability paths no longer crash on `UnicodeEncodeError` while printing failures.
- Final polish pass cleaned launcher product language and CTA labels across login, dashboard, lobbies, profile, engineer, settings, and sidebar actions.
- Added honest degraded states for `lobbies` and `profile`, so backend/profile API failures no longer masquerade as empty user data.
- Removed the stray overlay-side position parsing `console.log(...)` and documented a launcher release smoke checklist plus residual risks in `QUICKSTART.md` and the step 06 session file.
- Fixed `Race Engineer` flicker in `agent/launcher_ui/index.html` by removing the poll-driven full-page rerender and introducing local engineer view syncing for toolbar/context/message areas, so the launcher no longer looks like it is reloading every 2.5 seconds while that page is open.
- Fixed personal-mode session history persistence after a real career-race validation exposed that live telemetry worked but `Profile` history stayed empty:
  - added `agent/personal_session_sync.py` to persist completed personal sessions into `/api/practice/sessions` with the authenticated launcher user's bearer token
  - updated `agent/main.py` so completed personal sessions trigger a background personal-history sync after session finalization
  - updated `agent/launcher.py` to pass `F1_AGENT_MODE`, surface personal-session sync events, and expose `session_type` in profile session entries
  - updated `agent/launcher_ui/index.html` so `Profile` now presents honest "sessions/recent runs" history instead of practice-only copy
- Rebuilt the launcher exe + installer after the `Race Engineer` flicker and personal-session-history fixes, and refreshed the website download artifacts in `backend/static`.

## Current Validation

- `python -m py_compile agent/packet_parser.py agent/replay_harness.py shared/packet_format.py agent/state_machine.py tests/test_packet_replay_harness.py` passed.
- `python -m unittest tests/test_packet_replay_harness.py` passed.
- `python -m agent.replay_harness --self-test --json` passed and confirmed:
  - parser backend is `resolve+manual_2025_packet_map`
  - replay fixture covers Session, Participants, Motion, LapData, Event, CarTelemetry, CarStatus, CarDamage, SessionHistory, LapPositions, and FinalClassification
  - smoke replay through `F1Agent` reaches `finished`, captures 2 classification entries, records 1 event, and produces telemetry samples without a live race
- Direct probe showed the installed `f1.packets.resolve(...)` misroutes or rejects official 2025 packet ids beyond the early packets (for example FinalClassification bytes with `packet_id=11` raise `ValueError` under the library's built-in map), which is why the manual 2025 class map is now required.
- `python -m py_compile agent/packet_parser.py agent/main.py` passed after the parser compatibility fix.
- Runtime smoke-check of `agent.packet_parser` confirmed the active parser path now uses the installed `resolve(...)` stack with a local compatibility layer instead of falling back to the fake raw-packet stub.
- Headless Playwright viewport probe against the launcher dashboard passed at `1920x1080`, `1600x900`, and `1366x768`: `bodyOverflow=false`, `workspaceOverflow=false`, `pageOverflow=false`, and the bottom dashboard zone remained visible in all three cases.
- Visual screenshots were reviewed for `1600x900` and `1366x768` after the layout rewrite to confirm the grid stayed aligned and the lower panels remained visible.
- `cmd /c agent\build_launcher.bat` passed after switching the spec from `__file__` to `SPECPATH`; fresh artifacts were rebuilt into `agent/dist`, `agent/installer_output`, and `backend/static`.
- `pyi-archive_viewer agent/dist/F1LeagueAgent.exe -l` confirmed the packaged launcher includes `launcher_ui/index.html`, `launcher_ui/game_bg.jpg`, and `agent/overlay/overlay.html`.
- Packaged `agent/dist/F1LeagueAgent.exe` starts successfully from the built artifact and stays alive beyond the initial boot window.
- Packaged launcher also starts with Python removed from `PATH`, which confirms first-run launcher boot does not depend on a local Python dev environment.
- Silent install of `agent/installer_output/Setup_F1LeagueAgent.exe` into a temp directory succeeded, and the installed `F1LeagueAgent.exe` also starts successfully from that installed location.
- Re-running the fresh installer now leaves a single `F1 League Agent UDP` firewall rule instead of accumulating duplicates on each install.
- `python -m py_compile agent/launcher.py` passed.
- Extracted launcher JS from `agent/launcher_ui/index.html` and `node --check` passed.
- `python -m py_compile agent/launcher.py` and `node --check` on the extracted launcher JS both passed after the dashboard polling rerender fix.
- `node --check` on the extracted launcher JS still passed after the later dashboard patching rewrite that limits polling updates to individual sections instead of replacing the whole dashboard page.
- `python -m py_compile agent/launcher.py` passed after the launcher Russification pass.
- Extracted JS from both `agent/launcher_ui/index.html` and `agent/overlay/overlay.html`; `node --check` passed after translating the launcher and overlay UI to Russian.
- Basic Python smoke-check of `LauncherAPI()` passed.
- Legacy saved config was normalized correctly into the newer overlay widget contract before the engineer widget was added to the synced layout.
- `python -m py_compile agent/launcher.py agent/overlay_server.py` passed after the overlay sync session.
- Extracted JS from both `agent/launcher_ui/index.html` and `agent/overlay/overlay.html`; `node --check` passed for both.
- `python -m py_compile agent/launcher.py backend/routers/lobby.py` passed after the host-mode session.
- Extracted launcher JS from `agent/launcher_ui/index.html`; `node --check` passed after the host workflow changes.
- Local smoke-check against `http://localhost:8000` confirmed `LauncherAPI().get_host_seasons()` follows the new backend route and `start_agent("lobby", "1")` now rejects a stale non-lobby season instead of starting host mode.
- `python -m py_compile agent/launcher.py agent/main.py agent/ws_client.py agent/udp_listener.py agent/overlay_server.py agent/uploader.py` passed after the observability session.
- Extracted launcher JS from `agent/launcher_ui/index.html`; `node --check` passed after the observability/recovery UI changes.
- Runtime probe on `LauncherAPI()` confirmed the healthy path now reports startup `ready`, UDP `listening`, websocket `connected`, and recent events populate as expected.
- Forced UDP port conflict now returns launcher status `Start failed`, marks startup/UDP as `error`, and records recent events instead of leaving the launcher in a false `running` state.
- `python -m py_compile agent/launcher.py agent/overlay_server.py` passed after the final polish pass.
- Extracted JS from both `agent/launcher_ui/index.html` and `agent/overlay/overlay.html`; `node --check` passed after the final polish cleanup.
- Playwright smoke probe with a mock `pywebview` API passed across dashboard, lobbies, lobby detail, profile, engineer, settings, and login, and also covered degraded `lobbies` / `profile` states plus `openSite()` success/error feedback with no console or page errors.
- Extracted launcher JS from `agent/launcher_ui/index.html`; `node --check` passed after the later `Race Engineer` flicker fix.
- Code inspection confirmed the engineer poller no longer calls `layout(renderEngineer())` on each poll tick; only the initial navigation render remains full-page, while later engineer updates use `syncEngineerView()`.
- `python -m py_compile C:\f1t\agent\config.py C:\f1t\agent\personal_session_sync.py C:\f1t\agent\main.py C:\f1t\agent\launcher.py C:\f1t\tests\test_personal_session_sync.py` passed after the personal-session-history fix.
- `python -m unittest C:\f1t\tests\test_personal_session_sync.py` passed.
- Extracted launcher JS from `agent/launcher_ui/index.html`; `node --check` passed after the `Profile` session-history update.
- `cmd /c agent\build_launcher.bat` passed again after the late launcher fixes; fresh artifacts were rebuilt into `agent/dist`, `agent/installer_output`, and `backend/static`.
- Lightweight `GET` checks confirmed the local backend currently serves the refreshed launcher artifacts:
  - `GET http://localhost:8000/agent/download` -> `200` (`Content-Length: 31091332`)
  - `GET http://localhost:8000/agent/installer` -> `200` (`Content-Length: 32757951`)

## Open Notes

- Existing real user `.env` and saved launcher config still contain environment-specific LAN values; product defaults and packaging scripts were cleaned, but release operators should still review deployment-specific `.env` before distributing artifacts.
- Existing saved launcher config currently points to `http://192.168.0.114:8000`.
- This was intentionally not auto-overwritten, because it may still be a real target in the user's environment.
- The new launcher now makes this visible and editable from the login screen and full settings screen.
- Added `C:\f1t\docs\launcher_sessions\` with step-by-step follow-up task files for separate sessions.
- Future agents should read `C:\f1t\MEMORY.md` plus the chosen task file, keep updating memory, and append reports into that same task file.
- Launcher session pack `01` through `06` is now complete; task-file statuses were normalized to `Completed`.
- Automated validation is clean, but browser-level visual QA of the new overlay/launcher preview match is still worth doing in a live pywebview session with real telemetry.
- Browser-level QA is still worth doing for the new host workflow in a live pywebview session, especially around create-lobby, invite reset, and season selection on real user data.
- Browser-level QA is still worth doing for the new observability panels in a live pywebview window, especially around backend/frontend outage messaging, manual retry UX, and recent-events readability under real failures.
- One real personal-mode career pass already ran and directly surfaced a missing post-session history writeback path; that gap is now fixed in code and included in the rebuilt artifacts.
- The already completed race that exposed the personal-history gap could not be recovered automatically from local cache because the checked `telemetry_flush_cache.json` and `raw_logs` were empty at diagnosis time.
- The main remaining launcher confidence gap is now one confirmatory live pass on the rebuilt artifact to verify:
  - personal-mode session history appears in `Profile` after a finished run
  - overlay placement/readability still holds on the real monitor/DPI setup
  - `Lobby Host` still works end-to-end with real season binding and a live game session
- Fresh installer/site binaries were rebuilt after the `Race Engineer` flicker and personal-session-history fixes and copied into `backend/static`.
- Release handoff now lives in both `QUICKSTART.md` and `docs/launcher_sessions/06_final_polish_and_release_check.md`.
- Added `C:\f1t\docs\core_reliability_sessions\` with the next session pack for parser/runtime/upload/telemetry hardening.
- Added `C:\f1t\docs\core_reliability_sessions\PROMPTS.md` with ready-to-paste prompts for sessions 01-06, each explicitly requiring `MEMORY.md` updates and `Session Log` updates in the corresponding task file.
- After the core reliability pack is finished, the next major focus shifts to website implementation and fixing incomplete/broken site functionality.
- Core reliability session 01 started on 2026-03-27 with focus on parser stability and replay tooling around `agent/packet_parser.py`.
- Confirmed local environment uses `f1-packets==2025.1.1`, where `f1.packets.resolve(...)` is the active parser entrypoint and `unpack_udp_packet(...)` is absent.
- No existing `session_*.bin` raw logs were found under the standard `C:\Users\Administrator\f1league_agent\raw_logs` path, so this session needs a reproducible fixture/log generation path in addition to support for future captured logs.
- Coverage risk remains for packet types that are not currently extracted or normalized beyond the generic `_to_dict()` conversion; replay validation should make those gaps explicit instead of assuming all packet layouts are safe.
- Corrected an earlier assumption from the previous session: switching to `resolve(...)` alone did not restore real telemetry parsing end-to-end.
- Validation on actual `bytes(PacketSessionData())` confirmed the installed library emits `snake_case` fields (`header.track_id`, `participants`, `car_status_data`, etc.), while current extractors still expect legacy `m_*` names.
- `_to_dict()` also leaves `ctypes` arrays such as `participants` as typed arrays instead of plain Python lists, which would still break nested `.get(...)` access even after key normalization.
- `shared/packet_format.py` currently normalizes the wrong level for both LapData and Participants packets: it touches top-level packet dicts instead of the nested per-car/per-participant entries, so the intended 2024/2025 compatibility adjustments are effectively inert.
- No captured real `session_*.bin` race logs were available in the default raw-log directory during this session; the new replay path is currently validated on a synthetic but protocol-accurate fixture generated from the installed `f1-packets` structs.
- Replay validation now covers the main packet families used by the current telemetry pipeline, but a future follow-up should still run the harness against a real captured race log once one exists.
- Several extractors and live-pipeline paths still operate on a fixed `20` car loop rather than using the full `22`-slot F1 25 packet capacity or the active participant count; this can still produce sparse ghost entries in synthetic/small-field scenarios and remains worth tightening in a later reliability step.

## Runtime QA Findings (2026-03-26)

- Verified in hidden `pywebview` runtime against live local `backend` and `frontend` containers.
- Login screen connection target change works and persists across launcher restart.
- Main happy-path pages render and work: dashboard, lobbies, lobby detail, profile, engineer, settings, and start/stop agent.
- Fixed runtime bugs:
  - settings no longer accept non-numeric or out-of-range UDP ports
  - malformed backend/frontend/websocket URLs with invalid ports now return controlled validation errors instead of throwing traceback-level exceptions
  - dashboard operator checklist now reflects the actual configured UDP port instead of a hardcoded `20777`
  - failed agent start no longer produces duplicate error toasts from action handling plus later polling
- Fixed later runtime/layout issues:
  - `agent/packet_parser.py` no longer falls back to the fake raw-packet stub on systems with `f1-packets==2025.1.1`; it now uses `f1.packets.resolve(...)`
  - the dashboard main screen now fits inside a single desktop viewport without workspace/body scrolling at `1920x1080`, `1600x900`, and `1366x768`
  - dashboard latency polling no longer rebuilds the entire launcher shell on each tick; the poller now refreshes only `.page-dashboard`, which removes the visible full-screen flash when backend latency updates
  - dashboard polling was tightened further after live QA showed residual flicker: the launcher now compares per-section signatures and patches only the sections whose visible content actually changed, so backend latency jitter should no longer repaint summary/control/diagnostics cards that did not change
  - launcher UI, overlay UI, launcher-side diagnostics/status messages, and engineer/runtime copy were translated to Russian so the product no longer mixes Russian screens with leftover English labels
  - launcher now localizes component-state pills, relative time labels, lobby roles, and host-season statuses instead of exposing raw internal English state strings in the UI
- Restored the pre-session launcher config in `C:\Users\Administrator\f1league_agent\launcher_config.json` after QA to avoid leaving user-specific state changed.
- Additional operational note from the observability session:
  - Localized Windows socket errors can contain non-ASCII text; raw `print(exc)` in worker threads was able to trigger `UnicodeEncodeError` on the console code page, so exception logging was normalized to safe ASCII escaping in launcher-side runtime components.
- Packaging/session findings:
  - `agent/F1LeagueAgent.spec` previously hardcoded `C:/f1t`, which made release builds path-dependent on the current machine.
  - `scripts/build_agent_exe.bat` and `scripts/install_agent.bat` were still wired to the legacy `agent.main` flow instead of the launcher.
  - `agent/build_launcher.bat` previously used `--add-data ".;agent"`, which risked bundling generated folders such as `dist` and `installer_output` back into the exe.
  - `agent/installer.iss` previously targeted `{autopf}` despite `PrivilegesRequired=lowest`, carried a stale `192.168.0.114.nip.io` URL, and could accumulate duplicate firewall rules on repeated installs.

## Active Session Notes (2026-03-27, Core Reliability 02)

- Read `C:\f1t\MEMORY.md` and resumed work on the core reliability session pack.
- Current focus for this session: harden `agent` runtime lifecycle, state-machine transitions, startup/shutdown/reconnect behavior, and UDP/WebSocket race handling.
- Initial plan: read `docs/core_reliability_sessions/02_agent_runtime_and_state_machine.md`, inspect runtime/state-machine code paths, implement lifecycle fixes, then run targeted verification and append session logs.
- Read `docs/core_reliability_sessions/02_agent_runtime_and_state_machine.md`; confirmed the requested focus is runtime lifecycle hardening around UDP, WebSocket, startup/shutdown, reconnects, and state transition guarantees.
- New risk discovered: the task file currently renders with mojibake on this machine, so final `Session Log` updates must preserve/handle the existing file encoding carefully.
- Opened `agent/main.py`, `agent/state_machine.py`, `agent/udp_listener.py`, `agent/ws_client.py`, `agent/uploader.py`, `agent/telemetry_buffer.py`, `agent/raw_logger.py`, `agent/launcher.py`, `agent/local_cache.py`, and `agent/replay_harness.py` to inspect lifecycle behavior end-to-end.
- Confirmed concrete runtime defects before implementation:
  - duplicate `FinalClassification` packets can spawn duplicate upload workers because only completed uploads are deduplicated
  - failed upload or missing participants leave the agent stuck in `FINISHED`, which blocks the next race without restarting the process
  - session rollover to a new `session_uid` does not stop/reset the previous raw-log and telemetry lifecycle safely
  - stale packets from an old session can contaminate a newer session because non-session packets are not checked against the active `session_uid`
  - `WSClient.stop()` can wait for reconnect backoff instead of waking immediately, and `UDPListener.stop()` does not proactively close the socket to unblock receive
- Implementation plan refined: harden the state machine, serialize session state mutations inside `F1Agent`, add active-session packet guards and upload de-duplication, make session rollover/reset deterministic, and add focused tests for rollover/failure/reconnect behavior.
- Implemented lifecycle hardening in code:
  - rewrote `agent/state_machine.py` with explicit allowed transitions, rejection logging for invalid transitions, and internal locking
  - rewrote `agent/main.py` so session mutations are serialized under an `RLock`, stale packets are ignored after rollover, duplicate `FinalClassification` packets are suppressed, upload success/failure no longer leaves the runtime stuck in `FINISHED`, and session rollover now stops/reset the old raw-log and telemetry collectors deterministically
  - added `F1Agent.start_runtime()` / `shutdown()` so launcher and console flows use the same startup/shutdown lifecycle
  - rewrote `agent/telemetry_buffer.py` to support `stop_and_snapshot()` plus later flush-by-`race_id`, which lets the runtime finalize one race cleanly before the next session begins
  - rewrote `agent/ws_client.py` so `stop()` wakes reconnect backoff immediately and joins the worker thread
  - rewrote `agent/udp_listener.py` so `stop()` closes the socket promptly and the listener can report recovery back to `listening` after transient callback/runtime errors
  - updated `agent/replay_harness.py` to match the new upload-worker entrypoint
  - added `tests/test_agent_runtime_lifecycle.py` for invalid transition rejection, duplicate final-classification de-duplication, upload-failure reset, stale-final-classification rollover protection, and websocket stop-during-reconnect behavior
- Validation completed for Core Reliability session 02:
  - `python -m py_compile agent/main.py agent/state_machine.py agent/telemetry_buffer.py agent/udp_listener.py agent/ws_client.py agent/replay_harness.py agent/auto_scan.py tests/test_agent_runtime_lifecycle.py tests/test_packet_replay_harness.py` passed
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness` passed
  - `python -m py_compile agent/launcher.py` passed after switching launcher lifecycle calls onto `F1Agent.start_runtime()` / `shutdown()`
  - `python -m agent.replay_harness --self-test --json` passed with final state `finished`, 2 classification entries, 1 event, 1 session-history entry, and non-zero telemetry/live snapshot counts under the new detach-and-flush lifecycle
- Additional runtime defect fixed during validation: `agent/auto_scan.py` still printed a Unicode arrow in its summary and could crash on cp1250 Windows consoles; it now uses ASCII-safe output.
- Residual risks after this session:
  - cached upload recovery still preserves race result payloads, but detached high-rate telemetry snapshots are not yet persisted across process restarts if the initial upload never obtains a `race_id`
  - replay/self-test still shows `live_entries=20` because some live-pipeline structures continue to assume the legacy fixed 20-car loops instead of a tighter active-field count
  - the new lifecycle logic is covered by unit/replay tests, but it still deserves one live pywebview race-day pass with real UDP + backend reconnects to verify launcher-facing UX under real network jitter
- Completed session closure tasks: updated `docs/core_reliability_sessions/02_agent_runtime_and_state_machine.md`, set its status to `Completed`, and appended a detailed `Session Log` for the implementation and validation work from this session.

## Active Session Notes (2026-03-27, Core Reliability 03)

- Read `C:\f1t\MEMORY.md` and `docs/core_reliability_sessions/03_race_upload_idempotency_and_cache.md` before starting implementation for this session.
- Current focus for this session: harden race-result upload idempotency, local cache durability, retry-after-restart behavior, duplicate protection, and backend guarantees around `session_uid`.
- New risks confirmed during initial inspection:
  - `agent/local_cache.py` performs unsynchronized read/write/replace operations on the JSON cache file, while launcher manual retry and runtime upload workers can run concurrently; this can corrupt the cache or lose one of the pending entries.
  - `agent/local_cache.py` treats any read/parse failure as `[]`, which effectively hides pending races after cache corruption instead of preserving or recovering them.
  - `agent/uploader.py` only stores the raw payload and does not persist retry metadata such as attempt count, last attempt time, or last error, so restart recovery is opaque and harder to reason about operationally.
  - `backend/routers/races.py` currently uses a check-then-insert dedupe flow around `session_uid`; the database unique constraint exists, but concurrent duplicate submits can still surface as `IntegrityError`/500 because that path is not caught and normalized into an idempotent duplicate response.
  - Backend duplicate responses currently omit the existing `race_id`, which means a request that actually committed server-side but lost its response cannot help the client finish same-process follow-up work that depends on `race_id`.
- Session 03 implementation plan:
  1. Rework the local cache into a locked, metadata-aware, backward-compatible store with safer writes and clearer pending-entry state.
  2. Update the uploader and launcher diagnostics to use that richer cache state and make retry-after-restart behavior visible and predictable.
  3. Strengthen backend race submission so duplicate/concurrent `session_uid` submits resolve into a stable idempotent response instead of an internal error.
  4. Add focused tests for success, duplicate replay, retry-after-restart, and backend duplicate races, then append the final session log and mark the task complete.
- Implemented cache/upload hardening for Session 03:
  - rewrote `agent/local_cache.py` around a locked, metadata-aware cache entry format with backward-compatible legacy entry normalization, atomic writes, backup/tmp fallback recovery, and retry metadata (`saved_at`, `last_attempt_at`, `attempt_count`, `last_error`, `last_outcome`)
  - updated `agent/uploader.py` to use the richer cache state, record attempt/failure metadata, preserve cached entries across retries, and emit clearer observer payloads for launcher diagnostics
  - updated `agent/launcher.py` pending-upload diagnostics so the launcher snapshot now reads the new cache-entry shape and exposes retry metadata instead of only the raw payload fields
  - hardened `backend/routers/races.py` so duplicate submits now return the existing `race_id` / `round` / `track`, and `IntegrityError` on the unique `session_uid` path is normalized back into an idempotent duplicate response instead of bubbling as a 500
- Validation completed for Session 03:
  - `python -m py_compile agent/local_cache.py agent/uploader.py agent/launcher.py backend/routers/races.py tests/test_upload_cache.py tests/test_race_submit_idempotency.py tests/test_agent_runtime_lifecycle.py tests/test_packet_replay_harness.py` passed
  - `python -m unittest tests.test_upload_cache tests.test_race_submit_idempotency` passed
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency` passed
- Remaining risks after Session 03:
  - race-result upload idempotency and restart retry are now stronger, but lap telemetry/session-history uploads are still fire-and-forget after `race_id` is known; if those follow-up calls fail after the race result itself is accepted, telemetry can still be incomplete across a restart
  - cache recovery now restores from the main file, backup, or tmp snapshot, but it is still designed around one launcher/agent process family; truly independent multi-process writers against the same cache file remain unsafe
- unit coverage is strong for duplicate/retry paths, but one live backend/network-chaos pass is still worth doing to observe launcher UX under real request timeouts and duplicate submit recovery

## Active Session Notes (2026-03-27, Core Reliability 04)

- Read `C:\f1t\MEMORY.md` and `docs/core_reliability_sessions/04_telemetry_pipeline_integrity.md` before starting implementation for this session.
- Current focus for this session: harden telemetry buffering, `race upload -> race_id -> telemetry flush` sequencing, lap/session-history consistency, and backend telemetry endpoint contracts.
- The session started with a mojibake/encoding risk in `04_telemetry_pipeline_integrity.md`; the task file was later rewritten in clean ASCII while preserving the same structure and final session log so future sessions do not inherit that encoding issue.
- Initial code inspection covered `agent/telemetry_buffer.py`, `agent/main.py`, `agent/uploader.py`, `backend/routers/telemetry.py`, and `backend/models/models.py`.
- Concrete integrity gaps confirmed during initial inspection:
  - `agent/telemetry_buffer.py` accepts `last_lap_ms` in `update_lap(...)` but never stores it in the buffered lap payload, so flushed telemetry rows are uploaded with `lap_time_ms=None`, which can break `/best` and `/compare` despite the samples existing.
  - telemetry flush after a successful race upload is still fire-and-forget: `flush_snapshot()` spawns raw threads for lap/session-history posts with no retry, no local cache, and no launcher-visible recovery path, so telemetry can still disappear silently after `race_id` is known.
  - backend telemetry writes use check-then-insert dedupe in `backend/routers/telemetry.py` without database uniqueness or `IntegrityError` normalization, so concurrent duplicate lap/history submits can still race into duplicates or 500s.
- Session 04 implementation is in progress with the following changes already landed:
  - rewrote `agent/telemetry_buffer.py` so per-lap snapshots now retain both samples and `lap_time_ms`, propagate completed-lap timing from `LapData.last_lap_ms`, and backfill missing lap times from `SessionHistory` before flush
  - added `agent/telemetry_delivery.py` plus `TELEMETRY_CACHE_FILE`, which persist telemetry snapshots by `session_uid`, bind them to `race_id` after race upload success/duplicate recovery, and retry failed telemetry flushes across restarts
  - updated `agent/main.py` and `agent/uploader.py` so telemetry snapshots are cached before race upload reset, race upload success attaches `race_id` to any pending telemetry snapshot, and runtime startup now retries both cached race uploads and cached telemetry flushes
  - reworked `backend/routers/telemetry.py` around idempotent lap/history upserts, `lap_time_ms` backfill from session history, fallback best-lap selection for legacy rows with missing lap times, and explicit GET session-history contracts
  - aligned `backend/models/models.py` with the existing unique indexes for `lap_telemetry` and `race_session_history`, so model metadata now matches the migration-level integrity guarantees already expected by the router code
- Validation completed for Session 04:
  - `python -m py_compile agent/telemetry_buffer.py agent/telemetry_delivery.py agent/main.py agent/uploader.py agent/config.py backend/routers/telemetry.py backend/models/models.py tests/test_telemetry_pipeline_integrity.py agent/replay_harness.py` passed
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency tests.test_telemetry_pipeline_integrity` passed
  - `python -m agent.replay_harness --self-test --json` passed after adapting the harness to the new persistent telemetry snapshot path
- Late sequencing gap fixed before closeout:
  - `agent/launcher.py` previously retried only cached race-result uploads before launcher-start/manual retry and then started `F1Agent` with `retry_cached_uploads=False`, which could strand telemetry snapshots that had just received a `race_id`; launcher-side pre-start/manual retry now also runs `telemetry_delivery.retry_pending()`
- Additional validation after the launcher sequencing fix:
  - `python -m py_compile agent/launcher.py` passed
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency tests.test_telemetry_pipeline_integrity` passed again after the launcher retry-path patch
- Remaining integrity gaps after Session 04:
  - telemetry durability is now preserved across restart until `race_id` is known and flush succeeds, but there is still no launcher/UI surfacing for the separate telemetry-flush queue; operators only see the race-result cache directly today
  - replay/self-test still reports `live_entries=20` / `telemetry_latest_entries=20`, which confirms the older fixed-car-count assumptions in parts of the live pipeline are still present outside this session’s flush/integrity scope
- backend telemetry contracts are now much safer for ordering/idempotency, but they are still validated through unit/replay coverage rather than a live backend race with forced HTTP failures; one real race-day chaos pass remains the best final confidence check

## Active Session Notes (2026-03-27, Core Reliability 05)

- Read `C:\f1t\MEMORY.md` and `docs/core_reliability_sessions/05_backend_contracts_and_regression_tests.md` before starting implementation for this session.
- Current focus for this session: backend contracts, regression tests, a reproducible smoke harness, and an explicit covered/uncovered risk map for the core agent/backend/launcher flow.
- New critical backend contract risks confirmed during initial inspection:
  - `backend/routers/telemetry.py` currently declared `GET /api/telemetry/{race_id}/{vehicle_index}/{lap_number}` before `GET /api/telemetry/{race_id}/{vehicle_index}/best`, so a real request to `/best` was being matched as `lap_number="best"` and returned `422` instead of the best-lap payload.
  - `backend/routers/telemetry.py` still used a Pydantic v1-style `fields = {"steer": {"alias": "str"}}` config that is ignored under the installed Pydantic v2 stack, so agent telemetry samples submitted with the `str` key were silently normalized to `steer=0.0` and lost steering data.
- Test strategy for this session:
  - add a backend contract smoke harness that exercises real FastAPI routes with deterministic fake dependencies instead of relying only on direct router-function unit tests
  - add regression coverage for agent upload contract shape, telemetry POST/GET contract shape, and launcher-critical lobby host-season response shape
  - keep the harness runnable without Postgres or a live race so it remains useful as a repeatable pre-release/core-regression check
- Implemented backend contract hardening for Session 05:
  - fixed `backend/routers/telemetry.py` best-lap route matching by constraining the lap route to `/{lap_number:int}`, which restores `GET /api/telemetry/{race_id}/{vehicle_index}/best`
  - updated `TelemetrySample` onto a Pydantic v2-safe alias definition so agent samples posted with `str` now preserve steering data as `steer`
  - added `tests/backend_contract_harness.py`, a reproducible FastAPI/TestClient smoke harness that can be run directly with `python C:\f1t\tests\backend_contract_harness.py --json`
  - added `tests/test_backend_contract_smoke.py`, which makes the new harness part of the automated regression suite
  - cleaned `backend/routers/races.py` to use a version-safe model dump helper for tyre stint payloads instead of deprecated direct `.dict()` calls
- Covered risk map after Session 05:
  - covered: `POST /api/race/submit` response shape used by the agent uploader (`status`, `race_id`, `round`, `track`, `unresolved_players`)
  - covered: `POST /api/telemetry/submit` contract for agent telemetry samples, including preservation of the agent-side `str` steering key
  - covered: `GET /api/telemetry/{race_id}/{vehicle_index}/best` response availability and lap-time backfill behavior
  - covered: `GET /api/telemetry/{race_id}/session-history` response shape used by telemetry analysis surfaces
  - covered: `GET /api/lobby/host-seasons` response shape and ordering relied on by launcher host mode
- Validation completed for Session 05:
  - `python -m py_compile backend/routers/races.py backend/routers/telemetry.py tests/backend_contract_harness.py tests/test_backend_contract_smoke.py` passed
  - `python C:\f1t\tests\backend_contract_harness.py --json` passed with 5/5 contract checks green
  - `python -m unittest tests.test_backend_contract_smoke tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency tests.test_telemetry_pipeline_integrity` passed
- Remaining uncovered or partially covered risks after Session 05:
  - the new smoke harness validates HTTP contract shape with deterministic fake sessions, but it still does not exercise real Postgres migrations, real database uniqueness/index behavior, or FastAPI lifespan startup
  - launcher-related lobby coverage is still focused on `host-seasons`; `list_lobbies`, `get_lobby`, invite reset, and join flows still rely mainly on manual/runtime confidence
  - telemetry smoke coverage still does not hit `compare`, `race-analysis`, braking/throttle analysis, or AI debrief endpoints
  - bot/background-task delivery after race upload is still not asserted end-to-end; the harness only checks the synchronous upload response contract
  - one live backend chaos pass with real HTTP failures, auth, and Postgres remains the highest-value final confidence check before calling backend contracts fully hardened
- Added follow-up task file `C:\f1t\docs\core_reliability_sessions\05_1_backend_integration_coverage.md` and a matching `Session 05.1` prompt entry in `C:\f1t\docs\core_reliability_sessions\PROMPTS.md`.
- This `05.1` follow-up is intentionally separate from the already existing `06_live_validation_and_postmortem_tooling.md`; session numbering now preserves Session 06 for the live-validation/postmortem track.

## Active Session Notes (2026-03-27, Core Reliability 05.1)

- Read `C:\f1t\MEMORY.md` and `docs/core_reliability_sessions/05_1_backend_integration_coverage.md` before starting implementation for this session.
- Current focus for this session: add a real backend integration layer around Postgres, FastAPI lifespan, JWT/agent auth, telemetry analysis endpoints, broader lobby flows, and race-submit background-task resilience.
- New critical backend risks confirmed during initial inspection:
  - backend database wiring was frozen at import time: `backend/db/base.py` created the engine/sessionmaker once from the initial environment, and background services (`standings_service`, `glicko2`, `achievement_engine`, `fun_stats`, `ai_engineer`, `contract_generator`) cached `DATABASE_URL` on import, which prevented isolated real-Postgres integration tests from exercising the same DB across request and background-task paths.
  - `backend/main.py` exposed only a singleton app with inline startup logic, so there was no reusable app factory for test clients, no clean way to target a temporary Postgres database, and Alembic startup behavior was hard to verify under lifespan-driven integration tests.
  - `/api/race/submit` queued raw background tasks directly; if any background coroutine raised, it could break the request/test flow and hide whether the race commit itself was durable under partial failure.
- Integration strategy for Session 05.1:
  - introduce a runtime-configurable backend app factory and DB layer so each integration run can bind the full FastAPI app plus background services to a temporary real Postgres database;
  - run Alembic + achievement seeding through real lifespan startup against that temporary database;
  - add a Postgres-backed integration harness and separate integration suite for auth, telemetry analysis, lobby flow, and race-submit side effects instead of extending the fake smoke harness.
- Implementation already landed in this session:
  - replaced `backend/main.py` with `backend/app_factory.py` + `create_app(...)`, so backend startup can now be reused by integration tests with explicit database and lifespan configuration;
  - rewrote `backend/db/base.py` around `configure_database(...)`, `get_database_url()`, and disposable engines, which allows the app/request path and background-service path to target the same temporary Postgres DB at runtime;
  - switched the background DB-using services from import-time `DATABASE_URL` constants onto `get_database_url()`, which removes the old cross-database test contamination risk;
  - hardened `backend/routers/races.py` background-task dispatch with a safe wrapper that logs task failures instead of letting one failing background job break the whole submit path.
- Additional critical backend risks found and closed during implementation:
  - fresh real-Postgres lifespan startup exposed a real migration defect: `backend/migrations/versions/0012_add_indexes.py` recreated indexes already introduced by earlier migrations, so brand-new integration databases failed during Alembic startup until the migration was made idempotent;
  - early-return background services (`glicko2`, `fun_stats`, and the Groq debrief path) could dispose async engines before their sessions had exited, which leaked asyncpg connections under `unittest` warnings mode; those services now dispose engines via `try/finally` after session shutdown;
  - app shutdown initially relied on a sync engine-dispose helper that triggered `MissingGreenlet` during asyncpg teardown; engine cleanup now runs inside FastAPI lifespan shutdown on the async path;
  - ORM timestamp defaults still used `datetime.utcnow`, which produced SQLAlchemy deprecation noise during regression runs; runtime defaults now use a timezone-aware UTC helper.
- Integration layer delivered in Session 05.1:
  - added `tests/backend_integration_support.py`, which can bring up Docker/Postgres if needed, create a temporary real Postgres database, bind the full FastAPI app to it, run Alembic + achievement seeding through lifespan, and tear the database down afterwards;
  - added `tests/backend_integration_harness.py`, a dedicated runner for the real integration suite separate from the fake contract smoke harness;
  - added `tests/test_backend_auth_integration.py` for website JWT / launcher login token flows plus agent-token enforcement on race and telemetry ingest;
  - added `tests/test_backend_lobby_integration.py` for lobby create/list/get, join/join-by-code, leave, invite reset, settings, role changes, kick, and host-season permission boundaries;
  - added `tests/test_backend_telemetry_integration.py` for `compare`, `race-analysis`, `braking-analysis`, `throttle-analysis`, `weather-correlation`, and `debrief` on real seeded rows;
  - added `tests/test_backend_race_submit_integration.py` for end-to-end `POST /api/race/submit` commit durability plus post-commit background-task delivery under controlled failures.
- Validation completed for Session 05.1:
  - `python -m py_compile backend/db/base.py backend/app_factory.py backend/models/models.py backend/services/glicko2.py backend/services/fun_stats.py backend/services/ai_engineer.py tests/backend_integration_support.py` passed;
  - `python C:\f1t\tests\backend_integration_harness.py --json` passed with `all_passed: true` and `tests_run: 8`;
  - `python -m unittest tests.test_backend_contract_smoke tests.test_backend_auth_integration tests.test_backend_lobby_integration tests.test_backend_telemetry_integration tests.test_backend_race_submit_integration` passed after the teardown and timestamp-default cleanup.
- Remaining uncovered or only partially covered risks after Session 05.1:
  - bot/background-task delivery is now covered only up to local notifier/debrief invocation; there is still no integration coverage against a live bot service or real external delivery channel;
  - telemetry `debrief` is covered against the real app and DB path, but the outbound Groq/LLM HTTP call remains mocked rather than exercised against the real external API;
  - backend integration coverage is now strong for request/lifespan/background ordering, but websocket/live frontend coupling and multi-process concurrency races still rely on later live-validation work rather than this suite;
  - `backend/services/contract_generator.py` still follows the older manual async-engine lifecycle pattern and is not yet part of this integration layer's exercised surface.
- Completed session closure tasks:
  - updated `docs/core_reliability_sessions/05_1_backend_integration_coverage.md`, set its status to `Completed`, and appended a detailed `Session Log`;
  - Session 05.1 now closes the main gap between the fake contract smoke harness from Session 05 and the later live-validation work reserved for Session 06.
- Session 05.1 coverage was then extended in a follow-up implementation pass to close the remaining backend-owned gaps without waiting for Session 06:
  - added `LocalHTTPCaptureServer` to `tests/backend_integration_support.py`, giving the suite a reusable way to exercise real outbound `httpx` calls against a local capture endpoint instead of mocking the transport layer;
  - rewrote `backend/services/ai_engineer.py` and `backend/services/contract_generator.py` so Groq URL/model/key and stagger timing are read at call time, and both services now dispose async engines safely via `try/finally`;
  - updated `backend/app_factory.py` so `/api/engineer/ask` also honors runtime `GROQ_URL` / `GROQ_MODEL`, which makes the launcher-facing proxy route testable against the same local outbound harness;
  - added `tests/test_backend_external_delivery_integration.py` for end-to-end `race/submit -> /internal/race_uploaded -> Groq debrief -> /internal/debrief` delivery plus real outbound coverage for `/api/engineer/ask`;
  - added `tests/test_backend_contracts_integration.py` for `POST /api/contracts/generate/{season_id}`, `GET /api/contracts/{season_id}`, `POST /api/contracts/accept`, Groq-backed offer narratives, and `/internal/contracts_ready` bot delivery;
  - added `tests/test_backend_ws_and_concurrency_integration.py` for backend websocket agent/client relay with snapshot replay and high-concurrency duplicate `session_uid` submits against real Postgres.
- Validation after this follow-up extension:
  - `python -m py_compile backend/services/ai_engineer.py backend/services/contract_generator.py backend/app_factory.py tests/backend_integration_support.py tests/backend_integration_harness.py tests/test_backend_external_delivery_integration.py tests/test_backend_contracts_integration.py tests/test_backend_ws_and_concurrency_integration.py` passed;
  - `python -m unittest tests.test_backend_external_delivery_integration tests.test_backend_contracts_integration tests.test_backend_ws_and_concurrency_integration` passed with `Ran 6 tests ... OK`;
  - `python C:\f1t\tests\backend_integration_harness.py --json` passed with `all_passed: true` and `tests_run: 14`;
  - `python -m unittest tests.test_backend_contract_smoke tests.test_backend_auth_integration tests.test_backend_lobby_integration tests.test_backend_telemetry_integration tests.test_backend_race_submit_integration tests.test_backend_external_delivery_integration tests.test_backend_contracts_integration tests.test_backend_ws_and_concurrency_integration` passed with `Ran 15 tests ... OK`.
- Updated residual-risk map after the extended Session 05.1 suite:
  - covered now: backend outbound bot delivery HTTP paths (`/internal/race_uploaded`, `/internal/debrief`, `/internal/contracts_ready`) via real local HTTP capture, outbound Groq/LLM HTTP paths for race debrief, contract narratives, and `/api/engineer/ask`, backend websocket relay/snapshot behavior, high-concurrency duplicate race-submit protection on real Postgres, and the `contract_generator` generate/get/accept surface;
  - still only partially covered: real Telegram/live bot process behavior, real Groq/vendor network behavior, browser/frontend rendering on top of websocket data, and true multi-worker/process deployment races beyond the threaded high-concurrency request layer used in this suite.

## Active Session Notes (2026-03-27, Core Reliability 06)

- Read `C:\f1t\MEMORY.md` and `docs/core_reliability_sessions/06_live_validation_and_postmortem_tooling.md` before starting implementation for this session.
- Current focus for this session: a live validation pass that exercises the real agent upload/telemetry path against the real backend app/runtime stack available in this environment, plus postmortem tooling and a release-grade race-day checklist.
- Validation strategy for this session:
  - reuse the existing real-Postgres backend integration harness from Session 05.1 instead of inventing a second backend test layer;
  - drive the agent through a synthetic-but-runtime-real packet flow so upload, telemetry flush, cache handling, and backend persistence are validated together rather than only through isolated unit/router tests;
  - add an operator-facing postmortem entrypoint that can inspect local caches/raw logs, explain where data is stuck, and point to the next replay/retry action quickly.
- New race-day risk confirmed during initial inspection:
  - the real local data directory `C:\Users\Administrator\f1league_agent` currently contains `telemetry_flush_cache.json` with a pending snapshot for `session_uid=987654321` and `race_id=null`, while there is no matching race upload cache entry or raw log; this means operators can detect that telemetry is stranded, but today there is still no single postmortem command that immediately explains whether the block is "missing race upload", "backend flush failure", or "raw log missing for replay".
- Additional critical reliability gaps found during Session 06 implementation:
  - the backend now enforces `verify_agent_token` on both `POST /api/race/submit` and telemetry ingest routes, but `agent/uploader.py` and `agent/telemetry_delivery.py` were still sending unauthenticated HTTP requests with no `X-Agent-Token` header; protected environments would therefore fail upload and telemetry flush regardless of the earlier parser/cache/integration hardening.
  - launcher manual recovery was still keyed only to the race upload cache count: `retry_pending_uploads_now()` returned a no-op when `pending_uploads == 0`, even if `telemetry_flush_cache.json` still contained ready-to-flush telemetry snapshots, and launcher diagnostics/recovery UI did not surface telemetry-only backlog as a first-class issue.
- Session 06 implementation landed:
  - added `agent/postmortem.py`, a reusable CLI/report layer that inspects race upload cache, telemetry flush cache, and raw logs; classifies `race_upload_pending`, `telemetry_flush_pending`, `telemetry_waiting_for_race_id`, `orphaned_telemetry`, and `raw_log_available`; and emits concrete replay/recovery guidance by `session_uid`.
  - updated `agent/uploader.py` and `agent/telemetry_delivery.py` so both now send `X-Agent-Token` when `AGENT_SECRET_TOKEN` is configured, which closes the protected-backend ingest failure that earlier suites had missed.
  - extended `agent/launcher.py` and `agent/launcher_ui/dashboard.js` so launcher diagnostics/recovery now surface telemetry backlog separately from race uploads (`pending_telemetry`, `telemetry_ready_to_flush`, `telemetry_waiting_for_race_id`) and manual retry now covers telemetry-only backlog instead of returning a false clean state.
  - added `tests/test_postmortem_tooling.py` and `tests/test_launcher_delivery_recovery.py` to lock the new postmortem classification and telemetry-only manual retry behavior into regression coverage.
  - added `tests/live_validation_harness.py`, which runs an end-to-end live validation pass against a real temporary backend process + Postgres DB + agent runtime path and then verifies DB rows, HTTP read paths, raw-log capture, and postmortem output.
- Live validation / tooling verification completed for Session 06:
  - `python -m py_compile agent/postmortem.py agent/config.py agent/uploader.py agent/telemetry_delivery.py agent/launcher.py tests/test_postmortem_tooling.py tests/test_upload_cache.py tests/test_telemetry_pipeline_integrity.py tests/test_launcher_delivery_recovery.py tests/live_validation_harness.py` passed.
  - `node --check C:\f1t\agent\launcher_ui\dashboard.js` passed after the telemetry backlog surfacing changes.
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_telemetry_pipeline_integrity tests.test_postmortem_tooling tests.test_launcher_delivery_recovery` passed.
  - `python -m agent.postmortem --json` passed on the real local data dir and correctly classified the existing `session_uid=987654321` artifact as `orphaned_telemetry`.
  - `python C:\f1t\tests\live_validation_harness.py --json` passed after switching the harness from an in-process ASGI thread to a real `uvicorn` subprocess, and confirmed:
    - protected race upload succeeds with `race_id=1`;
    - protected telemetry flush succeeds and persists `lap_rows=2` / `session_history_rows=1`;
    - the captured raw log is replayable through `agent.replay_harness`;
    - postmortem summary on the successful run reports zero pending caches and one replayable raw log.
- Session 06 documentation/handoff was completed:
  - rewrote `docs/core_reliability_sessions/06_live_validation_and_postmortem_tooling.md` with the final live-validation report, postmortem workflow, race-day checklist, residual risks, and a detailed Session Log;
  - updated `QUICKSTART.md` with a short race-day postmortem quick path covering `agent.postmortem`, `agent.replay_harness`, and the new live validation harness command.
- Additional note from live validation:
  - the first version of Session 06 live harness failed with a real `asyncpg` "Future attached to a different loop" error when a second backend app instance was served from another event loop inside the same Python process; this was treated as a harness topology issue rather than a release blocker for the product runtime, and the harness was rebuilt around a separate backend subprocess to match real deployment topology.
- Session 06 follow-up closed the remaining race-day recovery gaps:
  - added backend `GET /api/race/session/{session_uid}` so telemetry recovery can resolve `race_id` from `session_uid` instead of staying blocked on local cache state alone;
  - updated `agent/telemetry_delivery.py` so retry/flush now attempts backend `session_uid -> race_id` lookup before emitting `blocked_no_race_id`, and added a safe `quarantine(...)` path for irrecoverable orphan telemetry entries;
  - updated `agent/postmortem.py` with `--quarantine-orphaned-telemetry`, which archives stranded entries into `telemetry_orphan_archive.json` while removing them from the active retry queue.
- Live runtime coverage was deepened beyond the earlier direct packet injection pass:
  - `tests/live_validation_harness.py` now runs the real `F1Agent.start_runtime()` path with an actual UDP socket, the real websocket client, and a `/ws/client` probe against the live backend process;
  - this live pass exposed and closed a real production auth bug: `agent/ws_client.py` had been authenticating `/ws/agent` with `F1_INVITE_TOKEN`, while the backend websocket route validated `AGENT_SECRET_TOKEN`; the client now prefers `AGENT_SECRET_TOKEN`, and `agent/config.py` no longer emits a false "auth disabled" warning when only the agent secret is configured.
- Validation completed for the Session 06 follow-up:
  - `python C:\f1t\tests\live_validation_harness.py --json` passed on the upgraded runtime path and confirmed real UDP ingest, websocket relay, race upload, telemetry flush, raw-log capture, and backend persistence together;
  - `python -m unittest tests.test_backend_external_delivery_integration` passed, reconfirming real outbound Telegram/Groq-style HTTP delivery against the local capture server;
  - `python -m unittest tests.test_backend_race_submit_integration tests.test_backend_ws_and_concurrency_integration` passed after adding coverage for the new race lookup route and concurrent duplicate telemetry submit protection;
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_telemetry_pipeline_integrity tests.test_postmortem_tooling tests.test_launcher_delivery_recovery tests.test_backend_race_submit_integration tests.test_backend_ws_and_concurrency_integration tests.test_backend_external_delivery_integration` passed with 32 tests green.
- Real local-operator cleanup completed:
  - `python -m agent.postmortem --json` on `C:\Users\Administrator\f1league_agent` initially still showed `session_uid=987654321` as `orphaned_telemetry`;
  - `http://localhost:8000/health` was healthy, but both `GET /api/race/session/987654321` on the running backend and a direct Postgres query against the real `f1league` database confirmed there is no matching race row;
  - `python -m agent.postmortem --quarantine-orphaned-telemetry --json` then removed the artifact from the active telemetry cache and preserved it in `C:\Users\Administrator\f1league_agent\telemetry_orphan_archive.json`, leaving `pending_race_uploads=0` and `pending_telemetry=0` in the real local data dir.
- Updated residual-risk map after the Session 06 follow-up:
  - no active local race upload or telemetry backlog remains in `C:\Users\Administrator\f1league_agent`;
  - still desirable for final confidence: one pass against a true live F1 25 feed, one true multi-worker backend deployment pass, and one pass against real external vendor/bot networks instead of the local capture harness;
  - non-blocking test noise remains: the combined reliability suite still emits a `ResourceWarning` about one unclosed event loop, even though all assertions now pass.
- Session 06 local-only hardening continued after that follow-up:
  - added persisted backend live snapshot endpoints in `backend/routers/ws.py`: `GET /api/live/snapshot`, `GET /api/live/status`, and `GET /api/live/data`, backed by `live_snapshot.json` on disk so browser/live consumers can recover after in-memory websocket state is lost;
  - fixed the real browser/live page bug in `frontend/app/season/[id]/live/page.tsx`: the page had been reading `message.data` even though backend websocket payloads are flat (`type`, `state`, `entries`); it now parses the real payload shape and hydrates/polls the new HTTP snapshot fallback path;
  - extended `tests/test_backend_ws_and_concurrency_integration.py` so snapshot HTTP endpoints are verified directly and their data survives `reset_ws_state(clear_persisted=False)`, which simulates loss of in-memory websocket state without losing the persisted operator view;
  - fixed `agent/ws_client.py` to close its private asyncio event loop during shutdown; the combined reliability suite now runs cleanly without the earlier unclosed-loop `ResourceWarning`;
  - extended `tests/live_validation_harness.py` so the live pass now also asserts that `/api/live/snapshot`, `/api/live/status`, and `/api/live/data` agree with each other on the real backend process after the runtime pass.
- Validation completed for this additional Session 06 hardening pass:
  - `python -m py_compile agent/ws_client.py backend/routers/ws.py tests/test_backend_ws_and_concurrency_integration.py tests/test_launcher_delivery_recovery.py tests/live_validation_harness.py` passed;
  - `python -m unittest tests.test_backend_ws_and_concurrency_integration tests.test_launcher_delivery_recovery` passed;
  - `npx tsc --noEmit` and `npm run build` passed in `C:\f1t\frontend`;
  - `python C:\f1t\tests\live_validation_harness.py --json` passed again and now confirms the new `/api/live/*` snapshot endpoints on the real backend process;
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_telemetry_pipeline_integrity tests.test_postmortem_tooling tests.test_launcher_delivery_recovery tests.test_backend_race_submit_integration tests.test_backend_ws_and_concurrency_integration tests.test_backend_external_delivery_integration` passed with `Ran 33 tests ... OK` and no `ResourceWarning`.
- Updated residual-risk map after this final local-only pass:
  - browser/live websocket handling is no longer relying solely on in-memory websocket replay; the operator view now has an HTTP snapshot fallback and persisted backend state;
  - the highest-value remaining confidence gaps are now a true live F1 25 feed, a true multi-worker backend deployment pass, and real external vendor/bot networks rather than the local HTTP capture harness;
  - no known local cache/retry backlog or unclosed-loop warning remains from the earlier Session 06 follow-up.

## Launcher Release Addendum (2026-03-27)

- Completed an autonomous live `pywebview` runtime QA pass against the real launcher window, not just HTML/mock probes.
- Runtime polish landed in `C:\f1t\agent\launcher_ui\index.html`, `C:\f1t\agent\launcher_ui\dashboard.js`, `C:\f1t\agent\launcher_ui\shell.js`, and `C:\f1t\agent\launcher.py`.
- Real runtime fixes from this pass:
  - source/dev launcher no longer opens Chromium DevTools by default; debug is now opt-in via `F1_LAUNCHER_DEBUG=1`
  - login was rebuilt into a calmer operator entry screen with live stack snapshot instead of the older hero-style first screen
  - sidebar shell copy was cleaned and the user box now truncates long identity values predictably instead of breaking layout
  - the top-right dashboard operations card was simplified so headline issue + next action stay readable in the real `pywebview` window
- Validation completed for this runtime/release pass:
  - `python -m py_compile C:\f1t\agent\launcher.py` passed
  - `node --check C:\f1t\agent\launcher_ui\dashboard.js` passed
  - `node --check C:\f1t\agent\launcher_ui\shell.js` passed
  - extracted inline JS from `C:\f1t\agent\launcher_ui\index.html`; `node --check` passed
  - live source launcher start confirmed one launcher window and zero DevTools windows by default
  - live packaged launcher smoke start from `C:\f1t\agent\dist\F1LeagueAgent.exe` stayed alive past boot and also opened zero DevTools windows
- Fresh release build completed with `cmd /c agent\build_launcher.bat`.
- Fresh launcher artifacts now verified on disk:
  - `C:\f1t\agent\dist\F1LeagueAgent.exe` (`31084530` bytes, SHA256 `78D48E9A69E09FAF55BF85BA6C1D38CD1CE07DB77D7DBC93FEC406A4E3885810`)
  - `C:\f1t\agent\installer_output\Setup_F1LeagueAgent.exe` (`32750073` bytes, SHA256 `23BF0E6E8CE70CDAA1C126A859AF6F1ACBE1148BA70AD029EF11536B9F54FE1F`)
  - `C:\f1t\backend\static\F1LeagueAgent.exe` matches the built EXE hash
  - `C:\f1t\backend\static\Setup_F1LeagueAgent.exe` matches the built installer hash
- Verified backend download endpoints serve the fresh files successfully:
  - `GET http://localhost:8000/agent/download` -> `200`, `Content-Length: 31084530`
  - `GET http://localhost:8000/agent/installer` -> `200`, `Content-Length: 32750073`
- Added release handoff doc `C:\f1t\docs\launcher_release_handoff_2026-03-27.md` with the final launcher status, release artifacts, release URLs, and remaining manual QA.
- Remaining launcher-specific work is now narrow and explicitly manual:
  - one live F1 25 telemetry pass in the real desktop environment
  - one live overlay placement/readability pass on the real monitor/DPI setup
  - one real host-flow pass (`Lobby Host`, season binding, session start, telemetry arrival)

## Website Product Shell & Localization Addendum (2026-03-27)

- Rebuilt the Next.js website around a season-first hybrid shell instead of the earlier lobby-first / disconnected-screen model.
- The primary website navigation is now `Home`, `Seasons`, `Races`, `Players`, `Records`, `Launcher`, and `Workspace`.
- The canonical browsing path is now `Home -> Seasons -> Season -> Race`, with real archive/index pages for seasons, races, players, and records instead of relying on direct links.
- Public/product, competition, deep-analysis, member/workspace, and operator surfaces are now structurally separated:
  - public/product: home, launcher, FAQ/setup/trust, discovery
  - competition: seasons, standings, calendar, live, races, players, records
  - deep analysis: telemetry, compare, replay, race analysis
  - member/workspace: workspace, me, join/invite, personal tools
  - operator: admin and season manage surfaces
- Added contextual navigation and breadcrumbs on deep pages:
  - season subnav: overview / standings / calendar / live / engineer / manage (role-gated)
  - race subnav: results / analysis / telemetry / compare / replay
- The homepage is now a product-aware front layer with a current-season cockpit, standings/race snapshot, telemetry proof, records/players discovery, launcher trust/conversion block, and concise footer/help layer.
- The season overview is now the main repeat-visit product page and opens with summary-before-detail instead of raw tables.
- Converted the website to Russian-first UI copy:
  - shared shell and metadata are localized
  - dates now format with `ru-RU`
  - major public, competition, member, operator, and deep-analysis routes were translated
  - secondary UI strings such as badges, modal labels, and achievement names were localized
- Replaced the website display font with a Cyrillic-safe condensed font (`Roboto Condensed`) after `Barlow Condensed` failed `next/font` validation with the `cyrillic` subset.
- Added/kept compatibility redirects so older routes still resolve into the new shell:
  - `/agent` -> `/launcher`
  - `/profile/[id]` -> `/players/[id]`
  - `/calendar`, `/standings`, `/live` -> active season routes
- Documentation was updated for the new web layer in:
  - `C:\f1t\QUICKSTART.md`
  - `C:\f1t\docs\website_shell_handoff_2026-03-27.md`
- Validation completed for the website/localization pass:
  - `npm run build` passed in `C:\f1t\frontend`
- Known follow-up:
  - English is not yet wired as a real runtime locale toggle; the current website is Russian-first.
  - A true bilingual `RU/EN` mode will require extracting inline UI copy into dictionaries and adding an explicit i18n layer.
  - Motorsport abbreviations such as `WDC`, `WCC`, `DRS`, `ERS`, `DNF`, and `FL` remain intentionally untranslated where they function as domain terms rather than prose.

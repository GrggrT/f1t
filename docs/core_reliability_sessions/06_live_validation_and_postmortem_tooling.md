# Step 06 - Live Validation And Postmortem Tooling

## Status

Completed

## Цель

Закрыть последний слой доверия по ядру: живой validation pass на реальном HTTP backend path и удобный postmortem workflow для race-day инцидентов.

## Почему это финальный шаг пакета

После parser/runtime/upload/telemetry/test hardening система уже была хорошо покрыта unit, replay, contract и integration слоями, но оставались два типа пробелов:

- реальные race-day сбои, которые проявляются только на связке `agent -> HTTP backend -> telemetry flush -> local artifacts`;
- операторский postmortem, когда после инцидента нужно быстро понять, что именно застряло: upload, telemetry flush, `race_id` binding или отсутствие raw log для replay.

## Что сделано

### 1. Live Validation Pass

- Добавлен reproducible live harness: `python C:\f1t\tests\live_validation_harness.py --json`
- Harness поднимает:
  - реальный backend app через отдельный `uvicorn` subprocess;
  - временную Postgres БД через уже существующий integration harness;
  - реальный agent upload/telemetry path поверх локального HTTP endpoint;
  - temp data dir с настоящим `raw_logs`, `final_classification_cache.json` и `telemetry_flush_cache.json`.
- Live validation confirmed:
  - агент проходит `waiting -> race -> finished -> uploaded -> idle`;
  - `POST /api/race/submit` проходит по реальному HTTP пути и создаёт race row;
  - telemetry flush проходит по реальному HTTP пути и создаёт telemetry/session-history rows;
  - raw log реально пишется на диск и сразу пригоден для replay/postmortem;
  - postmortem report на успешном прогоне показывает `pending_race_uploads=0`, `pending_telemetry=0`, `raw_logs=1`.

### 2. Postmortem Tooling

- Добавлен `agent/postmortem.py` с CLI:
  - `python -m agent.postmortem`
  - `python -m agent.postmortem --json`
- Tool читает:
  - локальный race upload cache;
  - локальный telemetry flush cache;
  - `raw_logs/session_*.bin`
- Tool связывает артефакты по `session_uid` и классифицирует ситуации:
  - `race_upload_pending`
  - `telemetry_flush_pending`
  - `telemetry_waiting_for_race_id`
  - `orphaned_telemetry`
  - `raw_log_available`
- Для каждого session tool сразу даёт `recommended_action`, а если есть raw log, то и готовую replay-команду.

### 3. Launcher Recovery Visibility

- Launcher diagnostics теперь отдельно видят telemetry backlog:
  - `pending_telemetry`
  - `telemetry_ready_to_flush`
  - `telemetry_waiting_for_race_id`
  - `telemetry_entries`
- Launcher recovery/actions теперь явно поднимают telemetry-specific risk, а не только race upload cache.
- Исправлен critical recovery bug:
  - раньше `retry_pending_uploads_now()` делал no-op, если `pending_uploads == 0`, даже когда pending telemetry уже лежала на диске;
  - теперь manual retry стартует и для telemetry-only backlog.

### 4. Agent Auth Transport Fix

- В ходе live validation найден и закрыт реальный transport gap:
  - backend ingest routes уже защищены `verify_agent_token`;
  - `agent/uploader.py` и `agent/telemetry_delivery.py` не отправляли `X-Agent-Token`.
- Исправлено:
  - race upload теперь отправляет `X-Agent-Token`;
  - telemetry submit/session-history flush теперь тоже отправляют `X-Agent-Token`.

## Живая проверка

### Подтверждено напрямую в этой среде

- `python C:\f1t\tests\live_validation_harness.py --json` passed.
- Harness подтвердил:
  - `race_id=1` persisted in DB;
  - `lap_rows=2`;
  - `session_history_rows=1`;
  - `best_lap` и `session-history` endpoints отвечают через реальный HTTP backend;
  - raw log captured at temp path and replay analysis succeeds with `parse_failures=[]`.
- `python -m agent.postmortem --json` на текущем реальном `C:\Users\Administrator\f1league_agent` нашёл residual incident artifact:
  - `session_uid=987654321`
  - status `orphaned_telemetry`
  - `race_id=null`
  - raw log отсутствует
  - upload cache entry отсутствует

## Postmortem Workflow

1. Сразу запустить:
   - `python -m agent.postmortem --json`
2. Посмотреть, что именно застряло:
   - `pending_race_uploads > 0` -> проблема в race upload path;
   - `pending_telemetry > 0` и `ready_to_flush > 0` -> race upload уже дошёл, застрял telemetry flush;
   - `pending_telemetry > 0` и `waiting_for_race_id > 0` -> telemetry есть, но `race_id` так и не привязался;
   - `orphaned_telemetry` -> telemetry snapshot есть, а race upload/raw log уже не осталось.
3. Если есть raw log:
   - `python -m agent.replay_harness --log "<RAW_LOG_PATH>" --agent`
4. Если backlog уже имеет `race_id`:
   - использовать launcher manual retry;
   - либо перезапустить агент, чтобы сработал startup retry path.
5. Если telemetry ждёт `race_id`:
   - проверить backend race-submit logs и наличие race row по `session_uid`;
   - если race row не появилась, использовать raw log/replay для восстановления цепочки.
6. Если это `orphaned_telemetry` и raw log нет:
   - локального replay path уже нет;
   - остаётся backend-side расследование по `session_uid` и улучшение operator discipline вокруг raw log retention.

## Race-Day Reliability Checklist

- [ ] Перед сессией прогнан `python C:\f1t\tests\live_validation_harness.py --json`
- [ ] Backend health отвечает по `/health`
- [ ] Launcher diagnostics не показывает `pending_uploads > 0`
- [ ] Launcher diagnostics не показывает `pending_telemetry > 0`
- [ ] Если есть buffered delivery, operator понимает, это race upload или telemetry flush
- [ ] `raw_logs` directory существует и доступен из data dir
- [ ] Agent/backend используют одинаковый `AGENT_SECRET_TOKEN`
- [ ] После тестового прогона есть replayable raw log
- [ ] Operator знает команду `python -m agent.postmortem --json`
- [ ] Operator знает команду `python -m agent.replay_harness --log "<RAW_LOG_PATH>" --agent`
- [ ] При backend outage используется launcher manual retry или restart retry path, а не ручное удаление cache файлов
- [ ] До релиза проверены реальные deployment-specific `.env` значения, а не только localhost defaults

## Остаточные риски по ядру

- В реальном локальном data dir уже лежит один unresolved artifact: `session_uid=987654321` как `orphaned_telemetry`; это не блокирует кодовые изменения этой сессии, но остаётся реальным incident tail.
- Live validation использует synthetic, но protocol-accurate UDP packet flow; полноценный прогон с настоящим F1 25 session feed всё ещё остаётся желательным финальным confidence step.
- Реальные внешние delivery surfaces за пределами ядра всё ещё не прогонялись в полном race-day контуре:
  - live Telegram/bot process;
  - real Groq/vendor network;
  - полный frontend/browser layer поверх live websocket data.
- Multi-worker/process deployment races по backend всё ещё покрыты слабее, чем single-process/runtime path этой сессии.

## Session Log

- 2026-03-27: прочитал `C:\f1t\MEMORY.md` и этот task-файл, затем подтвердил, что Session 06 должна закрыть именно live validation + postmortem gap, а не ещё один isolated test layer.
- 2026-03-27: в реальном `C:\Users\Administrator\f1league_agent` найден residual incident artifact: `telemetry_flush_cache.json` с `session_uid=987654321`, `race_id=null`, без соответствующего race upload cache entry и без raw log.
- 2026-03-27: добавил `agent/postmortem.py`, который читает race cache, telemetry cache и raw logs, связывает их по `session_uid`, классифицирует incident state и выдаёт next action / replay command.
- 2026-03-27: добавил `tests/test_postmortem_tooling.py`, покрывающий upload backlog, telemetry flush backlog и orphaned telemetry classification.
- 2026-03-27: в ходе live validation выявил и исправил реальный auth transport gap: `agent/uploader.py` и `agent/telemetry_delivery.py` теперь отправляют `X-Agent-Token` на backend ingest routes.
- 2026-03-27: выявил и исправил launcher-side recovery gap: telemetry-only backlog теперь виден в diagnostics/recovery, а `retry_pending_uploads_now()` больше не делает ложный no-op при `pending_uploads == 0`.
- 2026-03-27: добавил `tests/test_launcher_delivery_recovery.py`, который отдельно фиксирует manual retry path для telemetry-only backlog.
- 2026-03-27: сначала live harness упал с реальным `asyncpg` loop-sharing failure, потому что backend HTTP server был поднят в том же процессе и делил async DB objects между разными event loops; harness был перестроен на отдельный `uvicorn` subprocess с тем же temp Postgres, что ближе к реальному deployment path.
- 2026-03-27: `python C:\f1t\tests\live_validation_harness.py --json` passed и подтвердил end-to-end path `agent -> race upload -> telemetry flush -> backend persistence -> raw log replayability`.
- 2026-03-27: финальная validation wave прошла:
  - `python -m py_compile agent/postmortem.py agent/config.py agent/uploader.py agent/telemetry_delivery.py agent/launcher.py tests/test_postmortem_tooling.py tests/test_upload_cache.py tests/test_telemetry_pipeline_integrity.py tests/test_launcher_delivery_recovery.py tests/live_validation_harness.py`
  - `node --check C:\f1t\agent\launcher_ui\dashboard.js`
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_telemetry_pipeline_integrity tests.test_postmortem_tooling tests.test_launcher_delivery_recovery`
  - `python -m agent.postmortem --json`
  - `python C:\f1t\tests\live_validation_harness.py --json`
- 2026-03-27 follow-up: deepened live validation from direct packet injection to the real `F1Agent.start_runtime()` path with an actual UDP socket, the real websocket client, and a `/ws/client` probe against the live backend process. `python C:\f1t\tests\live_validation_harness.py --json` passed on this upgraded path and confirmed UDP ingest, websocket relay, race upload, telemetry flush, raw-log capture, and backend persistence together.
- 2026-03-27 follow-up: live runtime validation exposed a production websocket auth mismatch. `agent/ws_client.py` had been using `F1_INVITE_TOKEN`, while backend `/ws/agent` validates `AGENT_SECRET_TOKEN`. The client now prefers `AGENT_SECRET_TOKEN`, and `agent/config.py` no longer emits a false auth-disabled warning when only the agent secret is configured.
- 2026-03-27 follow-up: added backend `GET /api/race/session/{session_uid}` plus telemetry-side backend lookup before `blocked_no_race_id`, then locked it with `tests.test_backend_race_submit_integration` and `tests.test_telemetry_pipeline_integrity`.
- 2026-03-27 follow-up: extended concurrency coverage so `tests.test_backend_ws_and_concurrency_integration` now also proves concurrent duplicate telemetry submit still leaves exactly one lap row in Postgres.
- 2026-03-27 follow-up: reran `python -m unittest tests.test_backend_external_delivery_integration` to re-confirm the Telegram/Groq-style outbound delivery path through the local real HTTP capture server after the Session 06 changes.
- 2026-03-27 follow-up: investigated the real local orphan `session_uid=987654321` against both the running backend (`http://localhost:8000/health` was up; `GET /api/race/session/987654321` returned no race row) and the real `f1league` Postgres database (direct query returned no matching race). The artifact was therefore confirmed irrecoverable rather than merely delayed.
- 2026-03-27 follow-up: `python -m agent.postmortem --quarantine-orphaned-telemetry --json` moved `session_uid=987654321` out of the active telemetry retry queue and preserved the forensic snapshot in `C:\Users\Administrator\f1league_agent\telemetry_orphan_archive.json`. After that remediation, `python -m agent.postmortem --json` on the real local data dir reported `pending_race_uploads=0`, `pending_telemetry=0`, and `issue_count=0`.
- 2026-03-27 follow-up: final regression sweep passed:
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_telemetry_pipeline_integrity tests.test_postmortem_tooling tests.test_launcher_delivery_recovery tests.test_backend_race_submit_integration tests.test_backend_ws_and_concurrency_integration tests.test_backend_external_delivery_integration`
  - result: `Ran 32 tests ... OK`
  - note: one non-blocking `ResourceWarning` for an unclosed event loop still appears in the combined sweep and remains the only known test-noise tail from this follow-up.
- 2026-03-27 second follow-up: added persisted live snapshot support in `backend/routers/ws.py` via `GET /api/live/snapshot`, `GET /api/live/status`, and `GET /api/live/data`, backed by an on-disk snapshot file so operator/live views can recover after in-memory websocket state is lost.
- 2026-03-27 second follow-up: fixed the real browser/live page bug in `frontend/app/season/[id]/live/page.tsx`. The page had been reading `message.data`, but backend websocket payloads are flat; it now parses the real payload shape and hydrates/polls the new HTTP snapshot fallback path.
- 2026-03-27 second follow-up: extended `tests.test_backend_ws_and_concurrency_integration` so persisted live snapshot state is verified across `reset_ws_state(clear_persisted=False)`, which simulates a lost in-memory websocket hub without losing the operator snapshot.
- 2026-03-27 second follow-up: fixed `agent/ws_client.py` to close its private asyncio loop on shutdown. After that change, the combined reliability sweep passed with `Ran 33 tests ... OK` and the earlier unclosed-loop `ResourceWarning` no longer appeared.
- 2026-03-27 second follow-up: frontend/live validation completed:
  - `npx tsc --noEmit` passed in `C:\f1t\frontend`
  - `npm run build` passed in `C:\f1t\frontend`
  - `python C:\f1t\tests\live_validation_harness.py --json` passed again and now also confirms `/api/live/snapshot`, `/api/live/status`, and `/api/live/data` on the real backend process.

## Follow-up Update (2026-03-27)

- Confirmed by live validation:
  - runtime path is now real `start_runtime()` plus actual UDP listener and websocket relay
  - protected race upload and telemetry flush still persist `race_id=1`, `lap_rows=2`, `session_history_rows=1`
  - raw log capture and replay analysis remain green on the upgraded live path
- Added for postmortem / recovery:
  - backend `session_uid -> race_id` lookup route
  - telemetry retry auto-heal via backend race lookup
  - orphan telemetry quarantine command with preserved forensic archive
- Remaining risks after the follow-up:
  - still desirable: one pass against a true live F1 25 feed instead of the synthetic protocol-accurate packet stream
  - still partial: true multi-worker backend deployment races beyond the threaded concurrency coverage in this repo
  - still external: real vendor/bot network behavior rather than the local HTTP capture harness
  - non-blocking: combined reliability tests still emit one `ResourceWarning` about an unclosed event loop

## Second Follow-up Update (2026-03-27)

- Confirmed by live validation:
  - the real backend process now serves consistent `/api/live/snapshot`, `/api/live/status`, and `/api/live/data` responses after the runtime pass
  - the browser/live page fix compiles in production (`npx tsc --noEmit`, `npm run build`)
  - the combined reliability sweep now passes with `Ran 33 tests ... OK` and no remaining unclosed-loop `ResourceWarning`
- Added for operator/browser resilience:
  - persisted live snapshot storage in `backend/routers/ws.py`
  - HTTP snapshot endpoints for clients that miss websocket replay or reconnect after worker-local state loss
  - frontend fallback hydration/polling for the season live page, using the real backend payload shape instead of the broken `message.data` assumption
- Remaining risks after the second local-only pass:
  - still desirable: one pass against a true live F1 25 feed instead of the synthetic protocol-accurate packet stream
  - still partial: true multi-worker backend deployment races beyond the threaded concurrency coverage and persisted-snapshot recovery added in this repo
  - still external: real vendor/bot network behavior rather than the local HTTP capture harness
  - still not fully automated end-to-end in a real browser session: browser confidence now comes from production build plus backend/live snapshot validation rather than headless browser orchestration

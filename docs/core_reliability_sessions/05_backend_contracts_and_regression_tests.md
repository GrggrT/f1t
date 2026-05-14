# Step 05 - Backend Contracts And Regression Tests

## Status

Completed

## Цель

Сделать reliability не только “по ощущениям”, но и закрепить её тестами и регрессией.

## Почему это нужно

Сейчас значительная часть доверия к системе держится на smoke-check и ручной проверке. Для ядра этого мало: нужен минимальный набор regression checks, который можно повторять после изменений.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Любое изменение test strategy фиксировать в `C:\f1t\MEMORY.md`.
3. Отчёт вести в `Session Log` этого файла.
4. Итоги сабагентов переносить сюда и в память.

## Что нужно сделать

- Определить минимально полезный набор regression checks для ядра.
- Проверить backend contracts, которые критичны для agent/frontend/bot.
- Добавить тесты или хотя бы reproducible smoke harness там, где полноценные тесты пока дороги.
- Зафиксировать, какие участки ядра всё ещё остаются без достаточного покрытия.

## Deliverables

- начальный regression слой для ядра
- карта покрытых и непокрытых рисков

## Проверка

- после изменений есть воспроизводимый способ проверить ядро без полной ручной гонки

## Session Log

- 2026-03-27: Read `C:\f1t\MEMORY.md` and this task file, then mapped the backend contracts that are critical for the core agent/backend/launcher flow.
- 2026-03-27: Fixed two real telemetry contract bugs:
  - `GET /api/telemetry/{race_id}/{vehicle_index}/best` was shadowed by the generic lap route and returned `422`; the lap route now uses `/{lap_number:int}`.
  - `POST /api/telemetry/submit` was silently dropping the agent-side `str` steering field under Pydantic v2; `TelemetrySample` now preserves it as `steer`.
- 2026-03-27: Added reproducible smoke harness `C:\f1t\tests\backend_contract_harness.py`.
  - Run command: `python C:\f1t\tests\backend_contract_harness.py --json`
  - Covered checks: race submit response contract, telemetry submit alias preservation, telemetry best-lap route, telemetry session-history overview, launcher host-seasons response shape.
- 2026-03-27: Added `C:\f1t\tests\test_backend_contract_smoke.py` so the smoke harness is also part of the automated regression suite.
- 2026-03-27: Validation completed:
  - `python -m py_compile backend/routers/races.py backend/routers/telemetry.py tests/backend_contract_harness.py tests/test_backend_contract_smoke.py`
  - `python C:\f1t\tests\backend_contract_harness.py --json`
  - `python -m unittest tests.test_backend_contract_smoke tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency tests.test_telemetry_pipeline_integrity`
- 2026-03-27: Covered now: agent upload response shape, telemetry POST/GET basics, restored `/best` route, session-history overview contract, and launcher host-season payload ordering/fields.
- 2026-03-27: Still not fully covered: real Postgres/lifespan startup, auth-backed paths, telemetry compare/analysis/debrief endpoints, broader lobby CRUD/join/invite flows, and end-to-end bot/background-task delivery under real HTTP/database failures.

- 2026-03-27: файл создан как отдельная задача для следующей сессии.

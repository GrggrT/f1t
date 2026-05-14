# Step 05.1 - Backend Integration Coverage

## Status

Completed

## Цель

Закрыть те backend reliability gaps, которые ещё не покрываются текущим regression layer: real Postgres, lifespan, auth, telemetry analysis endpoints, lobby CRUD/join/invite flows и background-task delivery под сбоями.

## Почему это нужно

Session 05 добавила полезный contract smoke harness, но он работает на deterministic fake dependencies. Этого достаточно для shape regression, но недостаточно для путей, где риски сидят в реальной БД, lifespan startup, JWT/auth, ordering side effects и поведении background tasks.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Любое изменение integration test strategy или risk map фиксировать в `C:\f1t\MEMORY.md`.
3. Отчёт вести в `Session Log` этого файла.
4. Если используются сабагенты, их вывод переносить сюда и в память.
5. Не останавливаться на плане: добавлять integration harness, app factory, test DB fixtures и реальные проверки там, где это даёт практическое покрытие.

## Что нужно сделать

- Подготовить backend integration harness с real FastAPI app, lifespan и test Postgres.
- Покрыть auth-backed paths реальными integration tests.
- Покрыть telemetry `compare`, `race-analysis`, `braking-analysis`, `throttle-analysis`, `weather-correlation`, `debrief`.
- Покрыть более широкий lobby flow:
  - create/list/get
  - join/join-by-code
  - leave
  - invite reset
  - settings
  - role change / kick
- Покрыть end-to-end `POST /api/race/submit` + background tasks под контролируемыми HTTP/DB failure scenarios.
- Зафиксировать, какие риски после этого всё ещё остаются вне покрытия.

## Required Coverage Targets

- real Postgres and Alembic-backed startup path
- FastAPI lifespan startup behavior
- JWT/auth flows for website and launcher-backed endpoints
- telemetry analysis endpoints on real seeded rows
- lobby CRUD and role/permission boundaries
- race submit side effects and notifier/background-task resilience

## Deliverables

- reproducible backend integration harness
- integration test modules для auth, telemetry analysis, lobby flows и race submit side effects
- обновлённая карта покрытых и непокрытых рисков

## Проверка

- после изменений есть воспроизводимый способ прогнать backend integration coverage без ручной гонки
- integration suite явно отделена от лёгкого smoke/unit слоя

## Session Log

- 2026-03-27: файл создан как follow-up к Session 05 для закрытия integration coverage gaps, которые не должны смешиваться с уже существующей Session 06.
- 2026-03-27: прочитал `C:\f1t\MEMORY.md` и этот task-файл, затем подтвердил, что fake contract smoke layer из Session 05 не покрывает real Postgres, lifespan startup, real auth и background-task ordering.
- 2026-03-27: выявил и зафиксировал в памяти критичные integration risks:
  - import-time DB wiring и cached `DATABASE_URL` в background services мешали реальному изолированному Postgres coverage;
  - singleton `backend/main.py` без reusable app factory не давал запускать полноценный lifespan against temp DB;
  - raw background tasks на `/api/race/submit` могли ломать request/test flow при частичных сбоях.
- 2026-03-27: добавил reusable backend integration layer:
  - `backend/app_factory.py` с `create_app(...)` и конфигурацией реального lifespan startup;
  - runtime-reconfigurable `backend/db/base.py` с `configure_database(...)`, `get_database_url()` и disposable engines;
  - новый real-Postgres harness в `tests/backend_integration_support.py` и runner `tests/backend_integration_harness.py`.
- 2026-03-27: перевёл background DB services на runtime `get_database_url()` и обернул race-submit background jobs в safe logging wrapper, чтобы commit durability можно было проверять отдельно от падений последующих side effects.
- 2026-03-27: fresh real-Postgres startup вскрыл реальный migration defect: `backend/migrations/versions/0012_add_indexes.py` дублировал индексы из более ранних миграций. Миграция сделана idempotent, после чего Alembic-backed startup на новом temp DB стал воспроизводимо проходить.
- 2026-03-27: добавил реальные integration tests:
  - `tests/test_backend_auth_integration.py` для website JWT / launcher login token / agent token paths;
  - `tests/test_backend_lobby_integration.py` для create/list/get, join/join-by-code, leave, invite reset, settings, role change, kick и host-season permissions;
  - `tests/test_backend_telemetry_integration.py` для `compare`, `race-analysis`, `braking-analysis`, `throttle-analysis`, `weather-correlation`, `debrief`;
  - `tests/test_backend_race_submit_integration.py` для end-to-end race submit + post-commit background delivery under controlled failures.
- 2026-03-27: во время финальной cleanup-валидации обнаружил async engine teardown leak в реальных background paths с ранним `return`; исправил lifecycle в `backend/app_factory.py`, `backend/services/glicko2.py`, `backend/services/fun_stats.py`, `backend/services/ai_engineer.py`, а также перевёл ORM timestamp defaults на timezone-aware UTC helper в `backend/models/models.py`, чтобы regression runs больше не шумели `MissingGreenlet` / `ResourceWarning` / `datetime.utcnow` deprecation.
- 2026-03-27: validation completed:
  - `python C:\f1t\tests\backend_integration_harness.py --json` -> `all_passed: true`, `tests_run: 8`;
  - `python -m unittest tests.test_backend_contract_smoke tests.test_backend_auth_integration tests.test_backend_lobby_integration tests.test_backend_telemetry_integration tests.test_backend_race_submit_integration` -> `Ran 9 tests ... OK`;
  - отдельный `py_compile` smoke for changed backend/test files passed.
- 2026-03-27: covered now:
  - real Postgres + Alembic-backed startup path;
  - FastAPI lifespan startup and shutdown cleanup;
  - website JWT / launcher auth / agent token enforcement;
  - telemetry compare/analysis/debrief endpoints on real seeded rows;
  - broad lobby CRUD / join / invite / permission boundaries;
  - race submit commit durability and post-commit background-task resilience.
- 2026-03-27: still not covered:
  - live external bot delivery channel;
  - real outbound Groq/LLM API calls;
  - websocket/frontend live coupling;
  - multi-process/high-concurrency DB races beyond this request-level integration layer;
  - `backend/services/contract_generator.py`, which still uses the older manual async-engine lifecycle pattern and is outside this session's exercised surface.
- 2026-03-27: follow-up extension started specifically to close the remaining backend-owned gaps from the earlier 05.1 closeout: outbound bot delivery HTTP, outbound Groq/LLM HTTP, websocket relay/snapshot behavior, high-concurrency duplicate race submits, and `contract_generator` surface coverage.
- 2026-03-27: extended the integration layer with a reusable local outbound harness:
  - added `LocalHTTPCaptureServer` in `tests/backend_integration_support.py` so backend integration tests now exercise real outbound `httpx` calls against a local capture endpoint rather than transport mocks;
  - made `backend/services/ai_engineer.py`, `backend/services/contract_generator.py`, and `/api/engineer/ask` in `backend/app_factory.py` runtime-configurable for `GROQ_URL` / `GROQ_MODEL` / `GROQ_API_KEY`;
  - kept outbound bot paths runtime-configurable through `BOT_NOTIFY_URL` / `BOT_NOTIFY_SECRET` / `BOT_NOTIFY_DELAY_SEC`.
- 2026-03-27: added new real-Postgres integration modules:
  - `tests/test_backend_external_delivery_integration.py` for `race/submit -> /internal/race_uploaded -> Groq debrief -> /internal/debrief` and `/api/engineer/ask`;
  - `tests/test_backend_contracts_integration.py` for contracts `generate/get/accept`, Groq-backed narratives, and `/internal/contracts_ready`;
  - `tests/test_backend_ws_and_concurrency_integration.py` for websocket agent/client relay, snapshot replay to reconnecting clients, and high-concurrency duplicate `session_uid` submit protection.
- 2026-03-27: validation after the extension completed:
  - `python -m py_compile backend/services/ai_engineer.py backend/services/contract_generator.py backend/app_factory.py tests/backend_integration_support.py tests/backend_integration_harness.py tests/test_backend_external_delivery_integration.py tests/test_backend_contracts_integration.py tests/test_backend_ws_and_concurrency_integration.py` -> passed;
  - `python -m unittest tests.test_backend_external_delivery_integration tests.test_backend_contracts_integration tests.test_backend_ws_and_concurrency_integration` -> `Ran 6 tests ... OK`;
  - `python C:\f1t\tests\backend_integration_harness.py --json` -> `all_passed: true`, `tests_run: 14`;
  - `python -m unittest tests.test_backend_contract_smoke tests.test_backend_auth_integration tests.test_backend_lobby_integration tests.test_backend_telemetry_integration tests.test_backend_race_submit_integration tests.test_backend_external_delivery_integration tests.test_backend_contracts_integration tests.test_backend_ws_and_concurrency_integration` -> `Ran 15 tests ... OK`.
- 2026-03-27: updated coverage map after the extension:
  - covered now: backend outbound bot delivery HTTP paths, outbound Groq/LLM HTTP paths for race debrief / contract narratives / `/api/engineer/ask`, backend websocket relay and snapshot replay, high-concurrency duplicate submit behavior on real Postgres, and the `contract_generator` generate/get/accept surface;
  - still only partially covered: real Telegram/live bot process behavior, real Groq/vendor network behavior, browser/frontend rendering over websocket data, and true multi-worker/process deployment races.

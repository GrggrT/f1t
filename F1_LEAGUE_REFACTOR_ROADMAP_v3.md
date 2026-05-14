# F1 League Refactor Roadmap — v3 (FINAL)

> **Версия:** 3.0
> **Дата:** 14 мая 2026
> **Исполнитель:** Claude Code (autonomous mode + approval gates)
> **Контекст:** small-league (<10 players, <20 races), self-hosted Windows + Docker
> **Discovery подтверждён:** см. `REFACTOR_LOG.md` от 2026-05-14

---

## Содержание

- [Контекст и допущения](#контекст-и-допущения)
- [Глобальные правила для агента](#глобальные-правила-для-агента)
- [Sprint -0.5: Testing & Staging Infrastructure](#sprint--05-testing--staging-infrastructure)
- [Sprint 0: Foundation Safety](#sprint-0-foundation-safety)
- [Sprint 0.6: Triage Existing Tests](#sprint-06-triage-existing-tests)
- [Sprint 1: Security Wins](#sprint-1-security-wins)
- [Что будет в Sprint 2+](#что-будет-в-sprint-2)

---

## Контекст и допущения

Все факты подтверждены через discovery (PR -0.5.1) и зафиксированы тут чтобы агент не угадывал:

```yaml
postgres_user: f1league          # confirmed in .env
postgres_db: f1league            # confirmed in .env
postgres_password: set           # confirmed (value not logged)
db_module: backend.db.base       # confirmed (NOT backend.services.db)
base_class: backend.db.base.Base # SQLAlchemy 2.0 DeclarativeBase
existing_tests: 16+ files in tests/
existing_pytest_config: none     # no pytest.ini, no pyproject.toml, no conftest.py
launcher_users: 1                # only the owner
launcher_token_storage: env_var_or_config_file  # NOT baked into .exe
launcher_config_path: ~/f1league_agent/launcher_config.json
launcher_401_handling: missing   # in uploader/telemetry_delivery/ws_client
groq_call_sites: 7               # (not 6 as previously assumed)
data_volume: very_small          # <10 players, <20 races
downtime_acceptable: yes         # 30+ min windows OK
staging_strategy: ephemeral_local_copy  # not permanent
autonomous_mode: full            # with mandatory approval gates
target_model: League → Season → Race  # multi-league friend groups
backend_dockerfile: python:3.11-slim
backend_dockerfile_curl: not_installed
```

Если хоть одно из этих допущений неверно — **немедленно остановиться и переуточнить**.

---

## Глобальные правила для агента

### Правило 1: Stop-the-world для всех миграций

Перед **любым** `alembic upgrade head` агент обязан:

```bash
# 1. Свежий бэкап
docker compose exec postgres pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc \
  > backups/pre-migration-$(date +%Y%m%d-%H%M%S).pgc

# 2. Остановить сервисы которые пишут в БД
docker compose stop backend bot

# 3. Запустить миграцию
docker compose run --rm backend alembic upgrade head

# 4. Запустить сервисы обратно
docker compose start backend bot

# 5. Smoke test (см. PR-specific criteria)
```

### Правило 2: Approval gate = STOP

Когда в PR помечен **Approval gate** — агент **не мерджит** до явного approve от пользователя. Если пользователь не отвечает 24 часа — агент пингует один раз и ждёт дальше. Не двигается. Не делает "временное решение".

### Правило 3: Имена БД из env

Везде где упоминается `f1league` как user/db — на самом деле читать из `$POSTGRES_USER` / `$POSTGRES_DB`. Хардкод запрещён.

### Правило 4: Pre-flight grep перед PR

Перед началом любого PR, который ссылается на конкретный код — выполнить grep для подтверждения что путь/функция/класс существуют. Если не существуют — пометить PR как BLOCKED и спросить.

### Правило 5: Одна миграция = один PR

Не объединять несколько `alembic revision` в один PR. По одной миграции на PR. Это упрощает rollback.

### Правило 6: Каждый PR имеет план отката

Если PR содержит миграцию — план отката должен быть протестирован локально через staging (`scripts/staging_up.sh`) до merge.

---

# Sprint -0.5: Testing & Staging Infrastructure

**Длительность:** 1-2 дня
**Pre-conditions:** Нет
**Цель:** Формализовать существующую тестовую инфраструктуру, поднять postgres-test, добавить ephemeral staging.

## PR -0.5.1: ✅ DONE

Discovery выполнен. Результаты в `REFACTOR_LOG.md`.

---

## PR -0.5.2: Formalize existing pytest infrastructure

**Контекст:** Из discovery — 16+ test файлов в `tests/`, но pytest не в requirements, нет конфига, нет conftest. Задача: сделать чтобы они запускались через `./scripts/run_tests.sh`.

**Файлы:**
- `backend/requirements-dev.txt` (create)
- `pyproject.toml` (create)
- `tests/conftest.py` (create)
- `docker-compose.test.yml` (create)
- `backend/Dockerfile` (modify)
- `scripts/run_tests.sh` (create)

### Имплементация

**`backend/requirements-dev.txt`:**

```
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-timeout>=2.2.0
pytest-mock>=3.12.0
```

> Note: `httpx` уже в `backend/requirements.txt` (подтверждено discovery).

**`pyproject.toml`:**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
timeout = 60
addopts = "-v --tb=short"
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

**`tests/conftest.py`:**

```python
"""Pytest fixtures for backend tests.

Uses isolated postgres-test container, not SQLite — because the schema
relies on JSONB, ARRAY, and partial unique indexes that SQLite doesn't support.
"""
import os
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

# Импорт подтверждён в discovery Task 5
from backend.db.base import Base


TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@postgres-test:5432/test",
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Per-test isolated DB session.

    Drops + creates schema each test (fast for small schema).
    For larger schema/setup, switch to transactional fixture later.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    SessionMaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionMaker() as session:
        yield session
    await engine.dispose()
```

**`docker-compose.test.yml`:**

```yaml
services:
  postgres-test:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test
    ports:
      - "127.0.0.1:5434:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 5s
      timeout: 3s
      retries: 5
    tmpfs:
      - /var/lib/postgresql/data
    logging:
      driver: json-file
      options:
        max-size: "5m"
        max-file: "2"

  backend-test:
    build:
      context: .
      dockerfile: backend/Dockerfile
      args:
        INCLUDE_DEV: "true"
    depends_on:
      postgres-test:
        condition: service_healthy
    environment:
      TEST_DATABASE_URL: postgresql+asyncpg://test:test@postgres-test:5432/test
      NEXTAUTH_SECRET: "test-secret-not-for-prod"
      AGENT_SECRET_TOKEN: "test-agent-token"
      POSTGRES_USER: test
      POSTGRES_DB: test
      POSTGRES_PASSWORD: test
    volumes:
      - ./backend:/app/backend:ro
      - ./tests:/app/tests:ro
      - ./pyproject.toml:/app/pyproject.toml:ro
    working_dir: /app
    entrypoint: ["pytest"]
```

**`backend/Dockerfile`** (добавить):

```dockerfile
ARG INCLUDE_DEV=false
COPY backend/requirements.txt /tmp/requirements.txt
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    if [ "$INCLUDE_DEV" = "true" ]; then \
        pip install --no-cache-dir -r /tmp/requirements-dev.txt; \
    fi
```

**`scripts/run_tests.sh`:**

```bash
#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.test.yml up -d postgres-test
docker compose -f docker-compose.test.yml run --rm --build backend-test "$@"

if [[ "${1:-}" == "--cleanup" ]]; then
    docker compose -f docker-compose.test.yml down -v
fi
```

### Acceptance criteria

1. `./scripts/run_tests.sh --collect-only` запускается без ошибок инфраструктуры (импорты, fixtures работают)
2. `pyproject.toml` парсится pytest'ом без warnings
3. `docker compose -f docker-compose.test.yml up postgres-test` поднимает контейнер за <10 сек
4. `from backend.db.base import Base` работает в conftest
5. Production stack не затронут

### Tests

PR сам — это инфраструктура. Verification — что 1+ existing test может быть collected.

### Rollback

Удалить файлы `requirements-dev.txt`, `pyproject.toml`, `conftest.py`, `docker-compose.test.yml`, `scripts/run_tests.sh`. Откатить Dockerfile diff.

### Approval gate

Нет (additive change).

---

## PR -0.5.3: Ephemeral staging procedure

**Контекст:** Для тестирования миграций нужна копия production БД, изолированная от main stack. Не постоянный staging — поднимается по требованию.

**Файлы:**
- `scripts/staging_up.sh` (create)
- `scripts/staging_down.sh` (create)
- `docker-compose.staging.override.yml` (create)
- `docs/STAGING.md` (create)

### Имплементация

**`docker-compose.staging.override.yml`:**

```yaml
services:
  postgres:
    ports:
      - "127.0.0.1:5433:5432"
    volumes:
      - postgres_staging_data:/var/lib/postgresql/data

  backend:
    ports:
      - "127.0.0.1:8001:8000"

volumes:
  postgres_staging_data:
```

**`scripts/staging_up.sh`:**

```bash
#!/usr/bin/env bash
set -euo pipefail
DUMP=${1:?"Usage: $0 <production-dump.pgc>"}

if [ -f .env ]; then
  set -a; source .env; set +a
fi

COMPOSE_PROJECT_NAME=f1t-staging \
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.staging.override.yml \
    up -d postgres

sleep 5
until COMPOSE_PROJECT_NAME=f1t-staging \
  docker compose exec -T postgres pg_isready -U "$POSTGRES_USER"; do
  sleep 1
done

COMPOSE_PROJECT_NAME=f1t-staging \
  docker compose exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner \
  < "$DUMP"

COMPOSE_PROJECT_NAME=f1t-staging \
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.staging.override.yml \
    up -d backend

echo "Staging up: backend=http://localhost:8001, postgres=localhost:5433"
echo "Tear down: ./scripts/staging_down.sh"
```

**`scripts/staging_down.sh`:**

```bash
#!/usr/bin/env bash
COMPOSE_PROJECT_NAME=f1t-staging \
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.staging.override.yml \
    down -v
echo "Staging torn down, volume deleted"
```

**`docs/STAGING.md`:**

```markdown
# Staging Procedure

Используется для тестирования миграций перед production.
Поднимается из production dump, после теста сносится.

## Lifecycle

1. Создать свежий dump production:
   `docker compose exec postgres pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc > /tmp/prod.pgc`
2. Поднять staging: `./scripts/staging_up.sh /tmp/prod.pgc`
3. Прогнать миграцию: `COMPOSE_PROJECT_NAME=f1t-staging docker compose exec backend alembic upgrade head`
4. Smoke test на `http://localhost:8001`
5. Если всё ОК — катить на production
6. Снести: `./scripts/staging_down.sh`

## Ограничения

- Volume staging изолированный, после `staging_down.sh` данные пропадают
- Staging **не** обновляется автоматически
- Использовать только для тестов миграций, не для разработки
```

### Acceptance criteria

1. `./scripts/staging_up.sh <dump>` поднимает изолированный stack на портах 8001/5433
2. `curl http://localhost:8001/healthz` → 200 (после Sprint 0)
3. Production stack продолжает работать на 8000/5432
4. `./scripts/staging_down.sh` полностью убирает staging

### Tests

Manual test: полный cycle up → migration → down.

### Rollback

Удалить скрипты и override-файл.

### Approval gate

Нет.

---

## Sprint -0.5 completion checklist

- [x] PR -0.5.1: discovery выполнен (`REFACTOR_LOG.md`)
- [ ] PR -0.5.2: pytest infrastructure формализована
- [ ] PR -0.5.3: staging scripts работают

---

# Sprint 0: Foundation Safety

**Длительность:** 1.5 дня
**Pre-conditions:** Sprint -0.5 завершён
**Цель:** Защитить данные через automated backup, добавить healthchecks, создать baseline.

## PR 0.1: Postgres automated backup service

**Контекст:** В `docker-compose.yml` нет сервиса бэкапа. Named volume `postgres_data` живёт только пока живёт Docker daemon.

**Файлы:**
- `docker-compose.yml` (modify): добавить сервис `backup`
- `backups/.gitkeep` (create)
- `.gitignore` (modify): `backups/*.pgc` и `backups/*.err`
- `scripts/restore_from_backup.sh` (create)

### Имплементация

**Сервис в `docker-compose.yml`:**

```yaml
backup:
  image: postgres:15-alpine
  depends_on:
    postgres:
      condition: service_healthy
  volumes:
    - ./backups:/backups
  environment:
    - PGPASSWORD=${POSTGRES_PASSWORD}
    - POSTGRES_USER=${POSTGRES_USER}
    - POSTGRES_DB=${POSTGRES_DB}
  entrypoint: |
    sh -c '
      while true; do
        TS=$$(date +%Y%m%d-%H%M%S)
        echo "[backup] starting $$TS"
        pg_dump -h postgres -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -Fc \
          > /backups/dump-$$TS.pgc 2>/backups/dump-$$TS.err
        if [ $$? -eq 0 ] && [ -s /backups/dump-$$TS.pgc ]; then
          rm /backups/dump-$$TS.err
          find /backups -name "dump-*.pgc" -mtime +14 -delete
          echo "[backup] success $$TS"
        else
          echo "[backup] FAILED $$TS, see /backups/dump-$$TS.err"
        fi
        sleep 86400
      done
    '
  restart: unless-stopped
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "3"
```

**`scripts/restore_from_backup.sh`:**

```bash
#!/usr/bin/env bash
set -euo pipefail

DUMP=${1:?"Usage: $0 <dump-file.pgc>"}

if [ ! -f "$DUMP" ]; then
  echo "ERROR: $DUMP not found"
  exit 1
fi

if [ -f .env ]; then
  set -a; source .env; set +a
fi

POSTGRES_USER=${POSTGRES_USER:-f1league}
POSTGRES_DB=${POSTGRES_DB:-f1league}

cat <<EOF
======================================================================
WARNING: Restore will OVERWRITE the current database.
   Dump: $DUMP
   DB: $POSTGRES_DB (user: $POSTGRES_USER)

Backend and bot will be stopped during restore.
======================================================================
EOF
read -p "Continue? Type 'yes' to proceed: " confirm
if [ "$confirm" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

echo "Stopping backend and bot..."
docker compose stop backend bot

echo "Restoring from $DUMP..."
docker compose exec -T postgres pg_restore \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner \
  < "$DUMP"

echo "Starting backend and bot..."
docker compose start backend bot

echo "Done. Verify the application is working."
```

### Acceptance criteria

1. После `docker compose up -d backup` — через **60 секунд** в `./backups/` появляется первый dump
2. `docker compose logs backup` показывает `[backup] success ...`
3. `./scripts/restore_from_backup.sh ./backups/dump-*.pgc` спрашивает подтверждение, останавливает backend+bot, восстанавливает
4. На staging (через PR -0.5.3) попытка restore работает
5. Cleanup: `find ./backups -name "dump-*.pgc" -mtime +14 -delete` — старые файлы удаляются

### Tests

`tests/test_backup_smoke.sh` — поднимает stack, ждёт первый dump, проверяет размер.

### Rollback

Удалить сервис из compose. Существующие dumps остаются.

### Approval gate

**ДА**. Подтвердить что:
1. Первый dump создался (путь+размер)
2. Restore protocol на staging успешен

---

## PR 0.2: Backend healthcheck + log rotation

**Контекст:** Backend без healthcheck → race condition при cold start. `python:3.11-slim` не содержит curl → healthcheck через `python -c`.

**Файлы:**
- `backend/routers/health.py` (create)
- `backend/app_factory.py` (modify): подключить health router
- `docker-compose.yml` (modify): healthcheck + logging

### Имплементация

**`backend/routers/health.py`:**

```python
"""Health and readiness endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# ✅ путь из discovery Task 3
from backend.db.base import get_db


router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness probe. No DB check."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe. Checks DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"DB not ready: {type(e).__name__}",
        )
    return {"status": "ready"}
```

**В `backend/app_factory.py`** (добавить):

```python
from backend.routers import health
# ...
app.include_router(health.router)
```

**В `docker-compose.yml`:**

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"

services:
  backend:
    # ...existing...
    healthcheck:
      # urlopen сам raise'ит на non-2xx → exception → exit 1; success → exit 0
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
    logging: *default-logging

  bot:
    # ...existing...
    depends_on:
      backend:
        condition: service_healthy
    logging: *default-logging

  frontend:
    # ...existing...
    depends_on:
      backend:
        condition: service_healthy
    logging: *default-logging

  postgres:
    # ...existing (already has healthcheck)...
    logging: *default-logging
```

### Acceptance criteria

1. `curl http://localhost:8000/healthz` → 200 `{"status":"ok"}`
2. `curl http://localhost:8000/readyz` → 200 при живой БД, 503 после `docker compose stop postgres`
3. `docker compose ps` показывает `healthy` для backend через ~30 сек
4. После `docker compose restart` frontend и bot ждут backend healthy
5. `docker inspect <backend>` показывает корректную healthcheck конфигурацию
6. Disk usage `/var/lib/docker/containers/*/` ограничен (max 30MB на сервис)

### Tests

```python
# tests/test_healthcheck.py
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_readyz_pattern(db_session):
    """Verifies the basic DB check pattern works."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
```

### Rollback

Revert файлов и compose-секций.

### Approval gate

Нет.

---

## PR 0.3: Baseline backup + git tag

**Контекст:** Перед началом изменений нужна гарантированная точка отката.

### Шаги (manual procedure)

```bash
# 1. Свежий dump
docker compose exec postgres pg_dump -U f1league -d f1league -Fc \
  > backups/pre-refactor-baseline-$(date +%Y%m%d).pgc

# 2. Скопировать на ВНЕШНИЙ носитель (OneDrive/USB)
#    Команда зависит от системы

# 3. Git tag
git tag pre-refactor-baseline
git push --tags

# 4. Обновить REFACTOR_LOG.md
echo "## $(date +%Y-%m-%d): Baseline backup created" >> REFACTOR_LOG.md
echo "- Path: backups/pre-refactor-baseline-$(date +%Y%m%d).pgc" >> REFACTOR_LOG.md
echo "- External copy: <YOUR_PATH>" >> REFACTOR_LOG.md
echo "- Git tag: pre-refactor-baseline" >> REFACTOR_LOG.md
```

### Acceptance criteria

1. Файл `backups/pre-refactor-baseline-*.pgc` существует и больше 100KB
2. Скопирован на минимум один внешний носитель
3. Git tag `pre-refactor-baseline` существует на remote
4. `REFACTOR_LOG.md` обновлён

### Tests

Не применимо (organizational PR).

### Rollback

Не применимо.

### Approval gate

**ДА**. Физическое подтверждение что бэкап на внешнем носителе.

---

## Sprint 0 completion checklist

- [ ] PR 0.1: backup сервис работает, первый dump создан
- [ ] PR 0.2: healthchecks работают, log rotation активна
- [ ] PR 0.3: baseline backup на внешнем носителе + git tag

---

# Sprint 0.6: Triage Existing Tests

**Длительность:** 1-2 дня
**Pre-conditions:** Sprint -0.5.2 завершён (pytest infrastructure работает)
**Цель:** Понять состояние существующих 16 тестов, починить или quarantine broken.

## Почему этот спринт существует

Discovery показал что есть 16+ test файлов **но** без pytest config. С большой вероятностью часть из них:

- Не collectible (broken imports)
- Падают (устарели после изменений кода)
- Skip'ятся

Без понимания этого состояния — acceptance criteria PR'ов 1.x будут декоративными.

---

## PR 0.6.1: Collection-only triage

**Контекст:** Запустить pytest в collection mode.

### Команда

```bash
./scripts/run_tests.sh --collect-only --tb=short
```

### Действие агента

1. Запустить команду
2. Записать в `REFACTOR_LOG.md` секцию `## Sprint 0.6.1: Test collection triage`:
   - Сколько тестов discovered
   - Сколько collection errors
   - Список файлов с errors + одна строка причины
3. Не пытаться исправлять — только записать факты

### Acceptance criteria

1. Команда выполнена, output полностью в `REFACTOR_LOG.md`
2. Для каждого collection error указан файл и причина
3. Никаких изменений в test файлах

### Approval gate

Нет (read-only).

---

## PR 0.6.2: Test run triage

**Контекст:** Запустить тесты которые collected, категоризировать результаты.

### Команда

```bash
./scripts/run_tests.sh --tb=line -p no:randomly
```

### Действие агента

1. Запустить команду, capture output
2. Категоризировать в `REFACTOR_LOG.md`:
   - ✅ **PASS** — список
   - ⚠️ **SKIP** — список с reason
   - 🔴 **FAIL** — список с одной строкой причины
   - 💀 **ERROR** — список с одной строкой причины
3. Для каждого FAIL/ERROR оценить:
   - **Easy fix** (несколько часов) — для починки в Sprint 0.7
   - **Hard fix** (день+) — для quarantine (`@pytest.mark.skip` с TODO)
   - **Obsolete** (тест устарел) — для удаления

### Acceptance criteria

1. Каждый из 16 тестов категоризирован
2. Создан явный план triage: fix / quarantine / delete

### Approval gate

**ДА**. Прочитать отчёт, подтвердить план до фактических правок.

---

## PR 0.6.3: Apply test triage decisions

**Контекст:** Реализовать решения из PR 0.6.2.

### Действия

- Easy fix → отдельный коммит с минимальной правкой каждого
- Quarantine → `@pytest.mark.skip(reason="...")` + TODO с issue number
- Obsolete → удалить файл, записать причину в `REFACTOR_LOG.md`

### Acceptance criteria

1. `./scripts/run_tests.sh` завершается с exit code 0
2. Skipped tests имеют clear reason
3. Удалённые тесты упомянуты в `REFACTOR_LOG.md`

### Approval gate

**ДА**. После — есть рабочая регрессионная сеть.

---

## Sprint 0.6 completion

После этого спринта:

- Известно сколько тестов реально работает (baseline)
- Какие фичи под покрытием, какие нет
- Можно писать `Tests: добавить test_X.py` в acceptance criteria уверенно

---

# Sprint 1: Security Wins

**Длительность:** 4-5 дней
**Pre-conditions:** Sprint 0.6 завершён, baseline тестов есть
**Цель:** Точечные security fix'ы с правильным порядком frontend/backend/agent изменений.

## Порядок PR'ов

```
PR 1.0   → Frontend Bearer audit (apiFetch helper)
PR 1.0.5 → Agent 401 handling (блокирует PR 1.4)
PR 1.1   → Backend require auth on open endpoints
PR 1.2   → AGENT_SECRET_TOKEN fail-closed (single-user flow)
PR 1.2.5 → /season/[id]/manage stub
PR 1.3   → Next.js bump + bot port + compare_digest
PR 1.4   → Secrets rotation (все секреты, включая NEXTAUTH_SECRET)
PR 1.5   → Google id_token verification (verify на первом sign-in only)
```

---

## PR 1.0: Frontend Bearer audit + universal apiFetch

**Контекст:** Из discovery — frontend во многих местах шлёт `web_user_id`/`requester_id` в body вместо Authorization header. PR 1.1 закроет endpoints — если до этого не переписать фронт, всё сломается.

**Файлы:**
- `frontend/lib/api-client.ts` (create)
- `frontend/app/me/page.tsx` (modify)
- `frontend/app/lobby/join/page.tsx` (modify)
- `frontend/app/lobby/[id]/page.tsx` (modify)
- `frontend/app/season/[id]/engineer/page.tsx` (modify)
- `frontend/app/practice/page.tsx` (modify)
- `frontend/components/CreateLobbyButton.tsx` (modify)

### Имплементация

**`frontend/lib/api-client.ts`:**

```typescript
import { getSession } from "next-auth/react";


const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";


export async function apiFetch(
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  const url = path.startsWith("http") ? path : `${API}${path}`;
  const session = await getSession();
  const headers = new Headers(init.headers);

  if (session?.user?.backendToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${session.user.backendToken}`);
  }

  if (init.body && !headers.has("Content-Type") && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  return fetch(url, { ...init, headers });
}


export async function apiFetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}
```

### Acceptance criteria (smoke test чек-лист)

После деплоя в DevTools Network проверить что каждый из этих запросов несёт `Authorization: Bearer ...`:

| Действие в UI | Endpoint | Где |
|---------------|----------|-----|
| Создание лобби | `POST /api/lobby` | `/me` → "Создать лобби" |
| Вступление по коду | `POST /api/lobby/join-by-code` | `/lobby/join?code=...` |
| Создание сезона | `POST /api/lobby/{id}/seasons` | `/lobby/[id]` → "Создать сезон" |
| AI ассистент | `POST /api/seasons/assistant` | `/me` → "Спросить ассистента" |
| Engineer ask | `POST /api/lobby/{id}/engineer/ask` | `/season/[id]/engineer` |
| Привязка игрока | `POST /api/web/link-player` | `/me` → "Привязать игрока" |
| Practice sessions | `GET /api/practice/sessions` | `/practice` |

Если **хоть один** не несёт Bearer — PR 1.1 НЕ мерджить.

### Tests

```typescript
// frontend/tests/api-client.test.ts
// Unit тест для apiFetch + проверка что Bearer добавляется
```

### Rollback

Revert файлов.

### Approval gate

**ДА**. Чек-лист выше — обязательное условие.

---

## PR 1.0.5: Agent 401 handling

**Контекст:** Из discovery Task 7 — `uploader.py`, `telemetry_delivery.py`, `ws_client.py` **не обрабатывают 401**. Они проверяют только `status_code != 200` / `>= 400` и retry'ят. После ротации `AGENT_SECRET_TOKEN` в PR 1.4 это приведёт к retry loop без понятной ошибки.

**Этот PR обязательно перед PR 1.4.**

**Файлы:**
- `agent/uploader.py` (modify)
- `agent/telemetry_delivery.py` (modify)
- `agent/ws_client.py` (modify)
- `agent/launcher_ui.py` (modify): новый экран reconfigure
- `agent/config.py` (modify): функция `set_agent_token`

### Имплементация (паттерн для трёх delivery модулей)

```python
# agent/uploader.py
import logging

logger = logging.getLogger(__name__)


class AuthFailureError(Exception):
    """Raised when AGENT_SECRET_TOKEN is rejected by server."""
    pass


async def _send(self, payload: dict) -> bool:
    try:
        response = await self._client.post(
            url,
            headers={"X-Agent-Token": self._token},
            json=payload,
        )
    except httpx.RequestError as e:
        logger.warning("Network error, will retry: %s", e)
        return False

    if response.status_code == 401:
        logger.error("Agent token rejected (401)")
        if self._on_auth_failure:
            await self._on_auth_failure()
        raise AuthFailureError("AGENT_SECRET_TOKEN rejected by server")

    if response.status_code >= 400:
        logger.warning("HTTP %s, will retry", response.status_code)
        return False

    return True
```

### UI экран в `launcher_ui.py`

```python
async def on_auth_failure():
    """Called when delivery modules detect 401."""
    state.auth_failed = True
    ui.show_screen("token_reconfigure")
    await uploader.pause()
    await telemetry.pause()
    await ws_client.pause()


def render_token_reconfigure_screen():
    """Shown when AGENT_SECRET_TOKEN is rejected."""
    return UI.Card(
        title="Токен агента отклонён сервером",
        body=[
            UI.Text("Сервер не принимает текущий AGENT_SECRET_TOKEN. "
                    "Возможно, он был обновлён администратором."),
            UI.Input(name="new_token", placeholder="Введите новый токен", masked=True),
            UI.Button("Сохранить и продолжить", on_click=apply_new_token),
        ],
    )


async def apply_new_token(new_token: str):
    """Save new token, restart delivery loops."""
    from agent.config import set_agent_token
    set_agent_token(new_token)
    state.auth_failed = False
    await uploader.resume()
    await telemetry.resume()
    await ws_client.resume()
    ui.show_screen("main")
```

### Функция в `config.py`

```python
import json
import os
from pathlib import Path


CONFIG_FILE = Path.home() / "f1league_agent" / "launcher_config.json"


def set_agent_token(new_token: str) -> None:
    """Update AGENT_SECRET_TOKEN in launcher_config.json and reload."""
    config = {}
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
    config["agent_token"] = new_token
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    os.environ["AGENT_SECRET_TOKEN"] = new_token
```

### Pre-flight grep

```bash
grep -n "status_code\|response\." agent/uploader.py
grep -n "status_code\|response\." agent/telemetry_delivery.py
grep -n "status_code\|response\." agent/ws_client.py
grep -n "screen\|show_screen\|render_" agent/launcher_ui.py | head -20
```

### Acceptance criteria

1. Симулировать invalid token: `AGENT_SECRET_TOKEN=garbage` → лаунчер показывает экран reconfigure, НЕ retry loop
2. Ввести правильный токен через UI → uploads/telemetry/ws_client возобновляются без перезапуска
3. `launcher_config.json` обновляется новым `agent_token`
4. Существующие agent runtime tests (`test_agent_runtime_lifecycle.py`, `test_launcher_delivery_recovery.py`) проходят
5. Логи при 401: одна строка `Agent token rejected (401)`, не спам

### Tests

```python
# Mock response status_code=401 → AuthFailureError raised
# Mock 200 → _send returns True
# Mock 5xx → _send returns False (retry)
```

### Rollback

Revert файлов agent/. Старая retry loop возвращается.

### Approval gate

**ДА**. Без этого PR — нельзя двигаться к PR 1.4.

---

## PR 1.1: Backend require auth on open endpoints

**Контекст:** Закрыть открытые endpoints через `Depends(get_current_user)` и helpers.

**Файлы:** все listed routers + новый `backend/services/auth_helpers.py`.

### Имплементация `auth_helpers.py`

```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# ✅ правильный импорт из discovery
from backend.db.base import get_db
from backend.models.models import WebUser, LobbyMember, Lobby, Season
from backend.services.auth_dependencies import get_current_user


async def require_lobby_member(
    lobby_id: int,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LobbyMember:
    member = await db.scalar(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.web_user_id == user.id,
        )
    )
    if not member:
        raise HTTPException(403, "Not a member of this lobby")
    return member


async def require_lobby_moderator(
    lobby_id: int,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LobbyMember:
    member = await require_lobby_member(lobby_id, user, db)
    if member.role not in ("admin", "moderator"):
        raise HTTPException(403, "Moderator+ role required")
    return member


async def require_season_member(
    season_id: int,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LobbyMember:
    season = await db.get(Season, season_id)
    if not season or not season.lobby_id:
        raise HTTPException(404, "Season not found")
    return await require_lobby_member(season.lobby_id, user, db)
```

### Список endpoints для закрытия

| Endpoint | File:line | Required auth |
|----------|-----------|---------------|
| `POST /api/players/register` | `players_admin.py:38` | system_admin |
| `POST /api/players/add_steam` | `players_admin.py:68` | system_admin |
| `POST /api/players/map_steam` | `players_admin.py:119` | system_admin |
| `PATCH /api/players/{id}` | `players_admin.py:160` | system_admin |
| `POST /api/contracts/generate/{season_id}` | `contracts.py:20` | lobby_moderator+ for season |
| `POST /api/contracts/accept` | `contracts.py` | authenticated, ownership check |
| `POST /api/web/link-player` | `web_auth.py:364` | authenticated, owner check |
| `POST /api/seasons/assistant` | `seasons.py:81` | authenticated |
| `POST /api/telemetry/race-analysis/{id}/debrief` | `telemetry.py:793` | authenticated |
| `GET /api/lobby/{id}/engineer` | `lobby.py:484` | require_lobby_member |
| `POST /api/lobby/{id}/engineer/ask` | `lobby.py:562` | require_lobby_member |
| `POST /api/engineer/ask` | `app_factory.py:150` | authenticated |
| `POST /api/predict/{season_id}` | `analytics.py:430` | authenticated |
| `POST /api/web/launcher/auth` | `web_auth.py:387` | authenticated |
| `GET /api/lobby/{id}/members` | `lobby.py:325` | require_lobby_member |
| `GET /api/lobby/{id}/seasons` | `lobby.py:459` | require_lobby_member |

### Pre-flight check

```bash
for path in players_admin contracts web_auth seasons telemetry lobby analytics app_factory; do
  grep -n "Depends(get_current_user)" backend/routers/${path}.py backend/${path}.py 2>/dev/null || true
done
```

### Acceptance criteria

1. Все endpoints из таблицы возвращают **401** без Bearer
2. Все возвращают **403** для авторизованного без нужной роли
3. Все возвращают **200/4xx по logic** для авторизованного с нужной ролью
4. PR 1.0 уже задеплоен → фронт шлёт Bearer → ничего не падает
5. `pytest tests/test_endpoint_authorization.py -v` все passing

### Tests

```python
# tests/test_endpoint_authorization.py
# Параметризованный тест по таблице:
# (endpoint, method, expected_anon_status, expected_no_role_status, expected_with_role_status)
```

### Rollback

Revert изменений в routers, оставить `auth_helpers.py`.

### Approval gate

**ДА**. После merge — DevTools проверка что фронт не ловит 401.

---

## PR 1.2: AGENT_SECRET_TOKEN fail-closed (single-user flow)

**Контекст:**
- Discovery: токен **не запекается в .exe**, читается из env или `~/f1league_agent/launcher_config.json`
- Только один пользователь лаунчера (ты)
- → Никакой redistribution, никакого ожидания

**Файлы:**
- `backend/services/auth_dependencies.py` (modify): fail-closed
- `.env.example` (modify): задокументировать
- Backend `.env` (manual): новый `AGENT_SECRET_TOKEN`
- `~/f1league_agent/launcher_config.json` (manual): обновить `agent_token`

### Имплементация

```python
# backend/services/auth_dependencies.py
import os
import hmac
from fastapi import Header, HTTPException, status


def verify_agent_token(x_agent_token: str | None = Header(default=None)) -> bool:
    expected = os.getenv("AGENT_SECRET_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent authentication not configured. Set AGENT_SECRET_TOKEN.",
        )
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Token header")
    if not hmac.compare_digest(x_agent_token, expected):
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return True
```

### Procedure (single-user)

```bash
# 1. Сгенерировать новый токен
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Установить в backend .env:
#    AGENT_SECRET_TOKEN=<new_token>

# 3. Установить в launcher (один из вариантов):
#    - env variable на твоей машине
#    - либо ~/f1league_agent/launcher_config.json → "agent_token": "<new>"

# 4. Merge fail-closed change в backend

# 5. Перезапустить
docker compose restart backend
# + перезапустить лаунчер на своей машине

# 6. Smoke test: запустить тестовую гонку через лаунчер
```

### Acceptance criteria

1. Новый `AGENT_SECRET_TOKEN` в `.env` и в `launcher_config.json` (или env)
2. После merge: `POST /api/race/submit` без X-Agent-Token → 401
3. Гонка с лаунчера успешно загружается (200 в backend logs)
4. `compare_digest` используется
5. PR 1.0.5 уже задеплоен → graceful handling при неправильном токене

### Tests

```python
# tests/test_agent_auth.py
# Кейсы: no env / no header / wrong token / right token
```

### Rollback

Revert файла. Если не хочешь 503 — временно вернуть `True` return (плохо).

### Approval gate

**ДА**. Manual smoke test (гонка через лаунчер).

**Estimated time:** ~1 час.

---

## PR 1.2.5: /season/[id]/manage stub

**Контекст:** Эта страница бьёт в 5 несуществующих endpoints. Заглушка до Sprint 4.

**Файлы:**
- `frontend/app/season/[id]/manage/page.tsx` (rewrite as stub)
- `frontend/app/season/[id]/SeasonNav.tsx` (modify)
- `frontend/app/admin/page.tsx` (modify)
- `frontend/app/workspace/page.tsx` (modify)

### Имплементация

```tsx
// frontend/app/season/[id]/manage/page.tsx
export default function SeasonManageStubPage() {
  return (
    <main className="container mx-auto px-4 py-12">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-8 text-center">
        <h1 className="text-2xl font-semibold text-amber-900">
          Управление сезоном недоступно
        </h1>
        <p className="mt-4 text-amber-700">
          Эта страница временно отключена и будет переработана в ближайшем обновлении.
          Если вам нужно изменить календарь или настройки сезона, обратитесь к администратору.
        </p>
      </div>
    </main>
  );
}
```

### Acceptance criteria

1. `/season/[id]/manage` показывает заглушку
2. Ссылок на manage с других страниц нет
3. Никаких requests к несуществующим endpoints

### Tests

Playwright test что страница не делает API calls (Network panel пуст).

### Rollback

Не критично.

### Approval gate

Нет.

---

## PR 1.3: Next.js bump + bot port + compare_digest

**Контекст:** Next.js 14.2.5 уязвим к CVE-2025-29927. Bot опубликован на 8001. Bot secret сравнивается через `!=`.

**Файлы:**
- `frontend/package.json`: bump `next` to `^14.2.25`
- `frontend/package-lock.json`: regenerate
- `docker-compose.yml`: убрать `ports: 8001:8001` у bot
- `bot/internal_server.py`: `hmac.compare_digest`

### Имплементация

```python
# bot/internal_server.py
import hmac
import os
from aiohttp import web


BOT_NOTIFY_SECRET = os.getenv("BOT_NOTIFY_SECRET", "").strip()


@web.middleware
async def verify_secret_middleware(request: web.Request, handler):
    if not BOT_NOTIFY_SECRET:
        return web.Response(status=503, text="Bot secret not configured")
    received = request.headers.get("X-Secret", "")
    if not hmac.compare_digest(received, BOT_NOTIFY_SECRET):
        return web.Response(status=401, text="Invalid secret")
    return await handler(request)
```

### Acceptance criteria

1. `cd frontend && npx next --version` ≥ 14.2.25
2. `docker compose port bot 8001` ничего не возвращает
3. С хоста `curl http://localhost:8001/...` → connection refused
4. Из backend: `docker compose exec backend curl http://bot:8001/...` работает (с X-Secret)
5. Bot без `BOT_NOTIFY_SECRET` → 503

### Tests

- `tests/test_bot_secret.py`: 503/401/200 по сценариям

### Rollback

Revert package.json + compose.

### Approval gate

Нет.

---

## PR 1.4: Secrets rotation

**Контекст:** Все секреты из `.env` и `CLAUDE.md` считаются утёкшими.

**Подтверждено discovery:** Launcher JWT хранится в `~/f1league_agent/launcher_config.json` под ключом `auth_token`. После ротации `NEXTAUTH_SECRET` он станет invalid → лаунчер получит 401 → **PR 1.0.5** добавил graceful handling → пользователь увидит экран login.

### Procedure (детальная)

```bash
# Step 1: Сгенерировать новые значения
NEW_BOT_NOTIFY_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
NEW_NEXTAUTH_SECRET=$(openssl rand -base64 32)
NEW_POSTGRES_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")

# Step 2: Через external UI ротировать сторонние:
#   - BOT_TOKEN: @BotFather → /revoke → /token
#   - GROQ_API_KEY: console.groq.com → revoke + create
#   - GOOGLE_CLIENT_SECRET: console.cloud.google.com → reset

# Step 3: Postgres password — СПЕЦИАЛЬНЫЙ FLOW
docker compose exec postgres psql -U f1league -d f1league -c \
  "ALTER USER f1league WITH PASSWORD '$NEW_POSTGRES_PASSWORD';"

# Step 4: Обновить .env (вручную):
#   AGENT_SECRET_TOKEN= ... (уже из PR 1.2)
#   BOT_TOKEN=<new from BotFather>
#   BOT_NOTIFY_SECRET=$NEW_BOT_NOTIFY_SECRET
#   GROQ_API_KEY=<new from console>
#   NEXTAUTH_SECRET=$NEW_NEXTAUTH_SECRET
#   GOOGLE_CLIENT_SECRET=<new from gcp>
#   POSTGRES_PASSWORD=$NEW_POSTGRES_PASSWORD

# Step 5: Restart
docker compose restart backend bot backup frontend

# Step 6: Verify
docker compose logs --tail 50 backend bot
# Должны стартовать без [ERROR]
```

### Эффекты

- `NEXTAUTH_SECRET` → все NextAuth сессии инвалидированы → перелогин на сайте
- Launcher JWT смена → лаунчер 401 → PR 1.0.5 покажет login → перелогин в лаунчере
- `POSTGRES_PASSWORD` → connection pool'ы перестроятся

### Acceptance criteria

1. Все секреты обновлены (`grep -E "^[A-Z_]+=" .env | wc -l`)
2. `CLAUDE.md` без реальных секретов (placeholders `<set in .env>`)
3. Все сервисы стартуют без `[ERROR]`
4. Сайт работает: перелогин через Google → доступ
5. Лаунчер работает: login → тестовая гонка → результат на бэке
6. Backup сервис создаёт новый dump в 60 сек (`[backup] success` в логах)
7. Бот отвечает на `/start` в Telegram

### Tests

Manual smoke test (operational change).

### Rollback

Полный rollback невозможен (старые ключи компрометированы). Локальный fallback — вернуть `.env` из локальной копии.

### Approval gate

**ДА**. Полный smoke test после ротации.

---

## PR 1.5: Google id_token verification

**Контекст:** Из discovery Task 8 — текущий `signIn` callback в `frontend/lib/auth.ts` отправляет `account.providerAccountId` как `google_id` без верификации. Любой может POST'нуть `{ email: "admin@..." }` → станет system_admin.

**Архитектурное решение:** verify только на первом sign-in (когда `account` есть в callback). На refresh — доверяем backend JWT (подписан `NEXTAUTH_SECRET`).

**Файлы:**
- `backend/requirements.txt`: + `google-auth>=2.30`
- `backend/routers/web_auth.py`: переписать `/api/web/google`
- `frontend/lib/auth.ts`: использовать `account.id_token`

### Имплементация backend

```python
# backend/routers/web_auth.py
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from pydantic import BaseModel
import os


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


class GoogleLoginRequest(BaseModel):
    id_token: str  # JWT from Google, signed by Google's keys


@router.post("/api/web/google")
async def google_login(
    body: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google login not configured")

    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise HTTPException(401, f"Invalid Google token: {e}")

    email = idinfo["email"].lower()
    email_verified = idinfo.get("email_verified", False)
    if not email_verified:
        raise HTTPException(401, "Email not verified by Google")

    google_id = idinfo["sub"]
    name = idinfo.get("name", email)
    picture = idinfo.get("picture")

    # upsert WebUser logic
    # is_system_admin ТОЛЬКО если email_verified AND email in SYSTEM_ADMIN_EMAILS

    return {
        "id": user.id,
        "player_id": user.player_id,
        "token": backend_jwt,
    }
```

### Имплементация frontend

```typescript
// frontend/lib/auth.ts
callbacks: {
  async signIn({ user, account }) {
    if (account?.provider === "google") {
      const idToken = account.id_token;
      if (!idToken) {
        console.error("No id_token from Google");
        return false;
      }

      const r = await fetch(`${API}/api/web/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: idToken }),
      });

      if (!r.ok) {
        console.error("Backend rejected Google id_token");
        return false;
      }

      const data = await r.json();
      user.id = String(data.id);
      (user as any).player_id = data.player_id ?? null;
      (user as any).backendToken = data.token ?? null;
    }
    return true;
  },
  // jwt и session — без изменений
},
```

### Pre-flight check

```bash
grep -n "GoogleProvider\|google" frontend/lib/auth.ts
```

### Acceptance criteria

1. `POST /api/web/google` со старым body `{ google_id, email }` → 422
2. `POST /api/web/google` с `{ id_token: "fake.jwt" }` → 401
3. С настоящим Google id_token → 200 + WebUser
4. NextAuth login end-to-end работает
5. `is_system_admin` только при `email_verified=True AND email in SYSTEM_ADMIN_EMAILS`
6. Последующие API запросы используют backend JWT (через `apiFetch`)

### Tests

```python
# tests/test_google_verify.py
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_google_login_with_valid_id_token(client, mocker):
    mock_verify = mocker.patch("google.oauth2.id_token.verify_oauth2_token")
    mock_verify.return_value = {
        "sub": "google-user-123",
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
    }
    response = await client.post("/api/web/google", json={"id_token": "fake.token"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_google_login_with_invalid_id_token(client, mocker):
    mock_verify = mocker.patch("google.oauth2.id_token.verify_oauth2_token")
    mock_verify.side_effect = ValueError("Invalid token")
    response = await client.post("/api/web/google", json={"id_token": "invalid"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_google_login_old_format_rejected(client):
    response = await client.post("/api/web/google", json={
        "google_id": "fake",
        "email": "test@example.com",
    })
    assert response.status_code == 422
```

### Rollback

Revert файлов. **Внимание:** старая уязвимость возвращается.

### Approval gate

**ДА**. Login через Google должен работать end-to-end.

---

## Sprint 1 completion checklist

- [ ] PR 1.0: Frontend Bearer audit, все 7 endpoints из чек-листа имеют Authorization header
- [ ] PR 1.0.5: Agent 401 graceful handling, экран reconfigure работает
- [ ] PR 1.1: Backend require auth, все 16 endpoints закрыты
- [ ] PR 1.2: `AGENT_SECRET_TOKEN` fail-closed (single-user procedure)
- [ ] PR 1.2.5: `/season/[id]/manage` stub
- [ ] PR 1.3: Next.js bumped, bot port hidden, `compare_digest`
- [ ] PR 1.4: Все секреты ротированы, smoke test passed
- [ ] PR 1.5: Google `id_token` verification, login работает
- [ ] Backup checkpoint: `backups/post-sprint-1-*.pgc`
- [ ] `REFACTOR_LOG.md` обновлён

---

# Что будет в Sprint 2+

**Sprint 2 (Identity Unification: WebUser+Player → User)** — будет написан отдельно когда будешь близок к концу Sprint 1. Причина: реальный опыт работы агента в Sprint 0-1 покажет:

- Какие тесты падают/проходят (PR 0.6 даст baseline)
- Как реально работает auth после фиксов
- Какие unexpected coupling между модулями

Sprint 2 самый опасный (миграция БД, слияние двух central tables). Лучше писать его на основе реальных фактов чем сейчас.

**Дальнейшие спринты (в общих чертах):**

```
Sprint 2 → Identity Unification: WebUser+Player → User
Sprint 3 → Auth schema под Bearer (убрать web_user_id из body), token revocation
Sprint 4 → Lobby → League rename + cleanup (drop SeasonModerator, dead fields)
Sprint 5 → Race без обязательного Season + per-league rating (PlayerRating per league)
Sprint 6 → UX rebuild (объединить /me + /workspace, переписать /season/[id]/manage)
Sprint 7 → Performance (N+1, shared async engine, indexes, _broadcast)
Sprint 8 → Contracts UI (frontend для контрактов)
Sprint 9 → Bot deprecation + polish
```

Реалистично весь рефактор займёт 6-10 недель.

---

# Стартовая инструкция

1. Открой Claude Code в `C:\f1t`
2. Запусти **PR -0.5.2** (этот документ, секция Sprint -0.5)
3. Когда агент закончит — пришли результат и переходи к **PR -0.5.3**
4. Далее по порядку: **PR 0.1 → 0.2 → 0.3 → 0.6.1 → 0.6.2 → 0.6.3 → 1.0 → 1.0.5 → 1.1 → ...**
5. На каждом **Approval gate** останавливайся, проверяй что сделано, подтверждай словами "ОК, merge"
6. На любой неожиданности — сообщи владельцу до продолжения

## Что у тебя есть как safety net

- `backups/pre-refactor-baseline-*.pgc` + копия на внешнем носителе
- Git tag `pre-refactor-baseline`
- Automated backup сервис (после PR 0.1)
- Staging procedure для тестирования миграций (после PR -0.5.3)
- Working test suite (после Sprint 0.6)

Удачи. Это серьёзный рефактор, но план обоснован, discovery подтверждён, ревью качественные. На любой панике в моменте — есть бэкап и git tag, всё откатывается.

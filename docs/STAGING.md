# Staging Procedure

Используется для тестирования миграций перед production.
Поднимается из production dump, после теста сносится.

## Lifecycle

1. Создать свежий dump production:

   ```bash
   docker compose exec postgres pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc \
     > /tmp/prod.pgc
   ```

2. Поднять staging:

   ```bash
   ./scripts/staging_up.sh /tmp/prod.pgc
   ```

3. Прогнать миграцию:

   ```bash
   COMPOSE_PROJECT_NAME=f1t-staging \
     docker compose \
       -f docker-compose.yml \
       -f docker-compose.staging.override.yml \
       exec backend alembic upgrade head
   ```

4. Smoke test на `http://localhost:8002`.

5. Если всё ОК — катить на production.

6. Снести:

   ```bash
   ./scripts/staging_down.sh
   ```

## Архитектура

- `COMPOSE_PROJECT_NAME=f1t-staging` изолирует контейнеры, сеть и volume от production
  (имена становятся `f1t-staging-postgres-1`, `f1t-staging_postgres_staging_data`, и т.д.)
- В `docker-compose.staging.override.yml` используется `!override` для `ports` и
  `volumes`, потому что Compose по умолчанию **мерджит** списки между файлами —
  без `!override` staging-postgres попытался бы забиндить 5432 и упал бы на
  конфликте с прод-стеком.
- Backend в staging читает прод-код через тот же bind-mount `./backend:/app/backend`,
  так что миграции тестируются на той же кодовой базе, что и на проде.

## Порты

| Stack       | Backend          | Postgres            |
|-------------|------------------|---------------------|
| Production  | `localhost:8000` | `localhost:5432`    |
| Staging     | `localhost:8002` | `localhost:5433`    |

Оба биндятся на `127.0.0.1` — наружу не торчат.

Note: 8001 не используется для staging backend, так как этот порт занят production
сервисом `bot`. После PR 1.3 bot перестанет публиковать 8001 наружу — тогда staging
backend можно будет вернуть на 8001 (или оставить на 8002 — без разницы).

## Ограничения

- Volume `postgres_staging_data` изолированный; после `staging_down.sh` данные пропадают.
- Staging **не** обновляется автоматически — данные на момент сделанного dump.
- Используется только для тестов миграций, не для разработки.
- Bot/frontend в staging не поднимаются (намеренно — миграции тестируются на API уровне).

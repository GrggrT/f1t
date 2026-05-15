# F1 League — Sprint 2 Spec: Identity Unification (WebUser + Player → User)

> **Версия:** 1.0
> **Дата:** 15 мая 2026
> **Pre-conditions:** Sprint 1 closure done (Item 3, Item 4 ✅)
> **Стиль:** Compact — pseudocode + acceptance criteria, trust agent на implementation details
> **Целевая длительность:** 7-10 рабочих дней
> **Risk level:** HIGH (DB миграции, слияние central tables)

---

## Цель спринта (one sentence)

Слить `web_users` и `players` в одну таблицу `users`, чтобы один пользователь = один объект identity, без необходимости ручной "привязки игрока".

## Архитектурные решения (зафиксированы)

```yaml
target_table: users
merge_strategy: dual_write_via_postgres_trigger  # не application-code
conflict_resolution:
  name: COALESCE(player.name, web_user.name)
  avatar_url: COALESCE(player.avatar_url, web_user.picture)
  steam_id64: COALESCE(player.steam_id64, web_user.steam_id64)
  steam_names: player only
  steam_url: player only
  telegram_id: player only
  email, password, google_id, is_system_admin: web_user only
edge_case_player_without_webuser: stays as User with NULL email
edge_case_webuser_without_player: stays as User with NULL telegram_id
edge_case_player_telegram_no_webuser_then_google_login: stays separate; manual merge UI in Sprint 6
stop_the_world_acceptable: unlimited (no current launcher users)
observation_period_before_drop: 48h standard
backup_per_pr: mandatory
```

## Глобальные правила (как в Sprint 1)

1. **Stop-the-world** перед каждой миграцией: `pg_dump` → `docker compose stop backend bot` → migration → restart → smoke test
2. **Approval gate** = STOP, не комментарий
3. **Pre-flight grep** перед каждым PR
4. **Одна alembic миграция = один PR** (или одна логически связанная группа миграций)
5. **Tests должны passing** после каждого PR (61 baseline + новые)

---

## PR 2.1: Schema + Backfill + Dual-Write Trigger

**Risk:** HIGH (создаёт новую схему, копирует данные, ставит trigger)
**Estimated:** 2-3 дня

### Цель

Создать таблицу `users`, наполнить из обоих legacy таблиц, поставить PostgreSQL trigger для dual-write на период миграции. Application code **не трогаем** — после этого PR backend продолжает работать через legacy таблицы как до миграции.

### Файлы

- `scripts/analyze_user_player_merge.py` (create, read-only)
- `backend/migrations/versions/0013_create_users_table.py` (create)
- `backend/migrations/versions/0014_dual_write_trigger.py` (create)
- `backend/models/models.py` (modify): добавить `User` класс **не удаляя** WebUser/Player

### Pre-flight grep

```bash
# Найти все FK на web_users / players
grep -rn "ForeignKey.*web_users\|ForeignKey.*players" backend/models/

# Подтвердить что Player.steam_names действительно ARRAY
grep -n "steam_names" backend/models/models.py

# Проверить uniqueness assumptions
grep -n "UniqueConstraint\|unique=True" backend/models/models.py
```

Записать в REFACTOR_LOG sub-section `## Sprint 2 / PR 2.1: pre-flight`:
- Список таблиц с FK на web_users (ожидаем ~5)
- Список таблиц с FK на players (ожидаем ~7)
- Total: ~10-12 таблиц с FK затронуты

### Pseudocode

**`scripts/analyze_user_player_merge.py`:**

```python
"""Read-only analysis. Run BEFORE any migration.

Outputs report covering:
1. count(*) web_users where player_id IS NULL  → web-only users
2. count(*) web_users where player_id IS NOT NULL  → linked
3. count(*) players where id NOT IN (select player_id from web_users WHERE player_id IS NOT NULL)  → player-only
4. count(*) where web_users.email is NULL  → expected 0
5. count(*) where players.player_id has multiple web_users  → expected 0 (conflict!)
6. Steam ID conflicts: web_user.steam_id64 != player.steam_id64 for linked pairs
7. Name conflicts: log all linked pairs where web_user.name != player.name (informational)
"""

# Run via:
# docker compose exec backend python scripts/analyze_user_player_merge.py
# Output to: backups/user_player_merge_analysis_$(date).md
```

**Acceptance for analysis script:**
- Report file создан
- Если найдены conflicts (multiple web_users per player, steam_id mismatch) — STOP, manual review
- Если нет conflicts → continue

**`0013_create_users_table.py`:**

```python
"""
Create users table with all merged fields.
Backfill from web_users + players.
DO NOT touch existing tables yet.
"""

def upgrade():
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String, nullable=True, unique=True),
        sa.Column('hashed_password', sa.String, nullable=True),
        sa.Column('google_id', sa.String, nullable=True, unique=True),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('avatar_url', sa.String, nullable=True),
        sa.Column('telegram_id', sa.BigInteger, nullable=True, unique=True),
        sa.Column('steam_id64', sa.String, nullable=True, unique=True),
        sa.Column('steam_names', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('steam_url', sa.String, nullable=True),
        sa.Column('is_system_admin', sa.Boolean, server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        # Tracking columns — для traceability + sync
        sa.Column('legacy_web_user_id', sa.Integer, nullable=True, unique=True),
        sa.Column('legacy_player_id', sa.Integer, nullable=True, unique=True),
    )

    # 2. Backfill — Case 1: linked (web_user.player_id IS NOT NULL)
    op.execute("""
        INSERT INTO users (
            email, hashed_password, google_id, name, avatar_url,
            telegram_id, steam_id64, steam_names, steam_url,
            is_system_admin, legacy_web_user_id, legacy_player_id
        )
        SELECT
            w.email, w.hashed_password, w.google_id,
            COALESCE(p.name, w.name),
            COALESCE(p.avatar_url, w.picture),
            p.telegram_id,
            COALESCE(p.steam_id64, w.steam_id64),
            p.steam_names, p.steam_url,
            w.is_system_admin,
            w.id, p.id
        FROM web_users w
        INNER JOIN players p ON w.player_id = p.id
    """)

    # 3. Backfill — Case 2: web-only (web_user without player)
    op.execute("""
        INSERT INTO users (
            email, hashed_password, google_id, name, avatar_url,
            steam_id64, is_system_admin, legacy_web_user_id
        )
        SELECT
            w.email, w.hashed_password, w.google_id, w.name, w.picture,
            w.steam_id64, w.is_system_admin, w.id
        FROM web_users w
        WHERE w.player_id IS NULL
    """)

    # 4. Backfill — Case 3: player-only (player created via bot, no web account)
    op.execute("""
        INSERT INTO users (
            name, avatar_url, telegram_id, steam_id64, steam_names, steam_url,
            is_system_admin, legacy_player_id
        )
        SELECT
            p.name, p.avatar_url, p.telegram_id, p.steam_id64, p.steam_names, p.steam_url,
            false, p.id
        FROM players p
        WHERE p.id NOT IN (SELECT player_id FROM web_users WHERE player_id IS NOT NULL)
    """)

    # 5. Create indexes
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'])
    op.create_index('ix_users_steam_id64', 'users', ['steam_id64'])
    op.create_index('ix_users_legacy_web_user_id', 'users', ['legacy_web_user_id'])
    op.create_index('ix_users_legacy_player_id', 'users', ['legacy_player_id'])


def downgrade():
    op.drop_table('users')
```

**`0014_dual_write_trigger.py`:**

```python
"""
PostgreSQL triggers для dual-write на период PR 2.1 → PR 2.5.

Когда писатель меняет web_users или players — соответствующая запись
в users обновляется автоматически. Это гарантирует что users остаётся
синхронным без application-level кода.
"""

def upgrade():
    op.execute("""
        -- Sync from web_users to users
        CREATE OR REPLACE FUNCTION sync_web_user_to_users() RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO users (
                    email, hashed_password, google_id, name, avatar_url,
                    steam_id64, is_system_admin, legacy_web_user_id
                ) VALUES (
                    NEW.email, NEW.hashed_password, NEW.google_id,
                    COALESCE(
                        (SELECT name FROM players WHERE id = NEW.player_id),
                        NEW.name
                    ),
                    COALESCE(
                        (SELECT avatar_url FROM players WHERE id = NEW.player_id),
                        NEW.picture
                    ),
                    NEW.steam_id64, NEW.is_system_admin, NEW.id
                ) ON CONFLICT (legacy_web_user_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    hashed_password = EXCLUDED.hashed_password,
                    google_id = EXCLUDED.google_id,
                    is_system_admin = EXCLUDED.is_system_admin;

                -- If web_user linked to player → update tracking
                IF NEW.player_id IS NOT NULL THEN
                    UPDATE users SET legacy_player_id = NEW.player_id
                    WHERE legacy_web_user_id = NEW.id;
                END IF;
            ELSIF (TG_OP = 'UPDATE') THEN
                UPDATE users SET
                    email = NEW.email,
                    hashed_password = NEW.hashed_password,
                    google_id = NEW.google_id,
                    is_system_admin = NEW.is_system_admin,
                    legacy_player_id = NEW.player_id
                WHERE legacy_web_user_id = NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_web_user_to_users
        AFTER INSERT OR UPDATE ON web_users
        FOR EACH ROW EXECUTE FUNCTION sync_web_user_to_users();
    """)

    op.execute("""
        -- Sync from players to users
        CREATE OR REPLACE FUNCTION sync_player_to_users() RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                -- Check if this player will be linked to a web_user (via player_id in web_users)
                -- If not — create standalone User
                INSERT INTO users (
                    name, avatar_url, telegram_id, steam_id64, steam_names, steam_url,
                    is_system_admin, legacy_player_id
                ) VALUES (
                    NEW.name, NEW.avatar_url, NEW.telegram_id, NEW.steam_id64,
                    NEW.steam_names, NEW.steam_url, false, NEW.id
                ) ON CONFLICT (legacy_player_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url),
                    telegram_id = EXCLUDED.telegram_id,
                    steam_id64 = EXCLUDED.steam_id64,
                    steam_names = EXCLUDED.steam_names,
                    steam_url = EXCLUDED.steam_url;
            ELSIF (TG_OP = 'UPDATE') THEN
                UPDATE users SET
                    name = NEW.name,
                    avatar_url = COALESCE(NEW.avatar_url, avatar_url),
                    telegram_id = NEW.telegram_id,
                    steam_id64 = NEW.steam_id64,
                    steam_names = NEW.steam_names,
                    steam_url = NEW.steam_url
                WHERE legacy_player_id = NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_player_to_users
        AFTER INSERT OR UPDATE ON players
        FOR EACH ROW EXECUTE FUNCTION sync_player_to_users();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_sync_web_user_to_users ON web_users;")
    op.execute("DROP TRIGGER IF EXISTS trg_sync_player_to_users ON players;")
    op.execute("DROP FUNCTION IF EXISTS sync_web_user_to_users();")
    op.execute("DROP FUNCTION IF EXISTS sync_player_to_users();")
```

**User class в `backend/models/models.py`** (добавить, не удалять WebUser/Player):

```python
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(unique=True)
    hashed_password: Mapped[str | None]
    google_id: Mapped[str | None] = mapped_column(unique=True)
    name: Mapped[str]
    avatar_url: Mapped[str | None]
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    steam_id64: Mapped[str | None] = mapped_column(unique=True)
    steam_names: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    steam_url: Mapped[str | None]
    is_system_admin: Mapped[bool] = mapped_column(default=False, server_default='false')
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    legacy_web_user_id: Mapped[int | None] = mapped_column(unique=True)
    legacy_player_id: Mapped[int | None] = mapped_column(unique=True)
```

### Acceptance criteria

1. ✅ Analysis report `backups/user_player_merge_analysis_*.md` создан, без conflicts
2. ✅ `SELECT COUNT(*) FROM users` = `COUNT(*)` web_users c player_id NOT NULL + web-only + player-only
3. ✅ Каждый row в `users` имеет хотя бы один из `legacy_web_user_id` / `legacy_player_id` non-NULL
4. ✅ Linked pairs: `users` row имеет ОБА legacy ids non-NULL
5. ✅ Web-only: только `legacy_web_user_id` non-NULL, `telegram_id IS NULL`
6. ✅ Player-only: только `legacy_player_id` non-NULL, `email IS NULL`
7. ✅ Trigger test: `INSERT INTO web_users (email, name) VALUES (...)` → автоматически появляется в `users`
8. ✅ Trigger test: `UPDATE players SET name = '...'` → `users.name` обновляется
9. ✅ Все 61 existing tests passing
10. ✅ Backend стартует и работает через legacy таблицы (application code не тронут)

### Tests (новые)

```python
# tests/test_user_unification_schema.py

@pytest.mark.asyncio
async def test_users_table_populated_from_backfill(db_session):
    """Verify backfill produced correct counts."""

@pytest.mark.asyncio
async def test_linked_pair_has_both_legacy_ids(db_session):
    """For each web_user.player_id IS NOT NULL → users row has both legacy_*_id."""

@pytest.mark.asyncio
async def test_player_only_has_no_email(db_session):
    """Player created via bot → users row has email IS NULL."""

@pytest.mark.asyncio
async def test_trigger_syncs_new_web_user(db_session):
    """INSERT INTO web_users → users row automatically created."""

@pytest.mark.asyncio
async def test_trigger_syncs_player_update(db_session):
    """UPDATE players.name → users.name reflects change."""
```

### Rollback

```bash
docker compose stop backend bot
docker compose run --rm backend alembic downgrade -2
docker compose start backend bot
```

После этого `users` таблицы нет, триггеров нет, web_users/players нетронуты.

### Approval gate

**ДА.** После migration, перед merge:
1. Проверить analysis report — нет conflicts
2. Проверить counts в `users`
3. Smoke test: create test web_user → видна в `users`
4. Подтвердить продолжение

---

## PR 2.2: Backend Reads Switch

**Risk:** HIGH (переключение всех reads)
**Estimated:** 2-3 дня

### Цель

Все backend код читает из `User`, не из `WebUser`/`Player`. Writes продолжают идти в legacy таблицы (через старую логику), но trigger из PR 2.1 синхронизирует `users`. Это даёт возможность откатить если что-то сломается.

### Файлы

- `backend/models/models.py`: User класс уже есть из PR 2.1, теперь обновить relationships
- `backend/routers/*.py`: все routers переключаются на User
- `backend/services/*.py`: все services
- `backend/routers/practice.py`: **raw SQL** — отдельный focus
- `backend/services/auth_dependencies.py`: `get_current_user` возвращает User вместо WebUser

### Pre-flight grep

```bash
# Найти все references на WebUser и Player в backend (не в models)
grep -rn "WebUser\|Player" backend/ --include="*.py" | grep -v "backend/models/" | grep -v "test_"

# Найти raw SQL в practice
grep -n "text(" backend/routers/practice.py

# Найти все Depends(get_current_user)
grep -rn "get_current_user\|get_current_player" backend/ --include="*.py"
```

Записать в REFACTOR_LOG: ожидаем что reads переписаны во всех routers, plus practice raw SQL.

### Pseudocode (паттерны)

**Pattern 1: Lookup by email (WebUser → User)**

```python
# Before:
user = await db.scalar(select(WebUser).where(WebUser.email == email))

# After:
user = await db.scalar(select(User).where(User.email == email))
```

**Pattern 2: Lookup by telegram_id (Player → User)**

```python
# Before:
player = await db.scalar(select(Player).where(Player.telegram_id == tg_id))

# After:
user = await db.scalar(select(User).where(User.telegram_id == tg_id))
```

**Pattern 3: Joined queries**

```python
# Before:
results = await db.execute(
    select(WebUser, Player)
    .join(Player, WebUser.player_id == Player.id)
    .where(WebUser.email == email)
)

# After (one table, one query):
user = await db.scalar(select(User).where(User.email == email))
# Все поля доступны напрямую: user.telegram_id, user.steam_id64, etc.
```

**Pattern 4: `get_current_user` returns User**

```python
# backend/services/auth_dependencies.py

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:  # was WebUser
    payload = decode_jwt(token)
    user_id = payload.get("legacy_web_user_id") or payload.get("user_id")  # backward compat
    # First try by legacy_web_user_id (existing JWTs)
    user = await db.scalar(
        select(User).where(User.legacy_web_user_id == user_id)
    )
    # Fallback by new id
    if not user:
        user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(401, "User not found")
    return user
```

**Pattern 5: Practice raw SQL**

```python
# backend/routers/practice.py — переписать text() запросы:

# Before:
await db.execute(
    text("INSERT INTO practice_sessions (web_user_id, ...) VALUES (:wuid, ...)"),
    {"wuid": web_user.id, ...}
)

# After:
await db.execute(
    text("INSERT INTO practice_sessions (user_id, ...) VALUES (:uid, ...)"),
    {"uid": user.id, ...}
)
```

⚠️ Внимание: `practice_sessions.user_id` ещё не существует! Нужна доп миграция в PR 2.2:

**`0015_add_user_id_to_practice.py`:**

```python
def upgrade():
    op.add_column('practice_sessions', sa.Column('user_id', sa.Integer, nullable=True))
    op.execute("""
        UPDATE practice_sessions ps
        SET user_id = u.id
        FROM users u
        WHERE u.legacy_web_user_id = ps.web_user_id
    """)
    op.alter_column('practice_sessions', 'user_id', nullable=False)
    op.create_foreign_key('fk_practice_user', 'practice_sessions', 'users', ['user_id'], ['id'])
    op.create_index('ix_practice_sessions_user_id', 'practice_sessions', ['user_id'])
    # web_user_id остаётся пока — drop в PR 2.5

def downgrade():
    op.drop_index('ix_practice_sessions_user_id')
    op.drop_constraint('fk_practice_user', 'practice_sessions', type_='foreignkey')
    op.drop_column('practice_sessions', 'user_id')
```

### Endpoints to update (high-level inventory)

Approximate (agent verify via grep):

| File | Endpoints affected | Notes |
|------|---------------------|-------|
| `routers/web_auth.py` | login, register, google, me, link-player | Heavy — auth heart |
| `routers/players_admin.py` | register, map_steam, PATCH /players/{id} | Player references → User |
| `routers/lobby.py` | All endpoints (creator, members) | WebUser → User |
| `routers/seasons.py` | assistant, list | WebUser → User |
| `routers/contracts.py` | accept, generate | Player → User |
| `routers/races.py` | submit (player resolution by steam_id64) | Player → User lookup |
| `routers/telemetry.py` | debrief endpoints | WebUser → User |
| `routers/analytics.py` | predict, ratings | WebUser → User |
| `routers/practice.py` | sessions, laps | **Raw SQL + new migration** |
| `routers/players.py` | profile, stats | Player → User |
| `routers/admin.py` | seasons, users management | WebUser → User |
| `routers/stewards.py` | penalties | Player + WebUser → User |

### Acceptance criteria

1. ✅ `grep -rn "WebUser\|Player" backend/ --include="*.py" | grep -v "backend/models/" | grep -v "test_" | grep -v "legacy"` → empty (или только в comments)
2. ✅ Practice raw SQL переписан на user_id
3. ✅ Migration 0015 применена, practice_sessions.user_id заполнена
4. ✅ `get_current_user` возвращает User
5. ✅ Все existing 61 tests passing
6. ✅ Новые tests для User flow добавлены (~10-15 штук)
7. ✅ Smoke test: login → /me → /workspace → /lobby/[id] → создать сезон → AI engineer → всё работает
8. ✅ Backend стартует без warnings/errors

### Tests (новые)

```python
# tests/test_user_reads.py

@pytest.mark.asyncio
async def test_get_current_user_returns_user_not_webuser():
    """JWT decode → User object, not WebUser."""

@pytest.mark.asyncio
async def test_lobby_creator_is_user():
    """POST /api/lobby → Lobby.creator references User table via legacy_web_user_id."""

@pytest.mark.asyncio
async def test_practice_session_uses_user_id():
    """POST /api/practice/sessions → row.user_id is non-null."""

@pytest.mark.asyncio
async def test_race_submit_resolves_steam_to_user():
    """POST /api/race/submit with steam_id64 → race_result.user_id populated."""

@pytest.mark.asyncio
async def test_steam_only_user_no_email():
    """User registered via Steam → email IS NULL, login still works."""
```

### Rollback

```bash
docker compose stop backend bot
docker compose run --rm backend alembic downgrade -1  # rollback migration 0015
git revert <PR 2.2 merge commit>
docker compose build backend
docker compose start backend bot
```

Сложнее чем PR 2.1 rollback, но reversible. Trigger из PR 2.1 продолжит работать.

### Approval gate

**ДА.** Это самый большой read switch. Перед merge:
1. Все тесты passing (61 + новые)
2. Manual smoke test всех journeys (login, lobby, race submit через лаунчер если возможно, AI engineer, practice)
3. Backend логи без `[ERROR]` за 30 минут production
4. Approval

---

## PR 2.3: Bot Adaptation

**Risk:** MEDIUM (изолированный сервис, легче откатить)
**Estimated:** 1 день

### Цель

Telegram bot handlers переходят на новую User-модель через backend API. Bot собственный код перестаёт прямо обращаться к Player таблице (он и так этого не делал — он ходит в backend).

### Файлы

- `bot/handlers/commands.py`: /register, /stats, /addsteam, /standings, /last
- `bot/handlers/achievements.py`: /achievements
- `bot/handlers/contracts.py`: /contracts, /accept
- `bot/handlers/stewards.py`: /remove_penalty (admin only)
- `bot/api_client.py`: типы и endpoints

### Pre-flight grep

```bash
# Найти все api_client calls в bot
grep -rn "api_client\." bot/ --include="*.py"

# Найти hardcoded "player" / "web_user" в bot
grep -rn "player\|web_user" bot/ --include="*.py" | grep -v ".pyc"
```

### Pseudocode

**Pattern: API response shape changed**

```python
# Before:
async def cmd_stats(message: Message):
    response = await api_client.get(f"/api/players/by_telegram/{message.from_user.id}")
    if response.status == 404:
        await message.reply("Player not found. Use /register first.")
        return
    player = response.json()
    # player.id, player.name, player.steam_id64 etc.

# After:
async def cmd_stats(message: Message):
    response = await api_client.get(f"/api/users/by_telegram/{message.from_user.id}")
    if response.status == 404:
        await message.reply("User not found. Use /register first.")
        return
    user = response.json()
    # user.id, user.name, user.steam_id64, user.email (might be NULL), etc.
```

**Backend endpoint to add (in PR 2.2 actually, or here):**

```python
# backend/routers/users.py (new or extend players.py)

@router.get("/api/users/by_telegram/{telegram_id}")
async def get_user_by_telegram(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        raise HTTPException(404, "User not found")
    return user
```

**Backward compat:** старый `/api/players/by_telegram/{tg_id}` может оставаться как deprecated alias на новый endpoint, или удалиться сразу. Решает agent based on grep.

### Acceptance criteria

1. ✅ Все bot команды работают через `/api/users/*` endpoints
2. ✅ `/register` создаёт User через POST `/api/users/register` (либо адаптированный existing endpoint)
3. ✅ `/stats <telegram_id>` показывает stats для User
4. ✅ `/addsteam <steam_url>` привязывает steam_id64 к User по telegram_id
5. ✅ Bot стартует без ошибок
6. ✅ Manual smoke test в Telegram: `/register`, `/stats`, `/standings`, `/last`

### Tests

```python
# tests/test_bot_user_adaptation.py

@pytest.mark.asyncio
async def test_register_command_creates_user():
    """/register in TG → User row with telegram_id."""

@pytest.mark.asyncio
async def test_stats_command_returns_user_data():
    """/stats <tg_id> returns user's race stats."""
```

### Rollback

```bash
git revert <PR 2.3 merge commit>
docker compose build bot
docker compose restart bot
```

Backend продолжает работать.

### Approval gate

**ДА.** Manual test нескольких bot команд в реальном Telegram chat.

---

## PR 2.4: Frontend Unification

**Risk:** MEDIUM (TypeScript build защищает от части ошибок)
**Estimated:** 1-2 дня

### Цель

Frontend types и UI пересмотрены: один `User` тип вместо WebMe + Player + FullProfile. Страница /me упрощается (нет "привязать игрока"). Profile pages универсальны.

### Файлы

- `frontend/lib/api.ts`: User type, удалить WebMe/Player/FullProfile (или alias)
- `frontend/lib/auth.ts`: callbacks возвращают User
- `frontend/app/me/page.tsx`: упрощение — нет секции "привязать игрока"
- `frontend/app/profile/[id]/page.tsx`: универсальный профиль User
- `frontend/app/players/[id]/page.tsx`: то же
- `frontend/app/workspace/page.tsx`: типы
- `frontend/app/admin/page.tsx`: типы

### Pre-flight grep

```bash
# Найти все WebMe / Player / FullProfile в frontend
grep -rn "WebMe\|FullProfile" frontend/ --include="*.ts" --include="*.tsx"
grep -rn "interface Player\|type Player\b" frontend/ --include="*.ts" --include="*.tsx"
```

### Pseudocode

**`frontend/lib/api.ts`:**

```typescript
// Before:
export interface WebMe {
  id: string;
  email: string;
  name: string;
  player_id: number | null;
  // ...
}

export interface Player {
  id: number;
  name: string;
  telegram_id: number | null;
  steam_id64: string | null;
  // ...
}

export interface FullProfile extends Player {
  // race stats etc.
}

// After:
export interface User {
  id: string;
  email: string | null;
  name: string;
  avatar_url: string | null;
  telegram_id: number | null;
  steam_id64: string | null;
  steam_names: string[] | null;
  is_system_admin: boolean;
  // Stats nested
  stats: {
    races: number;
    wins: number;
    podiums: number;
    rating: number;
    // ...
  } | null;
}

// Backwards compat — alias for gradual migration:
export type WebMe = User;
export type Player = User;
export type FullProfile = User;
```

**`/me/page.tsx` упрощение:**

```tsx
// Before:
{me.player_id === null && (
  <Card>
    <CardTitle>Привязать профиль игрока</CardTitle>
    <select value={selectedPlayerId} onChange={...}>
      {availablePlayers.map(p => <option>...</option>)}
    </select>
    <Button onClick={handleLinkPlayer}>Привязать</Button>
  </Card>
)}

// After:
// Эта секция полностью удалена. /me просто показывает User profile.
// Если у юзера нет telegram_id — небольшая подсказка "Подключите Telegram бот"
// (но не блокирует UI).
```

### Acceptance criteria

1. ✅ TypeScript build green (`npm run build`)
2. ✅ `frontend/lib/api.ts` экспортирует `User` type
3. ✅ /me не имеет "привязать игрока" секции
4. ✅ /profile/[id] работает универсально (no special-casing for player vs web user)
5. ✅ NextAuth session.user типизирован как User
6. ✅ Manual smoke test: login → /me → /profile/[id] → /workspace → всё рендерится без ошибок в консоли

### Tests

```typescript
// frontend/tests/types-unification.test.ts
// Проверка что User type соответствует backend response shape

// frontend/tests/me-page.test.tsx
// Snapshot test что /me НЕ содержит "Привязать игрока"
```

### Rollback

```bash
git revert <PR 2.4 merge commit>
docker compose build frontend
docker compose up -d frontend
```

### Approval gate

**ДА.** Manual smoke test всех страниц.

---

## PR 2.5: Drop Legacy (48h After PR 2.4)

**Risk:** HIGH (destructive — drops tables)
**Estimated:** 1 день (но 48h observation period before)
**Pre-conditions:** 48h prod без `[ERROR]`, без 5xx в backend логах

### Цель

Удалить legacy таблицы и колонки. После этого PR — single source of truth: `users` table.

### Файлы

- `backend/migrations/versions/0016_drop_legacy_user_columns.py` (create)
- `backend/migrations/versions/0017_drop_legacy_tables.py` (create)
- `backend/migrations/versions/0018_cleanup_users_tracking.py` (create, optional)
- `backend/models/models.py`: удалить WebUser, Player, SeasonModerator классы

### Pseudocode

**`0016_drop_legacy_user_columns.py`:**

```python
"""
Drop columns referencing web_users / players in dependent tables.
Drop triggers (no longer needed).
"""

def upgrade():
    # 1. Drop triggers (no longer dual-write)
    op.execute("DROP TRIGGER IF EXISTS trg_sync_web_user_to_users ON web_users;")
    op.execute("DROP TRIGGER IF EXISTS trg_sync_player_to_users ON players;")
    op.execute("DROP FUNCTION IF EXISTS sync_web_user_to_users();")
    op.execute("DROP FUNCTION IF EXISTS sync_player_to_users();")

    # 2. Drop legacy FK columns in dependent tables
    # (agent: enumerate via grep, but expect these tables):
    op.drop_column('practice_sessions', 'web_user_id')
    op.drop_column('lobby_members', 'web_user_id')  # → user_id
    op.drop_column('lobbies', 'creator_id')  # → creator_user_id
    op.drop_column('seasons', 'creator_id')
    op.drop_column('race_results', 'player_id')  # → user_id
    op.drop_column('rating_history', 'player_id')
    op.drop_column('player_ratings', 'player_id')
    op.drop_column('player_achievements', 'player_id')
    op.drop_column('penalty_corrections', 'player_id')
    op.drop_column('penalty_corrections', 'applied_by')
    op.drop_column('season_contracts', 'player_id')
    op.drop_column('championship_standings', 'player_id')
    # races.host_player_id — dead column from discovery
    op.drop_column('races', 'host_player_id')

def downgrade():
    raise NotImplementedError("Restore from backup; this migration is destructive.")
```

⚠️ Wait — drop columns assumes that dependent tables ALREADY have new `user_id` columns. They don't yet — agent должен добавить их в **PR 2.2** (как с practice_sessions). Уточнение для агента:

**В PR 2.2 для каждой dependent таблицы:**
- Добавить `user_id` (или `creator_user_id` для lobbies/seasons) column
- Backfill через `JOIN users ON legacy_*_id`
- Создать FK constraint, index
- Старая колонка остаётся пока

**В PR 2.5 теперь:**
- Drop старые колонки
- Drop triggers
- Drop tables web_users, players, season_moderators

**`0017_drop_legacy_tables.py`:**

```python
def upgrade():
    op.drop_table('web_users')
    op.drop_table('players')
    op.drop_table('season_moderators')  # dead from discovery

def downgrade():
    raise NotImplementedError("Restore from backup.")
```

**`0018_cleanup_users_tracking.py`** (optional):

```python
"""
After successful production stability, drop tracking columns.
This is cosmetic — they're nullable and don't hurt.
Can be deferred to a later cleanup PR.
"""
def upgrade():
    op.drop_column('users', 'legacy_web_user_id')
    op.drop_column('users', 'legacy_player_id')
```

**Models cleanup:**

```python
# backend/models/models.py
# Удалить классы:
# - class WebUser
# - class Player
# - class SeasonModerator

# Keep only User and дочерние таблицы with user_id FK.
```

### Acceptance criteria

1. ✅ 48 часов production без `[ERROR]` в backend/bot/frontend logs
2. ✅ Pre-migration fresh backup: `backups/pre-sprint-2-final-*.pgc`
3. ✅ Migration applied, alembic upgrade head succeeds
4. ✅ `psql \dt` не показывает `web_users`, `players`, `season_moderators`
5. ✅ Все 61+ tests passing после migration
6. ✅ Smoke test всех journeys
7. ✅ Backup post-sprint-2: `backups/post-sprint-2-*.pgc`
8. ✅ Git tag `post-sprint-2`
9. ✅ REFACTOR_LOG.md updated

### Tests

Существующих 61+ тестов достаточно. Если они проходят с пустыми legacy tables — миграция OK.

### Rollback

⚠️ **Only via backup restore.** После DROP TABLE downgrade не работает.

```bash
docker compose stop backend bot
docker compose exec postgres pg_restore -U f1league -d f1league \
  --clean --if-exists --no-owner < backups/pre-sprint-2-final-*.pgc
docker compose start backend bot
git revert <PR 2.5 merge commit>
```

### Approval gate

**ДА — самый критичный gate в Sprint 2.** Перед merge:

1. Подтверждение что 48 часов прошло
2. `docker compose logs backend bot --since 48h | grep -i "error\|exception"` — empty (или только known harmless)
3. Свежий backup сделан (`backups/pre-sprint-2-final-*.pgc`)
4. External copy backup'a
5. На staging (через `./scripts/staging_up.sh`) миграция протестирована
6. Только тогда merge

---

## Sprint 2 Completion Checklist

- [ ] PR 2.1: schema + backfill + dual-write trigger
- [ ] PR 2.2: backend reads switch + practice migration
- [ ] PR 2.3: bot adaptation
- [ ] PR 2.4: frontend types unification
- [ ] **48h observation** between PR 2.4 and PR 2.5
- [ ] PR 2.5: drop legacy tables
- [ ] Backup checkpoint: `backups/post-sprint-2-*.pgc` + external copy
- [ ] Git tag `post-sprint-2`
- [ ] REFACTOR_LOG.md: Sprint 2 closure section

---

## What's Next (Sprint 3 preview)

After Sprint 2:

```
Sprint 3 → Auth schema cleanup
  - Remove web_user_id from request bodies (use Bearer JWT only)
  - Token revocation mechanism
  - PyJWT instead of custom HMAC
  - JWT claims: iss, aud, exp, token_version

Sprint 4 → Lobby → League rename
  - Conceptual: League = долгоживущее сообщество
  - Season = временной отрезок внутри League
  - SeasonModerator class removal (table уже dropped в Sprint 2)
  - Migration: rename table, models, frontend strings

Sprint 5 → Race без обязательного Season
  - race.season_id nullable
  - PlayerRating per (user_id, league_id) — per-league Glicko
  - Casual races support

Sprint 6 → UX rebuild + Telegram link UI
  - Manual link: User with Google login can connect to bot-only User
  - One canonical /me page
  - Removed /workspace duplication
```

---

## Notes for Agent (важно)

1. **Каждый PR — отдельная feature branch.** Не нагромождать.
2. **После каждого PR pause** — даже если approval gate говорит "нет, automatic", всё равно дать 1 час production observation перед началом следующего PR.
3. **При первом 🔴 в логах между PR'ами — STOP, report.**
4. **Migration order matters.** PR 2.5 не может идти раньше 48h после PR 2.4. Если попытка — fail с явным error.
5. **`legacy_*_id` columns are sacred during Sprint 2.** Не дропать до PR 2.5. Они — твой mapping для rollback.
6. **Никогда не запускать `DROP TABLE` без свежего backup в этой же сессии.**

---

## Final notes for owner

Этот документ — самодостаточный spec. После каждого PR агент возвращается за approval. Sprint 2 более опасный чем Sprint 1 (Sprint 1 был security-fixes, локальные изменения; Sprint 2 — central data migration).

Если в любой момент что-то идёт не так:
- `backups/pre-refactor-baseline-*.pgc` — fallback до начала всего рефактора
- `git tag pre-refactor-baseline` — fallback тег
- `backups/post-sprint-1-*.pgc` — fallback до Sprint 2
- `git tag post-sprint-1` — fallback тег

Удачи. 🏁

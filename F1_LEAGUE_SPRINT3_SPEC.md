# F1 League — Sprint 3 Spec: Auth Schema Cleanup

> **Версия:** 1.0
> **Дата:** 16 мая 2026
> **Pre-conditions:** Sprint 2 closed, post-sprint-2-20260516.pgc backup exists, git tag post-sprint-2 pushed
> **Стиль:** Compact (как Sprint 2 spec)
> **Целевая длительность:** 4-6 рабочих дней
> **Risk level:** MEDIUM (auth changes are sensitive, но schema migrations меньше Sprint 2)

---

## Цель спринта (one sentence)

Закрыть архитектурную дыру «фронт шлёт `web_user_id` в request body вместо использования JWT», заменить самописный HMAC на PyJWT с правильными claims, добавить logout-all через `token_version`.

## Контекст и обоснование

**Что не так сейчас:**

1. **`web_user_id` в request body** — несмотря на Bearer auth добавленный в Sprint 1, многие endpoints до сих пор принимают идентичность из body (`{ web_user_id: 5, ... }`) и не игнорируют её. Sprint 1 PR 1.1 закрыл часть, но не все.

2. **Самописный HMAC "JWT"** — `backend/services/jwt_auth.py` использует hex вместо base64url, нет валидации `alg`, нет стандартных claims (`iss`, `aud`, `iat`, `exp`, `nbf`, `sub`). Это **не настоящий JWT**. PyJWT уже в requirements (с Sprint 1 PR 1.5) — нужно мигрировать.

3. **Нет logout-all** — смена пароля или подозрение на компрометацию не инвалидирует существующие токены. 30-дневный токен живёт 30 дней независимо от любых действий юзера.

**Финальные решения (locked):**

```yaml
revocation_mechanism: token_version  # +1 INT column on users
pyjwt_rollout: strict_cutover         # no legacy fallback, no soft window
jwt_expiry: 14_days_static            # was 30 days
jwt_library: PyJWT (already in requirements)
breaking_change: yes                  # all current sessions invalidated on deploy
mitigation: 5 users (including owner) re-login once via Google/Steam
```

---

## Глобальные правила (как в Sprint 1/2)

1. **Stop-the-world** перед migration: `pg_dump` → `docker compose stop backend bot` → migration → restart → smoke test
2. **Approval gate** = STOP
3. **Pre-flight grep** перед каждым PR
4. **Tests passing** после каждого PR (61+ baseline)
5. **Backup checkpoint** между PR'ами если меняется auth flow

---

## PR 3.1: `web_user_id` Purge from Request Bodies

**Risk:** MEDIUM (touch много endpoints + frontend pages)
**Estimated:** 2-3 дня
**Dependencies:** None (independent from PR 3.2/3.3)

### Цель

Backend: удалить (или игнорировать) поля `web_user_id`, `requester_id`, `user_id` в request bodies везде где они есть. Идентичность извлекается только из JWT через `Depends(get_current_user)`.

Frontend: убрать эти поля из request bodies.

### Pre-flight grep

```bash
# Backend: найти все Pydantic schemas с web_user_id / requester_id
grep -rn "web_user_id\|requester_id" backend/routers/ backend/models/ --include="*.py"

# Backend: найти endpoints читающие user_id из body
grep -rn "body\.web_user_id\|body\.requester_id" backend/ --include="*.py"

# Frontend: найти все fetch'ы с web_user_id в body
grep -rn "web_user_id\|requester_id" frontend/ --include="*.ts" --include="*.tsx" | grep -v ".d.ts"
```

Записать в REFACTOR_LOG.md sub-section `## Sprint 3 / PR 3.1: pre-flight`:
- Список Pydantic схем с user-identity полями
- Список endpoints читающих identity из body
- Список frontend pages шлющих identity в body

### Pseudocode

**Backend Pattern 1: Удалить поле из Pydantic schema**

```python
# Before:
class CreateLobbyRequest(BaseModel):
    name: str
    description: str | None = None
    web_user_id: int  # ❌ identity from body

@router.post("/api/lobby")
async def create_lobby(
    body: CreateLobbyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lobby = Lobby(name=body.name, creator_user_id=user.id)

# After:
class CreateLobbyRequest(BaseModel):
    name: str
    description: str | None = None
    # web_user_id removed
```

**Backend Pattern 2: Endpoint с identity в URL — оставить URL, добавить auth check**

```python
@router.get("/api/web/me/{user_id}")
async def get_me(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # User может смотреть только свой profile, или system_admin любой
    if current_user.id != user_id and not current_user.is_system_admin:
        raise HTTPException(403, "Forbidden")
    ...

# Добавить новый endpoint без user_id в URL:
@router.get("/api/web/me")
async def get_me_self(current_user: User = Depends(get_current_user)):
    return current_user
```

**Frontend Pattern: убрать identity из body**

```typescript
// Before:
const res = await apiFetch("/api/lobby", {
  method: "POST",
  body: JSON.stringify({
    name: lobbyName,
    web_user_id: session.user.id,  // ❌ remove
  }),
});

// After:
const res = await apiFetch("/api/lobby", {
  method: "POST",
  body: JSON.stringify({ name: lobbyName }),
});
```

### Endpoints to update (high-level inventory)

| File | Endpoints | Action |
|------|-----------|--------|
| `routers/lobby.py` | POST /api/lobby, POST /api/lobby/{id}/seasons, POST /api/lobby/join-by-code | Remove web_user_id/requester_id from schemas |
| `routers/seasons.py` | POST /api/seasons/assistant | Remove player_id from schema |
| `routers/telemetry.py` | POST /api/telemetry/race-analysis/{id}/debrief | Remove web_user_id |
| `routers/web_auth.py` | POST /api/web/link-player | Remove user_id (use current_user.id) |
| `routers/practice.py` | GET /api/practice/sessions | Remove ?web_user_id query param |
| `routers/web_auth.py` | POST /api/web/launcher/auth | poll_id остаётся, identity из JWT |

### Frontend files to update

| File | Changes |
|------|---------|
| `frontend/app/me/page.tsx` | Удалить web_user_id из всех fetch'ей (~5 мест) |
| `frontend/app/lobby/[id]/page.tsx` | requester_id убрать |
| `frontend/app/lobby/join/page.tsx` | web_user_id убрать |
| `frontend/app/season/[id]/engineer/page.tsx` | web_user_id убрать |
| `frontend/app/practice/page.tsx` | web_user_id query param убрать |
| `frontend/components/CreateLobbyButton.tsx` | web_user_id убрать |

### Special case: launcher `/api/web/launcher/auth`

```python
class LauncherAuthRequest(BaseModel):
    poll_id: str
    # user_id removed

@router.post("/api/web/launcher/auth")
async def launcher_auth(
    body: LauncherAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _launcher_polls[body.poll_id] = current_user.id
```

### Acceptance criteria

1. ✅ `grep -rn "web_user_id\|requester_id" backend/routers/` — пусто (или только в comments)
2. ✅ `grep -rn "web_user_id\|requester_id" frontend/app/ frontend/components/` — пусто
3. ✅ Каждый изменённый endpoint имеет integration test проверяющий что подделанный user_id в body игнорируется
4. ✅ Все 61+ existing tests passing
5. ✅ Smoke test: create lobby, join lobby, AI engineer, practice — всё работает
6. ✅ Manual: DevTools Network на /me, "Создать лобби" — body не содержит web_user_id

### Tests (новые)

```python
# tests/test_identity_only_from_jwt.py

@pytest.mark.asyncio
async def test_create_lobby_ignores_user_id_in_body(client_with_auth):
    """POST /api/lobby with extra web_user_id in body → still creates as JWT user."""
    response = await client_with_auth.post(
        "/api/lobby",
        json={"name": "test", "web_user_id": 9999},  # forged
    )
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        lobby = await db.scalar(select(Lobby).where(Lobby.id == response.json()["id"]))
        assert lobby.creator_user_id != 9999

@pytest.mark.asyncio
async def test_practice_sessions_no_query_param(client_with_auth):
    """GET /api/practice/sessions БЕЗ ?web_user_id= → returns current user's sessions."""
    response = await client_with_auth.get("/api/practice/sessions")
    assert response.status_code == 200
```

### Rollback

```bash
git revert <PR 3.1 merge commit>
docker compose build backend frontend
docker compose restart backend frontend
```

Никаких миграций БД — pure code change.

### Approval gate

**ДА.** После merge — DevTools проверка что body не содержит identity, plus smoke test всех journeys.

---

## PR 3.2: PyJWT Migration + 14d Expiry + token_version

**Risk:** HIGH (auth core, invalidates all sessions)
**Estimated:** 1-2 дня
**Dependencies:** None strictly, но логично после 3.1

### Цель

Заменить самописный `jwt_auth.py` HMAC implementation на PyJWT. Добавить standard claims (`iss`, `aud`, `iat`, `exp`, `sub`, `token_version`). Срок жизни токена: 14 дней. Добавить колонку `users.token_version` для logout-all.

**Strict cutover:** legacy токены **не принимаются** после merge. Все юзеры (5 человек) перелогиниваются один раз.

### Pre-flight grep

```bash
cat backend/services/jwt_auth.py
grep -rn "jwt_auth\|create_token\|verify_token\|decode_token" backend/ --include="*.py"
grep "PyJWT\|pyjwt" backend/requirements.txt
```

Записать в REFACTOR_LOG.md:
- Текущий формат токена (hex? base64?)
- Места где token signing/verification вызывается
- PyJWT version

### Pseudocode

**Migration 0019: add token_version**

```python
"""0019_add_token_version_to_users.py"""

def upgrade():
    op.add_column(
        'users',
        sa.Column('token_version', sa.Integer, nullable=False, server_default='1'),
    )

def downgrade():
    op.drop_column('users', 'token_version')
```

**New `backend/services/jwt_auth.py`:**

```python
"""JWT signing and verification using PyJWT."""
import os
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException


JWT_SECRET = os.getenv("NEXTAUTH_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "f1league-backend"
JWT_AUDIENCE = "f1league-client"
JWT_EXPIRY_DAYS = 14


def create_token(user_id: int, token_version: int) -> str:
    if not JWT_SECRET:
        raise RuntimeError("NEXTAUTH_SECRET not configured")

    now = datetime.now(timezone.utc)
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRY_DAYS)).timestamp()),
        "tv": token_version,
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    if not JWT_SECRET:
        raise HTTPException(503, "JWT not configured")

    try:
        claims = pyjwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.InvalidIssuerError:
        raise HTTPException(401, "Invalid issuer")
    except pyjwt.InvalidAudienceError:
        raise HTTPException(401, "Invalid audience")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {e}")

    return claims
```

**Update `get_current_user`:**

```python
# backend/services/auth_dependencies.py

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    claims = verify_token(token)  # raises 401 if invalid

    user_id = int(claims["sub"])
    token_version_in_jwt = claims.get("tv")

    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(401, "User not found")

    if user.token_version != token_version_in_jwt:
        raise HTTPException(401, "Token revoked (logout-all triggered)")

    return user
```

**Token creation in `web_auth.py`:**

Все места где создаётся token (login, register, google_callback, steam_callback, launcher_login):

```python
# Before:
token = create_legacy_hex_token(user.id)

# After:
token = create_token(user_id=user.id, token_version=user.token_version)
```

### Strict cutover deployment

```bash
# 1. Backup
docker compose exec postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  > backups/pre-sprint3-pr32-$(date +%Y%m%d).pgc

# 2. Stop
docker compose stop backend bot

# 3. Apply migration
docker compose run --rm backend alembic upgrade head

# 4. Deploy new code
git pull
docker compose build backend
docker compose start backend bot

# 5. Smoke test:
#    - Old JWT (from browser session) → 401
#    - Login через Google → new JWT issued
#    - New JWT works
```

**User-facing impact:** все юзеры (5 человек) увидят login screen при следующем посещении. Один click "Continue with Google" → новый JWT.

### Acceptance criteria

1. ✅ Migration 0019 applied, `SELECT token_version FROM users LIMIT 1` returns 1
2. ✅ PyJWT используется для encoding/decoding (нет custom hex/base64)
3. ✅ JWT claims include `iss`, `aud`, `iat`, `exp`, `sub`, `tv`
4. ✅ JWT expiry = 14 дней (verify через decode: `exp - iat == 14 * 24 * 3600`)
5. ✅ Все 61+ tests passing
6. ✅ Старый legacy токен из браузера → 401 "Invalid token"
7. ✅ После login через Google → новый JWT работает
8. ✅ Frontend NextAuth callback правильно сохраняет new token в session
9. ✅ Launcher login flow работает

### Tests (новые)

```python
# tests/test_jwt_pyjwt.py

import jwt as pyjwt
from backend.services.jwt_auth import (
    create_token, verify_token, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_DAYS
)


def test_create_token_has_standard_claims():
    token = create_token(user_id=1, token_version=1)
    claims = pyjwt.decode(
        token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
        audience="f1league-client",
    )
    assert claims["sub"] == "1"
    assert claims["tv"] == 1
    assert claims["iss"] == "f1league-backend"
    assert claims["aud"] == "f1league-client"
    assert claims["exp"] - claims["iat"] == JWT_EXPIRY_DAYS * 24 * 3600


def test_verify_token_rejects_wrong_issuer():
    bad_token = pyjwt.encode(
        {"iss": "evil", "aud": "f1league-client", "sub": "1"},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        verify_token(bad_token)
    assert exc.value.status_code == 401


def test_verify_token_rejects_expired():
    import time
    expired = pyjwt.encode(
        {
            "iss": "f1league-backend", "aud": "f1league-client",
            "sub": "1", "tv": 1,
            "iat": int(time.time()) - 100,
            "exp": int(time.time()) - 50,
        },
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        verify_token(expired)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_stale_token_version(db_session):
    """JWT with old tv → 401 after user.token_version bump."""
    # ... fixture user with token_version=1
    # create JWT with tv=1
    # bump user.token_version to 2
    # verify_token + get_current_user → 401
```

### Rollback

⚠️ **Сложнее обычного.** После deploy все NextAuth sessions считают новый формат токена правильным.

```bash
docker compose stop backend bot
git revert <PR 3.2 merge commit>
docker compose run --rm backend alembic downgrade -1
docker compose build backend
docker compose start backend bot
# Все юзеры опять перелогиниваются — со старым форматом
```

Restore из backup не нужен — token_version column был DEFAULT 1, drop безопасный.

### Approval gate

**ДА.** Перед merge:
1. Backup `pre-sprint3-pr32-*.pgc` создан
2. Migration tested на staging
3. PyJWT tests passing
4. После deploy: твой login → новый JWT → /me работает

---

## PR 3.3: Logout-All Endpoint + UI

**Risk:** LOW (additive feature)
**Estimated:** 1 день
**Dependencies:** PR 3.2 must be merged (`token_version` column exists)

### Цель

Endpoint и UI кнопка для "разлогиниться на всех устройствах". Реализация: `UPDATE users SET token_version = token_version + 1 WHERE id = current_user.id`. После этого все JWT с старым `tv` будут отбрасываться `get_current_user`.

### Файлы

- `backend/routers/web_auth.py`: новый endpoint POST `/api/web/logout-all`
- `frontend/app/me/page.tsx`: новая кнопка "Выйти со всех устройств"
- `frontend/lib/api.ts`: типы (если нужны)

### Pseudocode

**Backend:**

```python
# backend/routers/web_auth.py

@router.post("/api/web/logout-all", status_code=204)
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invalidate all existing JWTs for current user by bumping token_version.
    Current session also invalidated — frontend must redirect to login.
    """
    current_user.token_version += 1
    await db.commit()
    return  # 204 No Content
```

**Frontend:**

```tsx
// frontend/app/me/page.tsx — добавить в settings section

import { signOut } from "next-auth/react";
import { apiFetch } from "@/lib/api-client";


const handleLogoutAll = async () => {
  const confirmed = confirm(
    "Это разлогинит вас на всех устройствах и потребует повторный вход. Продолжить?"
  );
  if (!confirmed) return;

  try {
    const res = await apiFetch("/api/web/logout-all", { method: "POST" });
    if (res.status === 204) {
      await signOut({ callbackUrl: "/login?message=logged_out_everywhere" });
    } else {
      alert("Не удалось выйти со всех устройств. Попробуйте ещё раз.");
    }
  } catch (e) {
    console.error(e);
    alert("Ошибка соединения");
  }
};


// Render section:
<section className="border-t pt-6">
  <h3 className="text-lg font-semibold">Безопасность</h3>
  <p className="text-sm text-gray-600 mt-2">
    Если вы потеряли доступ к устройству или думаете что ваш аккаунт скомпрометирован,
    разлогиньтесь со всех устройств.
  </p>
  <button
    onClick={handleLogoutAll}
    className="mt-3 px-4 py-2 bg-red-50 text-red-700 border border-red-300 rounded hover:bg-red-100"
  >
    Выйти со всех устройств
  </button>
</section>
```

### Acceptance criteria

1. ✅ POST `/api/web/logout-all` без auth → 401
2. ✅ POST `/api/web/logout-all` с valid auth → 204
3. ✅ После logout-all: тот же токен → 401 (token_version mismatch)
4. ✅ После logout-all: re-login → новый JWT с обновлённым tv → работает
5. ✅ Frontend кнопка: confirmation dialog, потом signOut + redirect to login
6. ✅ `/login?message=logged_out_everywhere` показывает информационный banner
7. ✅ Tests passing

### Tests (новые)

```python
# tests/test_logout_all.py

@pytest.mark.asyncio
async def test_logout_all_bumps_token_version(client_with_auth, db_session):
    user = ...  # current authenticated user
    old_version = user.token_version

    response = await client_with_auth.post("/api/web/logout-all")
    assert response.status_code == 204

    await db_session.refresh(user)
    assert user.token_version == old_version + 1


@pytest.mark.asyncio
async def test_old_token_rejected_after_logout_all(client_with_auth):
    """Existing JWT becomes invalid after logout-all."""
    response_before = await client_with_auth.get("/api/web/me")
    assert response_before.status_code == 200

    await client_with_auth.post("/api/web/logout-all")

    response_after = await client_with_auth.get("/api/web/me")
    assert response_after.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_requires_auth(client):
    response = await client.post("/api/web/logout-all")
    assert response.status_code == 401
```

### Rollback

```bash
git revert <PR 3.3 merge commit>
docker compose build backend frontend
docker compose restart backend frontend
```

`token_version` column остаётся (он из PR 3.2).

### Approval gate

**ДА** (lower stakes чем 3.2). Smoke test: нажать кнопку, увидеть login screen, перелогиниться.

---

## Sprint 3 Completion Checklist

- [ ] PR 3.1: `web_user_id`/`requester_id` purged from request bodies (backend + frontend)
- [ ] PR 3.2: PyJWT migration, 14d expiry, `token_version` column
  - Migration 0019 applied
  - All sessions invalidated (5 users re-login once)
- [ ] PR 3.3: logout-all endpoint + UI
- [ ] All 61+ tests passing
- [ ] Backup checkpoint: `backups/post-sprint-3-*.pgc`
- [ ] Git tag `post-sprint-3` + pushed
- [ ] REFACTOR_LOG.md: Sprint 3 closure section

---

## Notes for Agent

1. **PR 3.1 и PR 3.2 — независимы.** Можно начинать параллельно, но логически 3.1 первый.
2. **PR 3.2 — самый чувствительный.** Все юзеры теряют сессии. Coordinate timing — не в субботу вечером.
3. **`NEXTAUTH_SECRET` уже ротирован в Sprint 1.** PR 3.2 использует тот же secret для PyJWT signing.
4. **Frontend NextAuth integration:** `lib/auth.ts` создаёт session с `backendToken` field. После PR 3.2 этот field будет содержать new PyJWT-format token. Проверь что NextAuth callback читает `data.token` из backend response и кладёт в session (этот pattern не меняется).
5. **Лаунчер JWT:** хранится в `~/f1league_agent/launcher_config.json` как `auth_token`. После PR 3.2 невалиден. PR 1.0.5 уже добавил graceful 401 handling — лаунчер покажет login screen. Никаких extra changes в лаунчере не нужно.

---

## What's Next (Sprint 4 preview)

```
Sprint 4 → Lobby → League conceptual rename
  - Migration: rename table lobbies → leagues
  - Models: Lobby class → League class
  - Endpoints: /api/lobby → /api/leagues
  - Frontend: "лобби" → "лига" во всех strings
  - SeasonModerator class final removal
  - This is conceptual rename, no business logic change
```

Sprint 4 — намного проще Sprint 3. Никаких security implications.

---

## Final notes for owner

После Sprint 3 у тебя будет:

- ✅ Identity только через Bearer JWT (нет body-based identity)
- ✅ Standard JWT (PyJWT, можно verify любыми tools)
- ✅ 14-day expiry (вместо 30)
- ✅ token_version mechanism для emergency logout-all
- ✅ UI кнопка для self-service logout-all

Что **не** будет:
- ❌ Per-device session management (Sprint 6+ если захочется)
- ❌ Refresh tokens (выбрали static 14d)
- ❌ 2FA (не в roadmap)

Если когда-нибудь захочется per-device sessions — миграция от `token_version` к `jti` denylist возможна, но это отдельный спринт.

Удачи. 🔐

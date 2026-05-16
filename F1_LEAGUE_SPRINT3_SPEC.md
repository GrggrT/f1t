# F1 League — Sprint 3: Auth schema cleanup

**Goal:** finish the auth modernization that Sprint 1 (security wins) and Sprint 2 (identity unification) set up. After Sprint 3 the JWT layer is industry-standard (`PyJWT`, proper claims, revocable) and the API never accepts `web_user_id` from the client — Bearer JWT is the single source of identity.

**Scope:** backend `jwt_auth.py`, all routers that read `web_user_id` from request body/query, frontend callers, models (`User.token_version` column), bot launcher token refresh path.

**Out of scope:** UI redesign, anything not auth-related, Sprint 4 (League rename).

---

## What we have today

### JWT
- `backend/services/jwt_auth.py` — hand-rolled HMAC-SHA256. Encodes `{sub, exp, iat}` as base64url JSON. Single secret = `NEXTAUTH_SECRET`. Algorithm hardcoded as `HS256`. 30-day expiry. No `iss`, no `aud`, no `kid`, no `nbf`, no `jti`. Decode trusts `alg` from header but only computes HS256 — accidentally safe but not enforced.
- `decode_token` falls open on invalid base64 / missing fields via broad `except Exception`. Returns `None` correctly but loses observability.
- No revocation. A leaked token is valid for ~30 days unless `NEXTAUTH_SECRET` is rotated (which invalidates ALL tokens — also done in PR 1.4).
- `auth_dependencies._resolve_user_from_token` looks up `User` by `id` first, then falls back to `legacy_web_user_id`. The fallback was added in PR 2.5 so Sprint 1/2 launcher tokens (which still have legacy IDs in `sub`) keep working.

### `web_user_id` on the API surface

**Backend live code (NOT migrations):**

| File | Where | Today's behavior |
|------|-------|-----------------|
| `routers/lobby.py:108,209` | `GET /api/lobby?web_user_id=...` and `GET /api/lobby/{id}?web_user_id=...` query param | Optional unauthenticated mode for anonymous viewers; if not set we fall back to Bearer user. |
| `routers/lobby.py:345` | `list_members` response — emits `"web_user_id"` alias on each row | Back-compat for old frontend that reads `member.web_user_id`. |
| `routers/telemetry.py:803-808` | `POST /api/telemetry/race-analysis/{race_id}/debrief` body — accepts `web_user_id` OR `user_id` | Used by launcher debrief flow. Required field — endpoint 400s without it. |
| `routers/users.py:40` | `GET /api/users/by_telegram/{tg_id}` response — emits `legacy_web_user_id` | Diagnostic field for bot/debug. |
| `services/auth_dependencies.py:25` | `User.legacy_web_user_id` fallback lookup | Keeps pre-PR2.5 JWTs working. |

**Frontend (sends `web_user_id` to backend):**

| File | Endpoint |
|------|----------|
| `app/me/page.tsx:126,191,196` | `GET /api/lobby?web_user_id=`, `POST /api/lobby` body, refresh |
| `app/workspace/page.tsx:81` | `GET /api/lobby?web_user_id=` |
| `app/lobby/[id]/page.tsx:29,53,238` | `GET /api/lobby/{id}?web_user_id=`, read `member.web_user_id` |
| `app/lobby/join/page.tsx:35` | `POST /api/lobby/join-by-code` body |
| `app/practice/page.tsx:56` | `GET /api/practice/sessions?web_user_id=` (currently ignored by backend) |
| `app/season/[id]/engineer/page.tsx:58,92` | engineer context fetch + ask body |
| `app/race/[id]/analysis/page.tsx:169` | debrief body |
| `components/SeasonNav.tsx:39` | lobby context fetch |
| `lib/api.ts:117,301` | type declarations |

Every one of these can use the JWT subject instead. None of these endpoints today validate that the supplied `web_user_id` matches the JWT — that's an authorization bug too (someone could pass a different user's id and read their lobby state). Closing this is a small security win.

---

## PRs

### PR 3.1 — `User.token_version` + remove `web_user_id` from API surface

**Risk:** LOW — additive column, no data migration, code-only changes.

#### Migration `0018_user_token_version.py`

```python
def upgrade():
    op.add_column("users", sa.Column(
        "token_version", sa.Integer(), nullable=False, server_default="0"
    ))
```

(Server default 0 means existing tokens stay valid because they have no `tv` claim → backend reads as 0 → match.)

#### Backend

- `auth_dependencies.get_current_user`: derive everything from JWT. Pass User through Depends to every router that previously read `web_user_id` from request.
- `routers/lobby.py`:
  - `list_lobbies(web_user_id=None, user_optional=...)` → drop the param, use `user.id` if present.
  - `get_lobby(lobby_id, web_user_id=None, ...)` → same; if anonymous viewer needs partial data, switch to a separate `GET /api/lobby/{id}/public` route.
  - `list_members` response: drop the `"web_user_id"` alias key; keep `"user_id"`. Update frontend to read `member.user_id`.
- `routers/telemetry.py`: debrief endpoint stops reading `web_user_id` from body; derive from JWT. The launcher already sends Bearer.
- `routers/users.py`: drop `legacy_web_user_id` from response (still in DB as audit; just not exposed).

#### Frontend

- Replace every `?web_user_id=X` query string with calls that rely on the implicit Bearer token (already attached by `apiFetch`).
- Replace `body: { web_user_id: X }` with no field — backend derives from JWT.
- `member.web_user_id` → `member.user_id`.
- `lib/api.ts`: drop `web_user_id` from types.

#### Tests
- New `tests/test_no_web_user_id_in_payloads.py`: assert response shapes don't contain `web_user_id` for known endpoints (lobby members, /api/users/by_telegram).
- New `tests/test_lobby_authz_uses_jwt.py`: pass a Bearer token for user A but query `?web_user_id=B`. The query param should be ignored and we should get user A's view, not user B's.
- Existing 61 tests must stay green.

#### Acceptance
- [ ] `grep -rn "web_user_id" backend/ --include="*.py" | grep -v migrations | grep -v legacy_web_user_id` → 0 hits
- [ ] `grep -rn "web_user_id" frontend/` → 0 hits
- [ ] All 61 prior tests + 2 new tests pass
- [ ] Smoke in Chrome: lobby create / join / members / season engineer still work

---

### PR 3.2 — PyJWT migration (HS256 → still HS256, but proper library)

**Risk:** MEDIUM — touches every token mint/verify path. Backwards compat needed during rollout.

#### Why PyJWT
- Hand-rolled HMAC has subtle bugs (algorithm confusion via alg=none, base64 padding, exp type coercion). PyJWT is battle-tested.
- Adds standard claims for free: `iss`, `aud`, `nbf`, `jti`.
- Easy to add `tv` (token version) as a private claim.

#### Token shape (post-3.2)

```json
{
  "iss": "f1league",
  "aud": "f1league-launcher" | "f1league-web",
  "sub": "42",
  "exp": 1734567890,
  "iat": 1731975890,
  "nbf": 1731975890,
  "jti": "<uuid4>",
  "tv": 0
}
```

#### Implementation

`backend/services/jwt_auth.py`:

```python
import jwt  # PyJWT
from uuid import uuid4

ISSUER = "f1league"
ALGORITHM = "HS256"

def create_token(user_id: int, *, audience: str, token_version: int = 0, days: int = 30) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": audience,
            "sub": str(user_id),
            "exp": now + days * 86400,
            "iat": now,
            "nbf": now,
            "jti": str(uuid4()),
            "tv": token_version,
        },
        get_jwt_secret(),
        algorithm=ALGORITHM,
    )

def decode_token(token: str, *, audience: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[ALGORITHM],  # strict allow-list — no alg=none
            audience=audience,
            issuer=ISSUER,
        )
    except jwt.InvalidTokenError:
        return None
```

#### Back-compat rollout

The token-decode path needs to accept BOTH old hand-rolled tokens AND new PyJWT tokens until the 30-day expiry window has rolled forward.

Approach: try PyJWT first; on failure fall back to the old `decode_token` from current code (renamed to `_decode_legacy_token`). After 30 days (one max expiry cycle) we delete `_decode_legacy_token` in PR 3.4.

`auth_dependencies._resolve_user_from_token` now also takes `audience` arg — launcher Depends uses `"f1league-launcher"`, web NextAuth uses `"f1league-web"`. (NextAuth doesn't mint these directly — backend mints, NextAuth carries.)

#### `tv` claim check

When `_resolve_user_from_token` finds the User, compare `payload["tv"]` vs `user.token_version`. If mismatch → reject. This is the revocation mechanism (PR 3.3 wires the increment side).

#### Tests
- `tests/test_jwt_pyjwt.py`:
  - Algorithm confusion: token with `alg=none` rejected.
  - Wrong audience rejected.
  - Wrong issuer rejected.
  - Expired token rejected.
  - `nbf` in future rejected.
  - Legacy hand-rolled token still accepted (during rollout).
  - `tv` mismatch rejected.

#### Acceptance
- [ ] All previous tests + 7 new pass
- [ ] `requirements.txt` has `PyJWT>=2.8.0` (replaces nothing; just adds)
- [ ] No regression on launcher login / debrief / WS auth

---

### PR 3.3 — Token revocation: `POST /api/web/logout-all`

**Risk:** LOW — feature add.

#### Endpoint

```python
@router.post("/logout-all")
async def logout_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.token_version = (user.token_version or 0) + 1
    await db.commit()
    return {"ok": True, "new_token_version": user.token_version}
```

After this call, every token previously minted for that user fails the `tv` check at next request. User has to re-login (Google OAuth re-flow / launcher email+password re-login) to get a fresh token with the new `tv`.

#### Frontend

- `/me` → add button "Выйти со всех устройств" (next to existing "Выйти"). Click → POST `/api/web/logout-all` → on success, also call `signOut()` to clear the local NextAuth session.

#### Tests
- `tests/test_logout_all.py`:
  - Mint token A, call `/logout-all`, then call any protected endpoint with token A → 401.
  - Mint token B AFTER `/logout-all` → works.

#### Acceptance
- [ ] Endpoint works end-to-end (Chrome smoke)
- [ ] Old token gets 401 after logout-all
- [ ] Two new tests pass

---

### PR 3.4 — Drop legacy hand-rolled JWT path

**Risk:** LOW — code-only cleanup; precondition is "30 days since PR 3.2 ship".

- Remove `_decode_legacy_token` and the try/except fallback in `decode_token`.
- Remove `User.legacy_web_user_id` fallback in `_resolve_user_from_token` (alongside cosmetic migration 0019 if we drop the column).
- Optional migration `0019_drop_users_legacy_ids.py` — finally drops `users.legacy_web_user_id` + `users.legacy_player_id`. Spec'd in Sprint 2 closure as the post-stability cosmetic.

#### Acceptance
- [ ] Tests pass
- [ ] No more `legacy_*_id` references in live application code

---

## Decision questions for you (need answers before I start PR 3.2)

### Q1 — Token revocation strategy

**Option A — `token_version` on User row (one int):** Simple. `/logout-all` increments. Every token check costs +1 DB column read (already loaded with User). Per-token revocation NOT supported — only "all my tokens". I'd pick this.

**Option B — JWT denylist (jti in Redis/DB with TTL=token-exp):** Per-token revocation possible. Costs +1 lookup per request OR shared cache. Adds Redis dependency or grows users table. Overkill for a 5-user league.

**My recommendation: A.** League is 5 people; per-device revocation isn't worth the dependency.

### Q2 — Backwards compat window for PyJWT

**Option A — strict cutover (PR 3.2 ships, all old tokens invalidated immediately):** Forces every user to re-login once. Cleanest code (no fallback path). For 5-user league this is fine.

**Option B — 30-day soft window (try PyJWT first, fall back to old HMAC):** Current users keep working until natural expiry. Code carries dual-decode for 30 days. PR 3.4 cleans it up.

**My recommendation: B for safety.** The "5-user league" argument cuts both ways — those 5 people don't want to wake up to a forced re-login if something else breaks at the same time. The fallback path is ~10 lines.

### Q3 — JWT expiry policy

**Current:** 30 days, no refresh, no sliding window.

**Option A — keep 30 days, no refresh:** What we have. Simple. After 30 days you re-login.

**Option B — sliding 30 days:** Every authenticated request gets a fresh token in the response with `exp = now + 30d`. Frontend swaps its stored token. User effectively never logs out unless 30 days of inactivity.

**Option C — short access (1h) + refresh (30d):** Industry standard. Two tokens. Refresh token rotation. Twice the moving parts.

**My recommendation: A.** League is closed group; long expiry is the feature, not the bug. If we want stricter, Option B is cheap. Option C is enterprise-grade overkill for this scope.

---

## Sprint 3 acceptance (overall)

- [ ] 4 PRs landed: 3.1 (web_user_id purge), 3.2 (PyJWT), 3.3 (logout-all), 3.4 (legacy cleanup, after 30 days)
- [ ] Backend: `grep -rn "web_user_id\|hmac.new" backend/ --include="*.py" | grep -v migrations` → 0 hits (legacy_web_user_id stays only in models.py + migration files)
- [ ] All existing 61 tests + ~12 new tests pass
- [ ] Production stable for 7 days after PR 3.3
- [ ] One-line `POST /api/web/logout-all` documented in CLAUDE.md

## What's next (Sprint 4 preview)

```
Sprint 4 → Lobby → League rename
  - rename `lobbies` table → `leagues`
  - rename `Lobby` ORM → `League`
  - frontend: всё "лобби" → "лига" в copy
  - models cleanup: SeasonModerator class fully removed (table уже dropped в Sprint 2)
  - URL: /lobby/[id] → /league/[id] with redirect
```

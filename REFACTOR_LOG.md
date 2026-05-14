# Refactor Log

## Sprint -0.5.1: Discovery (date: 2026-05-14)

### 1. Tests infrastructure
- Existing test files: 16+ files under `tests/` — including `test_backend_auth_integration.py`, `test_backend_lobby_integration.py`, `test_backend_telemetry_integration.py`, `test_backend_contracts_integration.py`, `test_backend_contract_smoke.py`, `test_backend_race_submit_integration.py`, `test_backend_ws_and_concurrency_integration.py`, `test_backend_external_delivery_integration.py`, `test_race_submit_idempotency.py`, `test_packet_replay_harness.py`, `test_upload_cache.py`, `test_postmortem_tooling.py`, `test_telemetry_pipeline_integrity.py`, `test_agent_runtime_lifecycle.py`, `test_launcher_delivery_recovery.py`, `test_personal_session_sync.py`. Support modules: `backend_contract_harness.py`, `backend_integration_harness.py`, `backend_integration_support.py`, `live_validation_harness.py`. `tests/__init__.py` exists. No frontend `*.test.ts` files found (only inside `node_modules/`).
- pytest configured: **no** — no `pytest.ini`, no `pyproject.toml`, no `setup.cfg`, no root `conftest.py`. Tests presumably rely on default pytest discovery and run from outside Docker.
- pytest in requirements: **no** — `backend/requirements.txt` contains 12 packages (fastapi/uvicorn/sqlalchemy/asyncpg/psycopg2-binary/alembic/pydantic/python-dotenv/pillow/httpx/bcrypt/PyJWT) and no `pytest`/`pytest-asyncio`. No `requirements-dev.txt`.
- 🔴 Mismatch with plan: **yes** — substantial test suite exists but tooling (pytest, pytest-asyncio, fixtures config) is not declared anywhere in repo. CI/local runs depend on whatever the developer has installed globally. Any plan step that assumes `docker compose run backend pytest` will fail out-of-the-box.

### 2. Postgres env vars
- POSTGRES_USER: `f1league`
- POSTGRES_DB: `f1league`
- POSTGRES_PASSWORD: `<set>`
- 🔴 Mismatch (plan assumed f1league/f1league): **no** — matches plan.

### 3. get_db import path
- Real path: `from backend.db.base import get_db`
- File where defined: `backend/db/base.py:73`
- Engine, `AsyncSessionLocal`, `DATABASE_URL`, `Base`, `configure_database`, `dispose_database_engines` also live in the same module.
- 🔴 Mismatch (plan assumed `backend.services.db`): **yes** — there is no `backend/services/db.py`. All DB session/engine plumbing is in `backend/db/base.py`. Plan must be updated everywhere it references `backend.services.db`.

### 4. Backend Dockerfile
- Base image: `python:3.11-slim`
- curl available: **no** — the Dockerfile has a single `RUN pip install ...` and no `apt-get install` line. `python:3.11-slim` does not ship `curl` by default.
- Recommendation for healthcheck: use `python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health', timeout=3); sys.exit(0)"` (or equivalent `httpx`/`requests`) — avoids adding `curl` and a new apt layer. If curl is preferred, add `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*` before the pip step.

### 5. Models & Base
- `__init__.py` status: **empty** (0 bytes, no exports).
- `Base` defined in: `backend/db/base.py:32` (modern `class Base(DeclarativeBase): pass` — SQLAlchemy 2.0 style, **not** `declarative_base()`).
- Correct import: `from backend.db.base import Base` (this is what `backend/models/models.py:9` already does).
- All ORM classes live in a single module: `backend/models/models.py`.
- 🔴 Mismatch with plan: **partial** — if the plan assumed `Base` is exported from `backend/models/__init__.py` or sits alongside the models, that's wrong. If the plan also assumed `declarative_base()` (legacy 1.x), Alembic env or migrations referencing `Base.metadata` must use the 2.0-style class. Otherwise correct.

### 6. Agent token storage
- Method: **mixed — env var + external config file**.
  - `AGENT_SECRET_TOKEN` (agent → backend ingest auth): read from env var in `agent/config.py:7` via `os.getenv("AGENT_SECRET_TOKEN", "")`. **Not hardcoded in the .exe.** No default value bundled. Used by `agent/ws_client.py:221`, `agent/uploader.py:115-117`, `agent/telemetry_delivery.py:196-198` as `X-Agent-Token` header.
  - `INVITE_TOKEN` (one-time onboarding): same pattern — env var `F1_INVITE_TOKEN`, no default.
  - User JWT (web login from launcher): persisted to `~/f1league_agent/launcher_config.json` under key `auth_token` (`agent/launcher.py:997-1003`, `CONFIG_FILE = Path.home() / "f1league_agent" / "launcher_config.json"` at line 37-39). Loaded at startup (`agent/launcher.py:282`) and re-exported as `F1_AUTH_TOKEN` env at line 1533.
- Config file path (if external): `~/f1league_agent/launcher_config.json` (per-user JSON, plaintext). Also stores `server_url`, `frontend_url`, `ws_url`, `season_id`, `udp_port`, `agent_mode`, overlay prefs, `user_id`.
- `build_agent_exe.bat` behavior: `scripts/build_agent_exe.bat` is a 9-line trampoline that `pushd`s to repo root and calls `agent/build_launcher.bat`. The real build (`agent/build_launcher.bat`): runs `pyinstaller F1LeagueAgent.spec` → produces `agent/dist/F1LeagueAgent.exe`, copies it to `backend/static/F1LeagueAgent.exe`, then optionally runs `ISCC.exe installer.iss` → `installer_output/Setup_F1LeagueAgent.exe` (also copied to `backend/static/`). **The build does NOT bake any secret/token into the EXE** — PyInstaller packs source only; tokens are pulled from env/config at runtime.
- 🔴 PR 1.2 strategy needed: **edit_config_file** (for JWT) + **reconfigure_via_ui** (for AGENT_SECRET_TOKEN if shown in UI; otherwise via env). EXE rebuild is **not** required for rotation. Plan steps that assumed token is baked into the EXE are wrong and should be removed/simplified.

### 7. Agent 401 handling
- Detected: **partial**.
- Behavior:
  - The launcher's own `login()` method explicitly handles 401: `agent/launcher.py:1063-1064` returns `{"error": "Неверный email или пароль."}` — graceful for the login form path.
  - `auto_login()` (`agent/launcher.py:1073-1082`): does NOT inspect status_code; on **any** exception (including HTTP errors from `_get`) it calls `_clear_session()` and returns `None`. So an expired token silently logs the user out at next launcher start — the user must re-enter credentials but the app does not crash.
  - All other agent paths (`uploader.py`, `telemetry_delivery.py`, `ws_client.py`, `personal_session_sync.py`) use `AGENT_SECRET_TOKEN` (not user JWT) and check only `response.status_code != 200` / `>= 400`. They surface generic `HTTP {code}` messages, retry via `RETRY_DELAYS = [1, 5, 30]`, and **have no special 401 path** — a rotated `AGENT_SECRET_TOKEN` will produce a retry loop with `HTTP 401` errors and no relogin/reconfigure prompt to the user.
- 🔴 Needs fix before PR 1.4 (secret rotation): **yes** — without a 401-specific handler in `uploader.py` / `telemetry_delivery.py` / `ws_client.py`, an `AGENT_SECRET_TOKEN` rotation will cause all field agents to silently fail uploads (only visible as "HTTP 401" toast). At minimum we need: (a) 401 detection in the three delivery modules, (b) clear UI surfacing in `launcher_ui` ("Agent token rejected — please reconfigure"), (c) ability to enter new token via UI without rebuilding EXE.

### 8. Frontend NextAuth
- `account.id_token` currently used: **no** — neither `signIn` nor `jwt` callback reads `account.id_token`. The `signIn` callback only uses `account.providerAccountId` (Google sub) to send to `/api/web/google`; the `jwt` callback only consumes `user` (and never `account`); `session` only forwards token fields.
- Current callbacks structure (full file, `frontend/lib/auth.ts`):
  ```ts
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google") {
        const r = await fetch(`${API}/api/web/google`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            google_id: account.providerAccountId,
            email:     user.email,
            name:      user.name,
            picture:   user.image,
          }),
        })
        if (r.ok) {
          const data = await r.json()
          user.id                     = String(data.id)
          ;(user as any).player_id    = data.player_id ?? null
          ;(user as any).backendToken = data.token ?? null
        }
      }
      return true
    },
    async jwt({ token, user }) {
      if (user) {
        token.userId       = user.id
        token.playerId     = (user as any).player_id ?? null
        token.backendToken = (user as any).backendToken ?? null
      }
      return token
    },
    async session({ session, token }) {
      session.user.id           = token.userId as string
      session.user.playerId     = (token.playerId as number | null) ?? null
      session.user.backendToken = (token.backendToken as string | null) ?? null
      return session
    },
  }
  ```
- Where to inject `id_token` verification: in the **`signIn` callback** (`frontend/lib/auth.ts:62-84`) — `account.id_token` is available there only on first sign-in. Forward it as a new field in the POST body to `/api/web/google` so the backend can verify Google signature/audience/expiry instead of trusting `providerAccountId` blindly. Alternatively extend the `jwt` callback signature to `async jwt({ token, user, account })` and stash `account.id_token` for backend verification on each refresh.
- 🔴 PR 1.5 complexity assessment: **moderate** — backend needs a Google JWKS verifier (new dep, e.g. `google-auth` or manual JWKS fetch + cache), plus payload shape change for `/api/web/google`. Frontend change itself is ~10 lines but coupled with backend changes and migration of existing sessions.

### 9. Groq integration sites
- Found **7** sites (expected 6).
- Files:
  1. `backend/app_factory.py` (line 155-159)
  2. `backend/routers/analytics.py` (lines 480, 482, 486, 489)
  3. `backend/routers/lobby.py` (lines 36-38, 615, 616, 649)
  4. `backend/routers/seasons.py` (lines 18-20, 132, 133, 145)
  5. `backend/routers/telemetry.py` (lines 802-806)
  6. `backend/services/contract_generator.py` (lines 18, 22, 26)
  7. `backend/services/ai_engineer.py` (lines 18, 22, 26, 122)
- 🔴 Mismatch: **yes** — one extra site versus plan's `6`. Each site duplicates the same boilerplate (`GROQ_API_KEY = os.getenv(...)`, `GROQ_URL`, `GROQ_MODEL`, fallback message). Strong candidate for consolidation into a single `backend/services/groq_client.py` helper.

---

## Summary of 🔴 mismatches
- **Task 1**: pytest test suite exists (16+ files) but pytest is not in `backend/requirements.txt` and no config file (`pytest.ini`/`pyproject.toml`/`conftest.py`) exists. Plan steps that assume in-Docker pytest will fail.
- **Task 3**: `get_db` lives in `backend/db/base.py`, **not** `backend.services.db`. Plan must be globally updated.
- **Task 5** (partial): `Base` is the new SQLAlchemy 2.0 `DeclarativeBase` subclass in `backend/db/base.py`, not legacy `declarative_base()`. `backend/models/__init__.py` is empty (no re-exports).
- **Task 6**: Token is **not** hardcoded in the EXE. PR 1.2 should target the per-user config file (`~/f1league_agent/launcher_config.json`) and env var, not an EXE rebuild.
- **Task 7**: No 401 handling exists in the three delivery modules (`uploader.py`, `telemetry_delivery.py`, `ws_client.py`). PR 1.4 secret rotation will brick agents silently without fixing this first.
- **Task 9**: 7 Groq call sites, not 6. Plan ETA for the refactor should account for the 7th file (`backend/services/contract_generator.py` was likely missed in discovery).

## Recommendations for plan v3
1. **Add a Sprint -0.5.2 (tooling)** before any test-touching sprint: introduce `requirements-dev.txt` with `pytest`, `pytest-asyncio`, `httpx`-based async test client; add a minimal `pyproject.toml` or `pytest.ini` with `asyncio_mode=auto` and `testpaths=tests`; add a `conftest.py` with the `AsyncSessionLocal` override and `TestClient` fixtures. Without this, "run tests" is undefined.
2. **Replace every `backend.services.db` reference in the plan with `backend.db.base`.** Audit migrations and any plan-introduced module imports.
3. **Healthcheck**: don't add curl. Use `python -c "..."` inline — avoids touching the Dockerfile beyond a single `HEALTHCHECK` line.
4. **Reorder PR 1.2 and PR 1.4**: ship 401 handling in agent (`uploader.py` / `telemetry_delivery.py` / `ws_client.py`) **before** the secret rotation. Add UI affordance in `launcher_ui` for reconfiguring `AGENT_SECRET_TOKEN` without rebuilding the EXE. Drop any "rebuild EXE for new token" step.
5. **Consolidate Groq calls** into `backend/services/groq_client.py` (single `async def ask_groq(prompt, *, model=None, system=None) -> str` + shared "key not set" message). Refactor all 7 sites in a separate PR — keeps the auth/secrets sprint focused.
6. **PR 1.5 (NextAuth id_token verification)**: confirm whether backend should re-verify the Google id_token on every session refresh or only on first sign-in. The current `jwt` callback does **not** receive `account` beyond first call, so a per-refresh model would require Google's userinfo endpoint or storing the id_token in the JWT. Pick one approach and document it before implementation.
7. **Models module**: leave `backend/models/__init__.py` empty (current state is fine) **or** explicitly re-export the most-used classes there in a separate cosmetic PR — but don't bundle that with auth/DB work.

---

## 2026-05-14: Baseline backup created (PR 0.3)

- **Dump:** `backups/pre-refactor-baseline-20260514.pgc` (75 KB, PostgreSQL custom format v1.15)
- **Git tag:** `pre-refactor-baseline` → commit `c027cdf` on `main`
- **Remote:** [github.com/GrggrT/f1t](https://github.com/GrggrT/f1t) (first push: `main` + tag)
- **External copy:** ⏳ to be performed manually by the operator (OneDrive / USB / external HDD)
- **Restore protocol:** validated end-to-end via `staging_up.sh` during PR 0.1 acceptance (staging postgres restored from dump → backend HTTP 200 on `/api/players` → row count matched prod)
- **GitHub Secret Scanning:** flagged real secrets in `.claude/CLAUDE.md:23` (GOOGLE_CLIENT_SECRET) — initial push rejected. Scrubbed all `*_SECRET`, `*_TOKEN`, `*_KEY`, `POSTGRES_PASSWORD` values to `<set in .env>` placeholders before successful push. The actual secrets are still considered leaked (visible to the operator and AI sessions); rotation is on the books for PR 1.4.

## Sprint -0.5 + Sprint 0 status

- [x] PR -0.5.1: discovery
- [x] PR -0.5.2: pytest infrastructure
- [x] PR -0.5.3: ephemeral staging
- [x] PR 0.1: automated daily backup
- [x] PR 0.2: backend healthcheck + log rotation
- [x] PR 0.3: baseline backup + git tag + remote setup

---

## Sprint 0.6.1: Test collection triage (date: 2026-05-14)

Command: `./scripts/run_tests.sh --collect-only --tb=short`
Image: `backend-test` built with `INCLUDE_DEV=true` (pytest 8.x + pytest-asyncio + pytest-timeout + pytest-mock).
Result: **21 tests collected across 9 modules, 7 collection errors.**

### Collected modules (no import errors)

| Module | Tests | Style |
|--------|------:|-------|
| `tests/test_backend_auth_integration.py` | 2 | UnitTestCase (`BackendAuthIntegrationTests`) |
| `tests/test_backend_contract_smoke.py` | 1 | UnitTestCase (`BackendContractSmokeTests`) |
| `tests/test_backend_contracts_integration.py` | 2 | UnitTestCase (`BackendContractsIntegrationTests`) |
| `tests/test_backend_external_delivery_integration.py` | 2 | UnitTestCase (`BackendExternalDeliveryIntegrationTests`) |
| `tests/test_backend_lobby_integration.py` | 2 | UnitTestCase (`BackendLobbyIntegrationTests`) |
| `tests/test_backend_race_submit_integration.py` | 3 | UnitTestCase (`BackendRaceSubmitIntegrationTests`) |
| `tests/test_backend_telemetry_integration.py` | 2 | UnitTestCase (`BackendTelemetryIntegrationTests`) |
| `tests/test_backend_ws_and_concurrency_integration.py` | 4 | UnitTestCase (`BackendWsAndConcurrencyIntegrationTests`) |
| `tests/test_healthcheck.py` | 1 | Coroutine (async, added in PR 0.2) |
| `tests/test_race_submit_idempotency.py` | 2 | UnitTestCase (`RaceSubmitIdempotencyTests`) |

Total: 10 modules → **21 collectible tests**. Most are `unittest.TestCase` style; only `test_healthcheck.py` (new) uses async pytest-style.

### Collection errors (file → first ImportError line)

| File | Cause |
|------|-------|
| `tests/test_agent_runtime_lifecycle.py` | `from agent.main import F1Agent` → `ModuleNotFoundError: No module named 'agent'` |
| `tests/test_launcher_delivery_recovery.py` | `from agent import telemetry_delivery, uploader` → `ModuleNotFoundError: No module named 'agent'` |
| `tests/test_packet_replay_harness.py` | `import f1.packets as f1_packets` → `ModuleNotFoundError: No module named 'f1'` |
| `tests/test_personal_session_sync.py` | `from agent.personal_session_sync import _build_laps, _select_vehicle_index, sync_personal_session` → `ModuleNotFoundError: No module named 'agent'` |
| `tests/test_postmortem_tooling.py` | `from agent.postmortem import build_postmortem_report, quarantine_orphaned_telemetry` → `ModuleNotFoundError: No module named 'agent'` |
| `tests/test_telemetry_pipeline_integrity.py` | `from agent import local_cache, telemetry_delivery, uploader` → `ModuleNotFoundError: No module named 'agent'` |
| `tests/test_upload_cache.py` | `from agent import local_cache, uploader` → `ModuleNotFoundError: No module named 'agent'` |

### Root cause (factual only — no fix attempted per PR 0.6.1 scope)

- 6 of 7 errors → missing `agent` package on the Python path inside the `backend-test` image. The Dockerfile (`backend/Dockerfile`) only copies `backend/` and `shared/` into `/app/`; `agent/` is intentionally not in the backend container (agent runs on a separate Windows machine).
- 1 of 7 errors → missing `f1` package. `f1` is not present anywhere in the repo (verified via `find . -type d -name "f1"` — no matches outside node_modules) and is not in `backend/requirements.txt` nor `backend/requirements-dev.txt`. Likely a third-party PyPI package (`f1-2021`, `f1-2024`, `f1-telemetry`, or similar) that someone expected as a dev dependency but never declared. No additional grep evidence as to which one.

### Triage decisions deferred to PR 0.6.2/0.6.3

No file modifications in this PR per acceptance criterion 3. Categorization (fix / quarantine / delete) happens in PR 0.6.2.

Initial read of options for PR 0.6.2 — for the council, not a decision:
- **Agent-coupled tests (6 files):** these test agent runtime / delivery / postmortem behavior. Options: (a) add `COPY agent/ ./agent/` to `backend/Dockerfile` only when `INCLUDE_DEV=true`; (b) create a separate `agent-test` compose service; (c) move tests to `tests/agent/` and exclude from backend-test image. Option (a) is the lightest touch but couples agent code to backend image — minor cost given single-user setup.
- **`f1` package test (1 file):** without identifying the intended package, either declare in `requirements-dev.txt` once identified, or quarantine/delete if `test_packet_replay_harness.py` is obsolete tooling.

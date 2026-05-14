# F1 League System — Memory / Progress Log

> Файл для отслеживания прогресса разработки. Обновляется по ходу работы.

---

## Проект

**F1 LEAGUE SYSTEM** — автоматическая лига для F1 25 (EA). 4-5 друзей играют на PC (Steam), система автоматически собирает результаты через UDP-телеметрию, считает очки, генерирует карточки, постит в Telegram.

## Архитектура (FACEIT-model)

- **Local Agent** (Python + pystray → PyInstaller .exe) — слушает UDP :20777, парсит f1-packets, отправляет на сервер
- **Backend** (FastAPI + PostgreSQL) — REST API, WebSocket hub, очки, PNG-карточки, AI-инженер
- **Frontend** (Next.js 14 + Tailwind) — season-first hybrid shell: Home, Seasons, Races, Players, Records, Launcher, Workspace, Season/Race detail, Telemetry, Analysis, Admin
- **Telegram Bot** (aiogram 3) — авто-пост результатов, команды, ачивки
- **Infra** — Docker Compose, GCP

## Ключевые документы

| Файл | Описание |
|------|----------|
| `docs/f1_25_udp_api_research.md` | Исследование UDP API F1 25 — все 14 пакетов, библиотеки, примеры |
| `docs/F1_LEAGUE_SYSTEM_SPEC_v4.md` | Проектная спецификация v4 — архитектура, DB schema, фазы, чеклисты |

## Фазы разработки

| Фаза | Статус | Описание |
|------|--------|----------|
| Phase 1 | НЕ НАЧАТА | Core: Agent + Backend + Frontend + Bot + DB |
| Phase 2 | — | Achievements, Fun Stats, Стюарды, Live Race |
| Phase 3 | — | Контракты, AI Race Engineer (Groq) |
| Phase 4 | — | Heatmaps, Telemetry, Comparison Tool |
| Phase 5 | — | AI Журналист, Новости лобби, Интервью |

## Tech Stack

- Python 3.11, f1-packets, pystray, PyInstaller
- FastAPI, SQLAlchemy async, Pydantic
- PostgreSQL 16, Alembic
- Next.js 14, Tailwind, WebSocket
- aiogram 3
- Pillow (PNG-карточки)
- Groq API (Llama 3.3 70B) — Phase 3

## Текущий прогресс

### 2026-03-24 (сессия 1)
- Создана структура монорепо: `agent/`, `backend/`, `frontend/`, `bot/`, `shared/`, `docs/`, `.claude/`
- Перемещены документы в `docs/`

**Готово:**
- `shared/f1_mappings.py` — tracks, teams, drivers, session types, weather, tyres, penalties, helpers
- `shared/points_system.py` — calc_points, calc_wdc, calc_wcc
- `shared/packet_format.py` — PacketAdapter (2024/2025), EVENT_CODES, PACKET_IDS
- `backend/db/base.py` — async SQLAlchemy engine + AsyncSession
- `backend/models/models.py` — все таблицы Phase 1: Player, Season, SeasonContract, Race, RaceResult, RaceEvent, ChampionshipStanding, ConstructorStanding, PenaltyCorrection
- `backend/services/player_mapper.py` — find_player_by_steam_name, resolve_participants
- `backend/services/round_detector.py` — detect_round (new/duplicate/reconnect/new_season)
- `backend/services/standings_service.py` — recalc_standings (BackgroundTask)
- `backend/routers/races.py` — POST /api/race/submit, GET /api/race/{id}, GET /api/races/{season_id}
- `backend/routers/standings.py` — GET /api/standings/{season_id}, GET /api/constructors/{season_id}
- `backend/routers/players.py` — GET /api/player/{id}/stats, GET /api/calendar/{season_id}
- `backend/routers/ws.py` — WebSocket hub (agent status relay)
- `backend/main.py` — FastAPI app
- `backend/requirements.txt`
- `backend/Dockerfile`
- `docker-compose.yml`

- `agent/config.py` — конфиг (SERVER_URL, WS_URL, INVITE_TOKEN, UDP_PORT, SEASON_ID, пути)
- `agent/state_machine.py` — StateMachine (IDLE→WAITING→QUALIFYING→RACE→FINISHED→UPLOADED)
- `agent/raw_logger.py` — запись сырых пакетов в .bin файл, replay_log генератор
- `agent/local_cache.py` — JSON кэш FinalClassification на диск (атомарная запись)
- `agent/udp_listener.py` — UDP socket listener в отдельном потоке, парсит header
- `agent/packet_parser.py` — парсер через f1-packets + extract_session_info/participants/final_classification/event
- `agent/ws_client.py` — WebSocket клиент с авто-реконнектом, отдельный поток + asyncio loop
- `agent/uploader.py` — build_race_payload, upload_race (retry 3x), retry_pending_uploads
- `agent/auto_scan.py` — верификация trackId/teamId/driverId при первом запуске
- `agent/main.py` — F1Agent: orchestrates all components, tray icon (pystray)
- `agent/requirements.txt`

- `frontend/lib/api.ts` — типизированный API клиент (fetch)
- `frontend/lib/ws.ts` — useAgentStatus() React hook (WebSocket + авто-реконнект)
- `frontend/lib/utils.ts` — formatLapTime, formatRaceTime, formatDate
- `frontend/app/layout.tsx` — root layout + Nav
- `frontend/app/page.tsx` — Lobby: agent status, следующая гонка, топ игроков, история
- `frontend/app/race/[id]/page.tsx` — Results: таблица 20 пилотов, events, FL, delta grid→pos
- `frontend/app/standings/page.tsx` — WDC (все 20) + WCC (все 10), progress bars
- `frontend/app/profile/[id]/page.tsx` — Profile: stats, recharts line chart, история гонок
- `frontend/app/calendar/page.tsx` — Calendar: прогресс-бар, список раундов
- `frontend/components/` — Nav, AgentStatusBadge, TeamColorBar, PlayerBadge, PointsBar
- `frontend/Dockerfile`

- `bot/config.py` — BOT_TOKEN, API_URL, SEASON_ID, CHAT_ID, ADMIN_IDS
- `bot/api_client.py` — async HTTP клиент к backend
- `bot/formatters.py` — fmt_race_results, fmt_wdc_standings, fmt_wcc_standings, fmt_player_stats, fmt_calendar
- `bot/card_generator.py` — generate_race_card (1200×675), generate_standings_card (Pillow)
- `bot/notifications.py` — post_race_results (текст + PNG + WDC + WCC), ask_unknown_player (inline buttons)
- `bot/handlers/commands.py` — /standings, /constructors, /last, /stats, /calendar, /register, /addsteam, /help
- `bot/callbacks/player_map.py` — callback для маппинга Steam → Player
- `bot/internal_server.py` — aiohttp сервер :8001 для webhook от backend
- `bot/main.py` — Dispatcher + polling + internal server
- `bot/requirements.txt`, `bot/Dockerfile`
- `backend/routers/players_admin.py` — /register, /add_steam, /map_steam, /players
- `backend/services/bot_notifier.py` — notify_race_uploaded (backend → bot)

- `backend/alembic.ini` — конфиг Alembic
- `backend/migrations/env.py` — async → sync адаптер для Alembic
- `backend/migrations/versions/0001_initial_schema.py` — полная миграция Phase 1
- `backend/routers/admin.py` — POST/GET /api/admin/seasons
- `backend/main.py` — lifespan: auto-migrate при старте
- `.env.example` — все переменные окружения с комментариями
- `docker-compose.yml` — обновлён с env_file и healthcheck
- `scripts/setup_season.py` — создаёт Season 1 с F1 2025 календарём
- `scripts/install_agent.bat` — установка agent на Windows
- `scripts/build_agent_exe.bat` — сборка .exe через PyInstaller
- `scripts/run_dev.bat` — запуск всех сервисов в dev режиме
- `QUICKSTART.md` — инструкция первого запуска

## Статус Phase 1

**ВСЁ ГОТОВО ✅** — можно запускать и тестировать

### Что осталось (не код, а действия):
1. `cp .env.example .env` и заполнить токены
2. `docker-compose up -d`
3. `python scripts/setup_season.py`
4. Зарегистрировать игроков через бота
5. Первая тестовая гонка

## Phase 2 ✅

- `backend/migrations/versions/0002_phase2_achievements.py` — таблицы achievements, player_achievements, season_id в race_results
- `backend/services/achievement_definitions.py` — 22 достижения, seed при старте
- `backend/services/achievement_engine.py` — 18 чекеров (FIRST_BLOOD, ROCKET_START, RAIN_MASTER, DOMINATOR, CONSISTENCY_KING, SPEED_DEMON, etc.)
- `backend/services/fun_stats.py` — 7 номинаций каждые 4 гонки (Mr.Consistent, Король обгонов, Штрафник, etc.)
- `backend/routers/stewards.py` — POST /api/stewards/penalty (коррекция времени + пересчёт позиций/standings)
- `backend/routers/achievements.py` — /achievements, /records, /fun_stats
- `bot/handlers/achievements.py` — /achievements, /records
- `bot/handlers/stewards.py` — /remove_penalty (только ADMIN_IDS)
- `bot/notifications.py` — post_achievements, post_fun_stats
- `bot/internal_server.py` — обрабатывает achievements + fun_stats в webhook
- `backend/services/bot_notifier.py` — передаёт achievements + fun_stats в уведомление

**Flow после гонки:**
```
race/submit → recalc_standings → notify_race_uploaded (sleep 3s)
  → check_achievements_after_race
  → compute_fun_stats (если гонок кратно 4)
  → POST bot/internal → post_results + post_achievements + post_fun_stats
```

## Phase 3 ✅

- `backend/services/ai_engineer.py` — AI Race Engineer (Groq Llama 3.3 70B). AICoachPayload, _build_prompt(), SYSTEM_PROMPT как Питер Боннингтон. Stagger 30s между дебрифами. Отправляет через /internal/debrief.
- `backend/services/contract_generator.py` — _calc_rating() (avg_pos 40%+win_rate 25%+consistency 20%+PPR 15%), _pick_offers() (TEAM_TIER, 3 тира), _generate_narrative() (Groq+fallback), apply_contract().
- `backend/routers/contracts.py` — POST /api/contracts/generate/{season_id}, GET /api/contracts/{season_id}, POST /api/contracts/accept.
- `backend/main.py` — зарегистрирован contracts.router.
- `backend/services/bot_notifier.py` — после bot notify запускает run_debriefs_after_race().
- `bot/handlers/contracts.py` — /contracts (просмотр предложений), /accept [команда] (принять).
- `bot/internal_server.py` — добавлены /internal/debrief и /internal/contracts_ready.
- `bot/api_client.py` — добавлен метод post().
- `bot/main.py` — зарегистрирован contracts.router.
- `bot/handlers/commands.py` — /contracts и /accept в /help.
- `.env.example` — GROQ_API_KEY добавлен.
- `docker-compose.yml` — GROQ_API_KEY передан в backend.

**Flow Phase 3:**
```
race/submit → recalc_standings → notify_race_uploaded (sleep 3s)
  → achievements + fun_stats → POST bot/internal/race_uploaded
  → run_debriefs_after_race (stagger 30s per player)
    → _call_groq → POST bot/internal/debrief → личное сообщение игроку

Admin: POST /api/contracts/generate/{season_id}
  → generate_contracts → _calc_rating + _pick_offers + _generate_narrative
  → POST bot/internal/contracts_ready → личные сообщения всем игрокам
Player: /contracts → просмотр | /accept McLaren → apply_contract
```

## Phase 4 ✅

**Архитектура телеметрии:**
```
Race state → TelemetryBuffer.start_collecting() → 5Hz sampler (thread)
  ← CarTelemetry(ID:6): speed/throttle/brake/gear/drs
  ← Motion(ID:0): world_x/world_z (GPS координаты)
  ← LapData(ID:2): lap_number/lap_distance/session_time
→ FinalClassification → upload_race() → race_id
→ TelemetryBuffer.stop_and_flush(race_id)
  → POST /api/telemetry/submit per lap (background threads)
```

**Новые файлы:**
- `backend/models/models.py` — LapTelemetry (race_id, vehicle_index, lap_number, lap_time_ms, samples JSONB)
- `backend/migrations/versions/0003_phase4_telemetry.py` — таблица + индексы
- `agent/telemetry_buffer.py` — 5Hz sampler, буферизация по кругам, flush после upload
- `agent/packet_parser.py` — extract_car_telemetry(), extract_motion(), extract_lap_data()
- `agent/udp_listener.py` — PACKET_ID_MOTION=0, PACKET_ID_CAR_TELEMETRY=6
- `agent/uploader.py` — upload_race() теперь возвращает (bool, race_id|None)
- `agent/main.py` — обработка Motion+CarTelemetry+LapData пакетов, start_collecting/stop_and_flush
- `backend/routers/telemetry.py` — POST /submit, GET /{race_id}, GET /{race_id}/{vidx}/{lap}, GET /{race_id}/{vidx}/best, GET /{race_id}/compare
- `backend/main.py` — зарегистрирован telemetry.router
- `frontend/components/TrackMap.tsx` — SVG heatmap (speed/throttle/brake/gear), цветовая шкала по сегментам
- `frontend/app/telemetry/[race_id]/page.tsx` — выбор пилота/круга/метрики, мини-статы
- `frontend/app/compare/[race_id]/page.tsx` — сравнение 2 пилотов: 2 карты + SVG speed chart + stats table
- `frontend/app/race/[id]/page.tsx` — ссылка "Телеметрия →"

**Все 4 фазы завершены. Проект полностью готов к запуску.**

## Phase 5 (планируется) — AI Журналист & Новости

**Концепция:** Лобби становится "живым" — после каждой гонки автоматически генерируются новости и интервью.

**Компоненты:**
- **AI Журналист** — генерация пост-рейс статей в стиле F1-журналистики (Groq). Анализ событий гонки: обгоны, сходы, штрафы, борьба за позиции, тренды сезона.
- **AI Интервью** — ИИ-журналист "берёт интервью" у пилотов после гонки. Вопросы на основе реальных данных (позиция, инциденты, темп). Пилот отвечает текстом → ИИ генерирует follow-up. Публикуется как "пресс-конференция".
- **Лента новостей** — `/season/[id]/news` — хронологическая лента статей и интервью внутри лобби.
- **Telegram** — краткие новости автоматически в чат.

**Backend:** `ai_journalist.py`, `routers/news.py`, таблицы `lobby_news`, `lobby_interviews`.
**Frontend:** `app/season/[id]/news/page.tsx`.
**Триггер:** Автоматически после `race/submit`.

## Архитектура сайта (после рефакторинга навигации)

### URL-структура
```
/                        — Главная: Current Season Cockpit + вход в продуктовый слой
/seasons                 — Индекс и архив сезонов
/season/[id]             — Главный обзор сезона
/season/[id]/standings   — Таблица сезона
/season/[id]/calendar    — Календарь сезона
/season/[id]/live        — Оперативный live-слой сезона
/season/[id]/engineer    — Сезонный AI-инженер
/season/[id]/manage      — Операторское управление сезоном
/races                   — Архив и поиск гонок
/race/[id]               — Каноническая страница результатов
/race/[id]/analysis      — Guided entry в глубокий анализ
/telemetry/[race_id]     — Сырая телеметрия
/compare/[race_id]       — Сравнение пилотов
/race/[id]/replay        — Пространственный replay/track view
/players                 — Индекс игроков
/players/[id]            — Публичный профиль игрока
/records                 — Глобальные рекорды и достижения
/launcher                — Установка и trust/setup слой лаунчера
/workspace               — Member hub / personal next actions
/me                      — Личный кабинет и account-linked tools
/lobby/[id]              — Group workspace / контейнер лобби
/lobby/join              — Join by invite
/login                   — Авторизация
/admin                   — Администрирование
```

### Навигационная модель
- Основной top nav: `Home`, `Seasons`, `Races`, `Players`, `Records`, `Launcher`, `Workspace`
- Канонический путь объекта: `Home -> Seasons -> Season -> Race`
- Контекстная навигация:
  - сезон: `Overview / Standings / Calendar / Live / Engineer / Manage`
  - гонка: `Results / Analysis / Telemetry / Compare / Replay`
- Глубокие страницы открываются с breadcrumbs, а не как "сироты" по прямым ссылкам

### Новые backend endpoints
- `GET /api/seasons` — список всех сезонов с races_played / total_rounds
- `GET /api/seasons/{id}` — один сезон
- `POST /api/seasons/assistant` — AI-ассистент (player_id + question → Groq)
- `GET /api/player/{id}/season-history` — статистика по каждому сезону (из ChampionshipStanding)

### /me — личный кабинет
- Общая статистика по ВСЕМ сезонам (суммарно)
- Таблица разбивки по сезонам (место, очки, победы)
- История гонок
- AI-ассистент: задаёт вопросы, Groq анализирует весь перформанс

## Дополнительные улучшения (после Phase 4)

**Исправления:**
- `agent/uploader.py` — `retry_pending_uploads` исправлен (tuple unpacking `success, _ = upload_race()`)
- `bot/config.py` — добавлен `BOT_NOTIFY_SECRET`

**Frontend:**
- `frontend/lib/api.ts` — добавлены типы: Achievement, TrackRecord, FunStat, TelemetrySample/Driver/Lap, ContractOffer/PlayerContracts; расширен `api` объект
- `frontend/app/live/page.tsx` — Live Race страница (WebSocket, live leaderboard, агент-статус)
- `frontend/app/admin/page.tsx` — Admin Panel (игроки, сезоны, генерация контрактов)
- `frontend/app/records/page.tsx` — Рекорды трасс + Fun Stats + все Achievements
- `frontend/app/profile/[id]/page.tsx` — секция Achievements (значки)
- `frontend/components/Nav.tsx` — Live, Records, Admin в навигации

**Backend:**
- `backend/routers/ws.py` — нормализован формат agent_status, добавлен live_data тип

**Agent:**
- `agent/ws_client.py` — `send_live()` метод, рефакторинг `_enqueue()`
- `agent/main.py` — live snapshot (throttled 2Hz) из LapData пакетов, `_send_live_snapshot()`

---

## Website Shell & Русская локаль (2026-03-27)

- Сайт переведен в русский-first режим: `lang="ru"`, `ru-RU` формат дат, русские labels в shell/nav/footer/subnav и на основных страницах.
- Из-за отсутствия `cyrillic` subset у `Barlow Condensed` display-font был заменен на `Roboto Condensed`.
- Переведены ключевые product/membership/operator/deep-analysis экраны:
  - home, seasons, races, players, records, launcher
  - season overview + standings/calendar/live/engineer/manage
  - race detail + analysis/telemetry/compare/replay
  - workspace, me, login, lobby/join, admin, practice
- Переведены вторичные UI-слои: footer, badges, modal labels, achievement names, CTA copy, launcher help/trust copy.
- Совместимость старых URL сохранена через redirect:
  - `/agent` -> `/launcher`
  - `/profile/[id]` -> `/players/[id]`
  - `/calendar`, `/standings`, `/live` -> активный сезон
- Документация по новому web shell добавлена в `docs/website_shell_handoff_2026-03-27.md`, а `QUICKSTART.md` обновлен под новую структуру маршрутов.
- Валидация: `npm run build` в `frontend` проходит.
- Follow-up:
  - полноценный EN toggle пока не сделан; для этого нужен явный i18n-слой со словарями
  - сокращения типа `WDC/WCC/ERS/DRS/DNF/FL` оставлены как доменные термины

---

## Решения и заметки

- UDP может терять пакеты → 3 уровня защиты: local cache, retry 3x, raw packet log
- FinalClassification — критический пакет, приходит 1 раз
- Equal performance → контракты это нарратив, не преимущество
- Очки считаются для ВСЕХ 20 пилотов (люди + AI)
- Steam names хранятся как массив (история)
- m_packetFormat в header → adapter pattern для 2024/2025

# F1 League — состояние проекта (CLAUDE.md)

## Инфраструктура

- **Сервер**: Windows, Docker Compose, путь проекта `C:\f1t`
- **IP пользователя (игровой ПК)**: `192.168.0.114`
- **Деплой**: `docker-compose up -d` из `C:\f1t`
- **Сервисы**: postgres:5432, backend:8000, frontend:3000, bot:8001

## .env — ключевые значения

```
# Реальные значения живут в .env (не закоммичены, в .gitignore).
# Эти секреты помечены к ротации в PR 1.4 (Sprint 1).

POSTGRES_PASSWORD=<set in .env>
BOT_TOKEN=<set in .env>
TG_CHAT_ID=<set in .env>
TG_ADMIN_IDS=<set in .env>
BOT_NOTIFY_SECRET=<set in .env>
GROQ_API_KEY=<set in .env>
NEXTAUTH_SECRET=<set in .env>
NEXTAUTH_URL=http://192.168.0.114.nip.io:3000
FRONTEND_URL=http://192.168.0.114.nip.io:3000
GOOGLE_CLIENT_ID=<set in .env>
GOOGLE_CLIENT_SECRET=<set in .env>
```

## Google OAuth

- Проект Google Cloud: `f1-league-491219` ("Лига Формулы-1")
- OAuth клиент: "Веб-сайт Лиги Формулы-1"
- JS origin: `http://192.168.0.114.nip.io:3000`
- Redirect URI: `http://192.168.0.114.nip.io:3000/api/auth/callback/google`
- Статус: **Testing** (только тестовые пользователи)
- Тестовый пользователь: `gregorysky04i@gmail.com`
- Для открытого доступа → Google Console → Аудитория → "Опубликовать приложение"
- **Важно**: для входа через Google открывать сайт через `http://192.168.0.114.nip.io:3000`

## Структура бэкенда

```
backend/
  models/models.py          — Player, Race, Lap, WebUser
  routers/
    players_admin.py        — CRUD игроков, /by_telegram/{id}, PATCH /{id}
    web_auth.py             — /api/web/* (register, login, google, steam)
    races.py, laps.py, ...
  services/
    steam_resolver.py       — resolve_steam_profile(), fetch_current_name()
    player_mapper.py        — find_player_by_steam_name_with_fallback()
  migrations/versions/
    0004_steam_id64.py      — добавляет steam_id64, steam_url в players
    0005_web_users.py       — создаёт таблицу web_users
```

### Модель Player (ключевые поля)
- `telegram_id`, `name`, `steam_names[]`
- `steam_id64` (постоянный ID Steam)
- `steam_url`, `avatar_url`

### Модель WebUser
- `id`, `email`, `name`, `picture`
- `google_id`, `steam_id64`, `hashed_password`
- `player_id` → FK на Player
- `is_system_admin` (bool) — глобальный админ системы

### Модель Lobby
- `id`, `name`, `description`, `avatar_url`
- `creator_id` → FK на WebUser
- `invite_code` (unique, auto-generated)

### Модель LobbyMember
- `lobby_id`, `web_user_id`, `role` (admin/moderator/member)

### Таблицы Practice Sessions
- `practice_sessions`: id, web_user_id, track_id, track_name, session_type, total_laps, best_lap_ms, created_at, ended_at
- `practice_laps`: id, session_id, lap_number, lap_time_ms, sector1/2/3_ms, tyre_compound, valid

### JWT Auth (для лаунчера)
- `backend/services/jwt_auth.py` — HMAC-signed tokens (30-day expiry)
- `POST /api/web/launcher/login` — email+password → user + JWT token
- `GET /api/web/me/by-token` — профиль по Authorization header

## Структура бота

```
bot/handlers/commands.py
  /register  — auto-использует Telegram display name; идемпотентен
  /stats     — auto-lookup по telegram_id; /stats N для других
  /addsteam  — принимает Steam URL/ID64/ник; показывает persona_name
  /help      — обновлён
```

## Структура фронтенда (Next.js 14, App Router)

```
frontend/
  app/
    page.tsx             — Hub: список лобби, навигация
    lobby/[id]/page.tsx  — Дашборд лобби: сезоны, участники, invite, создание сезонов
    lobby/join/page.tsx  — Вступление по invite коду/ссылке
    season/[id]/
      layout.tsx         — SeasonNav (breadcrumb с лобби, вкладки)
      page.tsx           — Обзор сезона (прогресс, следующая гонка, топ игроков)
      standings/page.tsx — WDC + WCC сезона
      calendar/page.tsx  — Календарь сезона
      live/page.tsx      — Live Race (WebSocket)
    standings/page.tsx   — редирект → /season/1/standings
    calendar/page.tsx    — редирект → /season/1/calendar
    live/page.tsx        — редирект → /season/1/live
    login/page.tsx       — Google, Steam, email/password вход
    me/page.tsx          — личный кабинет, лобби, Glicko рейтинг, AI ассистент, System Admin панель
    admin/page.tsx       — (legacy, функционал перенесён в /me для system admin)
    agent/page.tsx       — инструкция установки агента с pre-filled конфигом
    race/[id]/
      page.tsx           — результаты гонки, ссылки на анализ и телеметрию
      analysis/page.tsx  — анализ гонки: position chart, lap times, sectors, strategy
    telemetry/[race_id]/
      page.tsx           — телеметрия: track map (7 метрик), выбор круга
    compare/[race_id]/
      page.tsx           — сравнение: multi-panel overlay, speed delta, stats
    profile/[id]/
      page.tsx           — публичный профиль: рейтинг, тренды, ачивки, сезоны
      achievements.ts    — 52 ачивки (definitions)
    api/auth/[...nextauth]/route.ts
  lib/
    api.ts               — типы и API вызовы (RaceAnalysis, TelemetrySample, etc.)
    auth.ts              — NextAuth config (Google, Credentials, Steam)
  components/
    Nav.tsx              — глобальная навигация: Главная | Рекорды | Агент
    SeasonNav.tsx        — вкладки + breadcrumb (Главная → Лобби → Сезон)
    TrackMap.tsx          — SVG track map с 7 цветовыми метриками
    Providers.tsx        — SessionProvider wrapper
  types/next-auth.d.ts   — расширение Session: id, playerId
  middleware.ts          — защищает /me
```

## Архитектура ролей

### System Admin
- `web_users.is_system_admin` = true
- Определяется по email через env `SYSTEM_ADMIN_EMAILS` (default: `gregorysky04i@gmail.com`)
- Автоматом выставляется при Google OAuth регистрации
- Видит System Admin панель в `/me` (управление игроками)

### Lobby roles (per lobby)
- **lobby_members** таблица: `lobby_id`, `web_user_id`, `role`
- Роли: `admin` (создатель) | `moderator` | `member`
- Admin может: менять роли, kick, сброс invite, управление сезонами
- Moderator может: создавать сезоны, менять настройки лобби
- Member: просмотр, участие

### Иерархия: Lobby → Season → Race
- `lobbies` содержат сезоны (`seasons.lobby_id`)
- `seasons` содержат гонки (`races.season_id`)
- Invite: код + ссылка (`/lobby/join?code=...`)

## Backend endpoints

```
# Lobby
GET    /api/lobby                       — список всех лобби
POST   /api/lobby                       — создать лобби
GET    /api/lobby/{id}                  — детали лобби + роль
POST   /api/lobby/{id}/join             — вступить по invite коду
POST   /api/lobby/join-by-code          — вступить только по коду (без lobby_id)
DELETE /api/lobby/{id}/leave            — покинуть лобби
GET    /api/lobby/{id}/members          — участники лобби
PATCH  /api/lobby/{id}/members/{uid}/role — сменить роль
DELETE /api/lobby/{id}/members/{uid}    — kick
PUT    /api/lobby/{id}/settings         — обновить название/описание
POST   /api/lobby/{id}/invite/reset     — сбросить invite code
POST   /api/lobby/{id}/seasons          — создать сезон в лобби
GET    /api/lobby/{id}/seasons          — сезоны лобби
GET    /api/lobby/{id}/engineer         — AI инженер контекст
POST   /api/lobby/{id}/engineer/ask     — вопрос AI инженеру

# Seasons
GET  /api/seasons                   — список всех сезонов (+ lobby_id)
GET  /api/seasons/{id}              — один сезон с деталями
POST /api/seasons/assistant         — AI-ассистент (player_id + question)
GET  /api/player/{id}/season-history — статистика по сезонам (ChampionshipStanding)

# Practice (personal telemetry, JWT-protected)
POST /api/practice/sessions           — создать сессию
GET  /api/practice/sessions           — список сессий пользователя
GET  /api/practice/sessions/{id}      — детали + круги
POST /api/practice/sessions/{id}/laps — добавить круги
POST /api/practice/sessions/{id}/end  — завершить сессию

# Launcher Auth
POST /api/web/launcher/login         — email+password → user + JWT token
GET  /api/web/me/by-token            — профиль по Bearer token
```

## Аутентификация (NextAuth v4)

- **Google**: OAuth → POST /api/web/google → upsert WebUser
- **Email/пароль**: POST /api/web/login → bcrypt verify → + JWT token
- **Steam**: GET /api/web/steam/start → Steam OpenID → callback → одноразовый код → NextAuth Credentials
- **Launcher**: POST /api/web/launcher/login → JWT token (30 дней, HMAC-signed)
- Сессия: JWT (NextAuth cookie на фронте, Bearer token в лаунчере)

## Миграции Alembic

Применяются автоматически при старте backend контейнера.
Текущие: 0001…0011

## Команды

```bash
# Запуск
cd C:\f1t && docker-compose up -d

# Пересборка одного сервиса
docker-compose build frontend && docker-compose up -d frontend

# Логи
docker-compose logs -f backend
docker-compose logs -f bot

# Тест API
curl http://localhost:8000/api/players
curl http://localhost:8000/docs   # Swagger
```

## Известные нюансы

1. **nip.io**: `192.168.0.114.nip.io` резолвится в `192.168.0.114` — нужен для Google OAuth (Google не принимает IP)
2. **Steam имена**: хранятся в `steam_names[]` как кеш; постоянный ID — `steam_id64`
3. **Привязка Steam→F1**: в `/me` есть дропдаун "Выбери свой профиль" — выбрать себя из списка игроков
4. **Admin не защищён**: `/admin` доступен без авторизации (пока)
5. **bcrypt** добавлен в `backend/requirements.txt`
6. **next-auth 4.24.7** добавлен в `frontend/package.json`

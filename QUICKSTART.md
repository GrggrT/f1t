# F1 League - Quickstart

## Первый запуск сервера

### 1. Подготовь `.env`
```bash
cp .env.example .env
# Заполни: BOT_TOKEN, TG_CHAT_ID, TG_ADMIN_IDS, BOT_NOTIFY_SECRET
# Замени POSTGRES_PASSWORD на своё значение
```

### 2. Запусти сервисы
```bash
docker-compose up -d
```

Будут подняты:
- PostgreSQL на `:5432`
- Backend (FastAPI) на `:8000`
- Frontend (Next.js) на `:3000`
- Bot (aiogram) + internal server на `:8001`

### 3. Создай `Season 1`
```bash
pip install httpx
python scripts/setup_season.py --url http://localhost:8000
```

Или вручную:
```bash
curl -X POST http://localhost:8000/api/admin/seasons \
  -H "Content-Type: application/json" \
  -d '{"name": "Season 1", "calendar": [], "points_system": {}}'
```

### 4. Открой API docs
`http://localhost:8000/docs`

## Agent / Launcher (ПК хоста)

### Установка для другого игрока
Скачивание с backend:
- installer: `http://YOUR_SERVER_IP:8000/agent/installer`
- portable exe: `http://YOUR_SERVER_IP:8000/agent/download`

Предпочтительный путь для раздачи - `Setup_F1LeagueAgent.exe`.

### Первый запуск launcher
1. Установи `Setup_F1LeagueAgent.exe` или запусти `F1LeagueAgent.exe`.
2. Launcher на первом старте создаст `%USERPROFILE%\f1league_agent\launcher_config.json`.
3. По умолчанию будут использованы безопасные localhost targets:
   - backend: `http://localhost:8000`
   - frontend: `http://localhost:3000`
   - websocket: `ws://localhost:8000/ws/agent`
4. Если backend находится на другом ПК, поменяй адрес прямо на login screen или в `Settings`.
5. Войди под своим аккаунтом и нажми `Start Agent`.

### Source/dev запуск
```bash
scripts\install_agent.bat
call agent_venv\Scripts\activate.bat
python -m agent.launcher
```

### Сборка релизного launcher
```bash
agent\build_launcher.bat
```

Результат:
- `agent\dist\F1LeagueAgent.exe`
- `agent\installer_output\Setup_F1LeagueAgent.exe`
- `backend\static\F1LeagueAgent.exe`
- `backend\static\Setup_F1LeagueAgent.exe`

### Release smoke checklist для launcher

- [ ] Выполнена свежая сборка `agent\build_launcher.bat`
- [ ] Новые артефакты лежат в `agent\dist`, `agent\installer_output` и `backend\static`
- [ ] Launcher стартует из `Setup_F1LeagueAgent.exe` или `F1LeagueAgent.exe` без traceback
- [ ] Login screen позволяет сохранить backend target и открыть web app
- [ ] Основные страницы открываются без явных UI/JS проблем: dashboard, lobbies, profile, engineer, settings
- [ ] Dashboard корректно показывает backend/frontend/auth/UDP/websocket/overlay/upload diagnostics
- [ ] `Start Agent` / `Stop Agent` работают предсказуемо в personal mode
- [ ] Lobby mode не стартует без валидного host season и стартует после явного выбора сезона
- [ ] `Open Overlay`, `Open Data Folder` и `Open Web App` работают из launcher
- [ ] Перед раздачей проверены deployment-specific значения в `.env` и сохранённом launcher config, если сервер не на localhost

### Race-day postmortem quick path

- `python -m agent.postmortem --json`
- if postmortem shows `orphaned_telemetry` with no backend race row: `python -m agent.postmortem --quarantine-orphaned-telemetry --json`
- если есть raw log: `python -m agent.replay_harness --log "<RAW_LOG_PATH>" --agent`
- reproducible end-to-end validation перед релизом: `python C:\f1t\tests\live_validation_harness.py --json`
- если backlog есть только у telemetry, launcher manual retry теперь тоже обязан его подхватывать; не ориентируйся только на race upload cache

## Telegram Bot

### Регистрация игроков
В групповом чате:
```text
/register Григорий
/addsteam GregF1_Steam
```

### Команды
| Команда | Описание |
|---------|----------|
| `/standings` | WDC таблица + PNG |
| `/constructors` | WCC таблица + PNG |
| `/last` | Последняя гонка |
| `/stats [id]` | Статистика игрока |
| `/calendar` | Расписание |
| `/register Имя` | Регистрация |
| `/addsteam НикВИгре` | Добавить Steam ник |
| `/achievements` | Ачивки сезона |
| `/records` | Рекорды трасс |
| `/contracts` | Контрактные предложения |
| `/accept Команда` | Принять контракт |

### Phase 3 - AI Race Engineer
После гонки каждый игрок получает в личку разбор от AI-инженера.

Нужен `GROQ_API_KEY` в `.env`.

## Web интерфейс

Интерфейс сайта теперь русский по умолчанию и собран вокруг season-first product shell.

- Основная навигация: `Home`, `Seasons`, `Races`, `Players`, `Records`, `Launcher`, `Workspace`
- Старые маршруты совместимости работают через redirect:
  - `/agent` → `/launcher`
  - `/profile/{id}` → `/players/{id}`
  - `/calendar`, `/standings`, `/live` → страницы активного сезона

| Страница | URL |
|----------|-----|
| Главная / product shell | `http://server:3000/` |
| Сезоны | `http://server:3000/seasons` |
| Обзор сезона | `http://server:3000/season/{season_id}` |
| Таблица сезона | `http://server:3000/season/{season_id}/standings` |
| Календарь сезона | `http://server:3000/season/{season_id}/calendar` |
| Live сезона | `http://server:3000/season/{season_id}/live` |
| AI-инженер сезона | `http://server:3000/season/{season_id}/engineer` |
| Управление сезоном | `http://server:3000/season/{season_id}/manage` |
| Архив гонок | `http://server:3000/races` |
| Рекорды | `http://server:3000/records` |
| Результаты гонки | `http://server:3000/race/{id}` |
| Анализ гонки | `http://server:3000/race/{id}/analysis` |
| Телеметрия | `http://server:3000/telemetry/{race_id}` |
| Сравнение пилотов | `http://server:3000/compare/{race_id}` |
| Повтор гонки | `http://server:3000/race/{id}/replay` |
| Игроки | `http://server:3000/players` |
| Профиль игрока | `http://server:3000/players/{player_id}` |
| Launcher | `http://server:3000/launcher` |
| Workspace | `http://server:3000/workspace` |
| Личный кабинет | `http://server:3000/me` |
| Join by invite | `http://server:3000/lobby/join` |
| Admin | `http://server:3000/admin` |
| API Docs | `http://server:8000/docs` |

## Первая гонка - чеклист

- [ ] Сервер запущен (`docker-compose up -d`)
- [ ] Season 1 создан (`python scripts/setup_season.py`)
- [ ] Игроки зарегистрированы (`/register` + `/addsteam`)
- [ ] Launcher установлен и открыт на ПК хоста
- [ ] Backend target в launcher выставлен корректно
- [ ] Agent запущен из launcher
- [ ] F1 25 -> Settings -> Telemetry: `ON`, `IP=localhost`, `Port=20777`, `Format=2025`
- [ ] Хост создаёт лобби в F1 25 -> agent переходит в `Waiting`
- [ ] Гонка начинается -> agent переходит в `Race`
- [ ] После финиша результаты уходят на backend и в бот

## Структура проекта
```text
f1t/
|- agent/
|- backend/
|- frontend/
|- bot/
|- shared/
|- scripts/
|- docs/
`- docker-compose.yml
```

Frontend локально: `http://localhost:3000`
Frontend с другой машины: `http://YOUR_SERVER_IP:3000`

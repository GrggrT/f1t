# F1 LEAGUE SYSTEM — Проектная спецификация

> **Версия:** 4.0 Final (Post-Review)  
> **Дата:** 24 марта 2026  
> **Автор:** Григорий  
> **Статус:** Готово к разработке  
> **Ревью:** 4 независимых ревью интегрированы

---

## 1. VISION

Превратить еженедельные гонки компании друзей (4-5 человек) в F1 25 из "поиграли и забыли" в **полноценную онлайн-карьеру** с автоматической статистикой, красивыми карточками, достижениями, AI-инженером и контрактной системой — без единого ручного ввода данных.

**Ядро:** Всё автоматически. Хост жмёт одну кнопку на сайте. Дальше система делает всё сама.

**Модель:** FACEIT-style — сайт как центр, local agent как мост, Telegram как нотификации.

---

## 2. ФОРМАТ ИГРЫ

| Параметр | Значение |
|----------|----------|
| Игра | EA SPORTS F1 25 (PC, Steam/EA) |
| Игроки | 4-5 друзей + 15-16 AI ботов = полная сетка 20 |
| Формат | Мультиплеер, чемпионат по календарю F1 |
| Сессия | Short Qualifying + Short Race |
| Частота | 1-4 гонки за вечер, несколько раз в неделю |
| Перфоманс | Equal performance (все машины одинаковые) |
| Пилоты | Закреплены на весь сезон по договорённости |
| Хост | Обычно один, но может меняться день ото дня |
| Лобби | Может пересоздаваться (проблемы с сетью) |
| Коммуникация | Telegram-группа |

---

## 3. АРХИТЕКТУРА (FACEIT-MODEL)

### 3.1 Принцип

**Сайт — центр системы.** Telegram бот — канал нотификаций. Local agent — мост между F1 25 и сервером.

```
┌─────────────────────────────────────────────────────────────┐
│                        HOST PC                              │
│  ┌──────────────┐     ┌──────────────────────┐              │
│  │   F1 25      │────▶│   LOCAL AGENT         │              │
│  │  (UDP :20777)│     │   Python + pystray    │              │
│  └──────────────┘     │   - UDP listener      │              │
│                       │   - Local cache       │              │
│                       │   - Raw packet log    │              │
│                       │   - WS client (out)   │              │
│                       └──────────┬───────────┘              │
└──────────────────────────────────┼──────────────────────────┘
                                   │ WebSocket (outbound only)
                                   │ Auth: invite-token
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│                     GCP SERVER                               │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  FASTAPI     │  │ NEXT.JS SITE │  │  TELEGRAM BOT    │   │
│  │  Backend     │  │  (Frontend)  │  │  (aiogram 3)     │   │
│  │  - REST API  │  │  - Lobby     │  │  - Auto-post     │   │
│  │  - WS hub    │  │  - Results   │  │  - PNG cards     │   │
│  │  - Points    │  │  - Standings │  │  - /commands     │   │
│  │  - Cards gen │  │  - Profiles  │  │  - Achievements  │   │
│  │  - AI engine │  │  - Calendar  │  │  - /remove_pen.  │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────┘   │
│         ▼                                                    │
│  ┌──────────────┐                                            │
│  │ POSTGRESQL   │                                            │
│  │  - Все данные│                                            │
│  │  - Все сезоны│                                            │
│  └──────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Tech Stack

| Компонент | Технология | Обоснование | Где |
|-----------|-----------|-------------|-----|
| Local Agent | **Python 3.11 + pystray + f1-packets** → PyInstaller .exe | Быстрее MVP, готовый парсер UDP, знакомый стек. Tauri → позже если нужен красивый UI | PC хостов (2-3 чел) |
| Frontend | Next.js 14 + Tailwind + WebSocket | SSR для SEO не нужен, но удобный фреймворк | GCP |
| Backend API | FastAPI + SQLAlchemy async + Pydantic | Знакомый стек, async WebSocket, BackgroundTasks | GCP |
| Database | PostgreSQL 16 | Надёжно, партицирование для телеметрии | GCP |
| Telegram Bot | aiogram 3 | Знакомый стек | GCP (один процесс) |
| Image Gen | Pillow + custom fonts (Outfit, JetBrains Mono) | Проверенный подход (как pred1 карточки) | GCP (в backend) |
| AI Engine | Groq API (Llama 3.3 70B, free tier) | 30 req/min free, хватит на 20 debriefs/вечер | Free API |
| Transport | Agent → Server: WebSocket outbound only + invite-token | NAT/firewall safe, минимальная security | Internet |

### 3.3 Монорепо

```
f1-league/
├── agent/                  # Python + pystray → PyInstaller .exe
│   ├── main.py             # Tray app + state machine
│   ├── udp_listener.py     # UDP socket + f1-packets parser
│   ├── ws_client.py        # WebSocket client → server
│   ├── local_cache.py      # Кэш FinalClassification + retry
│   ├── raw_logger.py       # Raw packet logging (страховка)
│   └── config.py           # Server URL, invite-token
├── frontend/               # Next.js 14
│   ├── app/
│   │   ├── page.tsx        # Lobby (кнопка «Я хост»)
│   │   ├── race/[id]/      # Race results
│   │   ├── standings/      # WDC + WCC
│   │   ├── profile/[id]/   # Player profile
│   │   ├── calendar/       # Season calendar
│   │   ├── achievements/   # Phase 2
│   │   └── admin/          # Season management
│   ├── components/
│   └── lib/ws.ts           # WebSocket client для live status
├── backend/                # FastAPI
│   ├── main.py
│   ├── models/             # SQLAlchemy models
│   ├── routers/
│   │   ├── races.py        # POST /race/submit, GET /race/{id}
│   │   ├── standings.py    # GET /standings, /constructors
│   │   ├── players.py      # GET /player/{id}/stats
│   │   └── ws.py           # WebSocket hub (agent status)
│   ├── services/
│   │   ├── points.py       # WDC + WCC calculator
│   │   ├── player_mapper.py    # Steam name → player (с историей)
│   │   ├── round_detector.py   # trackId → round number
│   │   ├── card_generator.py   # Pillow PNG cards
│   │   ├── achievement_engine.py  # Phase 2
│   │   ├── contract_generator.py  # Phase 3
│   │   └── ai_engineer.py        # Phase 3: Groq/Gemini
│   └── db/
├── bot/                    # aiogram 3
│   ├── main.py
│   ├── handlers/
│   ├── callbacks/
│   └── notifications.py
├── shared/
│   ├── f1_mappings.py      # trackId, driverId, teamId → names, colors
│   ├── points_system.py
│   └── packet_format.py    # Adapter для разных UDP форматов (2024/2025)
└── docker-compose.yml
```

---

## 4. КЛЮЧЕВЫЕ РИСКИ И РЕШЕНИЯ (POST-REVIEW)

### 4.1 РИСК #1: Потеря FinalClassification пакета (КРИТИЧЕСКИЙ)

**Проблема:** UDP не гарантирует доставку. FinalClassification приходит один раз. Если потерялся — результаты гонки потеряны.

**Решение (3 уровня защиты):**
1. **Local cache:** Agent кэширует FinalClassification на диск сразу при получении
2. **Retry:** Если WebSocket/POST отвалился — retry 3 раза с exponential backoff
3. **Raw packet log:** Agent пишет все пакеты в бинарный файл. Если всё сломалось — можно реплеить из лога
4. **Manual fallback:** Форма на сайте (admin) или `/add_result` через бота

### 4.2 РИСК #2: UDP формат меняется между версиями

**Проблема:** EA каждый год сдвигает биты, добавляет поля.

**Решение:**
1. Используем `f1-packets` библиотеку (обновляется автором под каждый релиз)
2. Читаем `m_packetFormat` из header пакета — поддержка форматов 2024 + 2025
3. **Adapter pattern:** `shared/packet_format.py` — прослойка маппинга. При выходе F1 26 меняем только маппинг, не логику
4. При первом запуске agent делает auto-scan и логирует все ID (tracks, drivers, teams) для верификации

### 4.3 РИСК #3: Телеметрия забьёт БД (Phase 4)

**Проблема:** 250K записей/гонка × 4 гонки/вечер = 1M строк/сессия.

**Решение:**
1. **Сэмплирование:** 2-5 Hz вместо 20-60 Hz (достаточно для heatmaps)
2. **Батчинг:** Agent буферит 3-5 секунд → отправляет одним JSON
3. **Партицирование:** `telemetry_samples PARTITION BY LIST (race_id)` — мгновенное удаление старых гонок
4. **Агрегаты:** `lap_telemetry_summary` materialized view для AI — LLM получает выжимку, не raw data
5. **Альтернатива (если PostgreSQL задохнётся):** Raw → Google Cloud Storage (JSON per lap), в PG только ссылка

### 4.4 РИСК #4: Live WebSocket — переоценён

**Проблема:** Люди играют — не смотрят сайт. Full live race view в Phase 1 это неделя работы без реальной ценности.

**Решение:**
1. **Phase 1:** Минимальный live — только статус agent'а на lobby page (`⚫ idle → 🟡 waiting → 🟢 recording → ✅ uploaded`). Подтверждение для хоста что agent работает.
2. **Phase 2+:** Полный live race view (позиции, гэпы, events) — когда базовая система стабильна.

### 4.5 РИСК #5: Steam name нестабилен

**Проблема:** Люди меняют ники, спецсимволы.

**Решение:**
1. `steam_names TEXT[]` — массив всех известных имён (история)
2. При несовпадении → сайт/бот спрашивает «Кто "xXNewName"?» с кнопками
3. Telegram подтверждение: «Это ты? Да/Нет»
4. Fuzzy matching — не нужен (5 человек, не 5000)

### 4.6 РИСК #6: Groq/Gemini rate limits для AI Engineer

**Проблема:** 4 гонки × 5 человек × длинный debrief = 20 запросов.

**Решение:**
1. Groq free tier: ~30 req/min — хватает с запасом
2. Не отправлять все 5 debriefs одновременно: BackgroundTasks + stagger 30 сек между запросами
3. LLM получает агрегаты (`AICoachPayload`), не сырую телеметрию
4. В чате: «⏳ Твой инженер анализирует телеметрию...» → через 1-2 мин полный debrief

---

## 5. DATA FLOW: ОТ ЛОББИ ДО TELEGRAM

### 5.1 Перед гонкой

1. **Сайт** показывает следующую трассу по календарю (автоматически)
2. Все видят список зарегистрированных пилотов (online/offline)
3. Хост заходит на сайт → жмёт **«Я хост сегодня»**
4. Сервер через WebSocket говорит agent'у на его PC: **активируй UDP listener**
5. Agent начинает слушать порт 20777 → статус на сайте: `🟡 Waiting...`

### 5.2 Во время гонки

6. Хост создаёт лобби в F1 25, все подключаются
7. Agent получает **Session** пакет → определяет `trackId` → читает `m_packetFormat` (2024 или 2025) → сайт: `🟢 Monaco detected`
8. Agent получает **Participants** → определяет кто human (`m_aiControlled=0`), за какого пилота (`m_driverId`), команду (`m_teamId`)
9. **Квалификация** → agent записывает grid positions
10. **Гонка** → agent буферит Events (PENA, OVTK, FTLP...), **пишет raw packets в лог-файл**

### 5.3 После финиша

11. Agent получает **FinalClassification** пакет → **кэширует локально на диск**
12. Agent собирает полный JSON всех 20 пилотов → POST `/api/race/submit`
13. Если POST failed → **retry 3x с exponential backoff** (1s, 5s, 30s)
14. Если всё failed → данные сохранены локально, отправятся при следующем подключении
15. Backend: проверяет дубли (`session_uid`) → маппит игроков по Steam name → сохраняет в PostgreSQL
16. Backend: пересчитывает WDC + WCC очки → проверяет ачивки (Phase 2)
17. Backend: генерирует PNG-карточку (Pillow)
18. Telegram bot: постит результаты + карточку + standings в группу
19. Сайт: обновляет results, standings, profiles
20. Agent сбрасывает буфер → готов к следующей гонке

### 5.4 Сценарий: 4 гонки подряд

Agent запускается один раз. После каждого финиша — отправляет → бот постит → agent сбрасывает → ждёт новую сессию. 4 гонки = 4 автоматических поста. Ноль ручных действий.

---

## 6. AUTO-DETECTION ИЗ UDP

Ноль ручного ввода. Всё из UDP пакетов.

| Данные | UDP пакет | Поле | Логика |
|--------|----------|------|--------|
| **UDP формат** | Header (все пакеты) | `m_packetFormat` | 2024 или 2025 → adapter pattern |
| Трасса | Session (ID:1) | `m_trackId` | Маппинг ID → название |
| Тип сессии | Session (ID:1) | `m_sessionType` | 8=Short Q, 10=Race. Записываем только Race |
| Кто human | Participants (ID:4) | `m_aiControlled` | 0=человек, 1=бот |
| За какого пилота | Participants (ID:4) | `m_driverId` | ID пилота (Leclerc=17) |
| Команда | Participants (ID:4) | `m_teamId` | 0=Mercedes, 1=Ferrari... |
| Steam имя | Participants (ID:4) | `m_name` | UTF-8, 32 символа |
| Позиции | FinalClassification (ID:11) | `m_position` | 1-20 |
| Best lap | FinalClassification (ID:11) | `m_bestLapTimeInMS` | Миллисекунды |
| Race time | FinalClassification (ID:11) | `m_totalRaceTime` | Для гэпов |
| Штрафы | FinalClassification (ID:11) | `m_penaltiesTime`, `m_numPenalties` | Секунды + количество |
| DNF | FinalClassification (ID:11) | `m_resultStatus` | 3=Finished, 4=DNF, 5=DSQ, 6=Retired |
| Шины | FinalClassification (ID:11) | `m_tyreStints[]` | Compound + laps каждого стинта |
| Fastest lap | Event (ID:3) | код `FTLP` | vehicleIdx + lapTime |
| Обгоны | Event (ID:3) | код `OVTK` | overtakingIdx, beingOvertakenIdx |
| Штрафы (live) | Event (ID:3) | код `PENA` | penaltyType, vehicleIdx |
| Погода | Session (ID:1) | `m_weather` | 0=clear...5=storm. Отслеживаем смену |
| Номер раунда | — | — | Вычисляем по trackId + список проведённых |

### Определение номера раунда (логика)

Система хранит календарь сезона и список проведённых гонок. При получении `trackId`:
1. Нет в текущем сезоне → следующий раунд
2. Уже была + тот же `sessionUID` → дубль, игнорируем
3. Уже была + другой `sessionUID` + тот же день + <30 мин → реконнект, спрашиваем
4. Все трассы календаря пройдены → новый сезон

---

## 7. МАППИНГ ИГРОКОВ

### Первый запуск сезона (одноразово)

1. Админ создаёт сезон на сайте: "Season 1", выбирает календарь
2. Каждый игрок регистрируется на сайте (или через бот `/register`)
3. Вводит Steam-имя (или определится автоматически из первой гонки)
4. Выбирает пилота на сезон: «Григорий → заменяет Leclerc → Ferrari»
5. Сохраняется в `season_contracts`

### Автоматический маппинг (каждая гонка)

- Agent видит human players по `m_aiControlled=0`
- Сопоставляет `m_name` с массивом `players.steam_names[]`
- Если совпадение → привязывает
- Если не нашёл → сайт/бот спрашивает «Кто "xXNewName"?» с кнопками + Telegram подтверждение
- Новое имя добавляется в `steam_names[]` (история)

---

## 8. DATABASE SCHEMA

```sql
-- ============================================
-- CORE TABLES
-- ============================================

-- Игроки (люди)
CREATE TABLE players (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL,        -- "Григорий"
    telegram_id     BIGINT UNIQUE,
    steam_names     TEXT[],                      -- ["GregF1", "Greg_v2"] — история имён
    avatar_url      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Сезоны
CREATE TABLE seasons (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50),                  -- "Season 1"
    status          VARCHAR(20) DEFAULT 'active', -- active / completed
    calendar        JSONB,                        -- [{round: 1, track_id: 3, track_name: "Bahrain"}, ...]
    points_system   JSONB,                        -- {1: 25, 2: 18, ... 10: 1, fastest_lap: 1}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Контракты (кто за кого едет в сезоне)
CREATE TABLE season_contracts (
    id              SERIAL PRIMARY KEY,
    season_id       INT REFERENCES seasons(id),
    player_id       INT REFERENCES players(id),
    driver_id       INT NOT NULL,                 -- F1 driverId (Leclerc=17)
    driver_name     VARCHAR(50),                  -- "Leclerc"
    team_id         INT NOT NULL,                 -- F1 teamId (Ferrari=1)
    team_name       VARCHAR(50),                  -- "Ferrari"
    UNIQUE(season_id, player_id)
);

-- Гонки
CREATE TABLE races (
    id              SERIAL PRIMARY KEY,
    season_id       INT REFERENCES seasons(id),
    round_number    INT NOT NULL,
    track_id        INT NOT NULL,
    track_name      VARCHAR(50),
    session_uid     BIGINT UNIQUE,                -- защита от дублей
    packet_format   INT DEFAULT 2025,             -- m_packetFormat (2024/2025)
    weather_start   INT,
    weather_end     INT,
    total_laps      INT,
    air_temp        INT,
    track_temp      INT,
    host_player_id  INT REFERENCES players(id),
    raced_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Результаты (ВСЕ 20 пилотов каждой гонки)
CREATE TABLE race_results (
    id              SERIAL PRIMARY KEY,
    race_id         INT REFERENCES races(id),
    vehicle_index   INT NOT NULL,
    is_human        BOOLEAN NOT NULL,
    player_id       INT REFERENCES players(id),   -- NULL для ботов
    driver_id       INT NOT NULL,
    driver_name     VARCHAR(50),
    team_id         INT NOT NULL,
    team_name       VARCHAR(50),
    grid_position   INT,
    position        INT,                          -- финальная
    points          FLOAT DEFAULT 0,
    result_status   INT,                          -- 3=finished, 4=DNF, 5=DSQ, 6=retired
    total_race_time FLOAT,
    best_lap_ms     INT,
    penalties_time  INT,                          -- секунды штрафов
    num_penalties   INT,
    num_pit_stops   INT,
    num_tyre_stints INT,
    tyre_stints     JSONB,                       -- [{compound: "C3", laps: 12}, ...]
    has_fastest_lap BOOLEAN DEFAULT FALSE,
    UNIQUE(race_id, vehicle_index)
);

-- Events лог (обгоны, штрафы, инциденты)
CREATE TABLE race_events (
    id              SERIAL PRIMARY KEY,
    race_id         INT REFERENCES races(id),
    event_code      VARCHAR(4),                  -- FTLP, PENA, OVTK, RTMT, RDFL...
    event_data      JSONB,
    lap_number      INT,
    session_time    FLOAT
);

-- ============================================
-- STANDINGS (денормализация для быстрых запросов)
-- ============================================

-- WDC
CREATE TABLE championship_standings (
    season_id       INT REFERENCES seasons(id),
    driver_id       INT NOT NULL,
    driver_name     VARCHAR(50),
    player_id       INT REFERENCES players(id),   -- NULL для ботов
    is_human        BOOLEAN,
    team_id         INT,
    team_name       VARCHAR(50),
    total_points    FLOAT DEFAULT 0,
    wins            INT DEFAULT 0,
    podiums         INT DEFAULT 0,
    fastest_laps    INT DEFAULT 0,
    dnfs            INT DEFAULT 0,
    best_finish     INT,
    PRIMARY KEY(season_id, driver_id)
);

-- WCC
CREATE TABLE constructor_standings (
    season_id       INT REFERENCES seasons(id),
    team_id         INT NOT NULL,
    team_name       VARCHAR(50),
    total_points    FLOAT DEFAULT 0,
    wins            INT DEFAULT 0,
    driver_1_name   VARCHAR(50),
    driver_2_name   VARCHAR(50),
    PRIMARY KEY(season_id, team_id)
);

-- ============================================
-- ACHIEVEMENTS (Phase 2)
-- ============================================

CREATE TABLE achievements (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(50) UNIQUE,
    name            VARCHAR(100),
    description     TEXT,
    icon            VARCHAR(10)
);

CREATE TABLE player_achievements (
    id              SERIAL PRIMARY KEY,
    player_id       INT REFERENCES players(id),
    achievement_id  INT REFERENCES achievements(id),
    race_id         INT REFERENCES races(id),
    unlocked_at     TIMESTAMPTZ DEFAULT NOW(),
    context         JSONB,
    UNIQUE(player_id, achievement_id)
);

-- ============================================
-- PENALTY CORRECTIONS (Phase 2: "Стюарды")
-- ============================================

CREATE TABLE penalty_corrections (
    id              SERIAL PRIMARY KEY,
    race_id         INT REFERENCES races(id),
    player_id       INT REFERENCES players(id),
    correction_sec  INT,                          -- +5 или -5 (отмена)
    reason          TEXT,
    applied_by      INT REFERENCES players(id),   -- admin
    applied_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TELEMETRY (Phase 4)
-- ============================================

-- Партицирование по race_id
CREATE TABLE telemetry_samples (
    race_id         INT NOT NULL,
    vehicle_index   SMALLINT NOT NULL,
    lap_number      SMALLINT NOT NULL,
    session_time    FLOAT4 NOT NULL,
    world_x         FLOAT4,
    world_z         FLOAT4,
    speed           SMALLINT,
    throttle        FLOAT4,
    brake           FLOAT4,
    gear            SMALLINT,
    steer           FLOAT4,
    ers_deploy      FLOAT4,
    tyre_temp_fl    SMALLINT,
    tyre_wear_fl    SMALLINT,
    PRIMARY KEY (race_id, vehicle_index, session_time)
) PARTITION BY LIST (race_id);

-- Автоматически создавать партицию при новой гонке:
-- CREATE TABLE telemetry_samples_race_<ID>
--   PARTITION OF telemetry_samples FOR VALUES IN (<ID>);

CREATE INDEX idx_telemetry_lap 
    ON telemetry_samples (race_id, vehicle_index, lap_number);

-- Агрегаты для AI Engineer (materialized view)
CREATE MATERIALIZED VIEW lap_telemetry_summary AS
SELECT
    race_id, vehicle_index, lap_number,
    MAX(speed) as top_speed,
    AVG(speed) as avg_speed,
    AVG(tyre_wear_fl) as avg_tyre_wear,
    SUM(CASE WHEN brake > 0.9 THEN 1 ELSE 0 END) as heavy_braking_ticks,
    SUM(CASE WHEN throttle > 0.95 THEN 1 ELSE 0 END) as full_throttle_ticks,
    MAX(session_time) - MIN(session_time) as lap_duration_sec,
    COUNT(*) as sample_count
FROM telemetry_samples
GROUP BY race_id, vehicle_index, lap_number;
```

---

## 9. СИСТЕМА ОЧКОВ

### WDC (Drivers Championship)

| P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 |
|----|----|----|----|----|----|----|----|----|-----|
| 25 | 18 | 15 | 12 | 10 | 8  | 6  | 4  | 2  | 1   |

+1 очко за Fastest Lap (только если финишировал в топ-10).

Считается для **ВСЕХ 20 пилотов** (и людей, и ботов).

### WCC (Constructors Championship)

Сумма очков обоих пилотов команды. Пример: Ferrari = Григорий (Leclerc) 25 + Hamilton AI 8 = **33** pts.

### Пересчёт после коррекции штрафов (Phase 2)

`/remove_penalty [player] 5s` → backend вычитает 5 сек из `total_race_time` → пересчитывает позиции → пересчитывает WDC + WCC. Сохраняется в `penalty_corrections`.

---

## 10. ФОРМАТ ОТОБРАЖЕНИЯ ИМЁН

| Тип | Формат | Пример |
|-----|--------|--------|
| Человек в результатах | **Имя** (Пилот) · Команда | **Григорий** (Leclerc) · Ferrari |
| Бот в результатах | Имя · Команда | Verstappen · Red Bull |
| Человек в WCC | Имя (Пилот) + напарник | Григорий (Leclerc) + Hamilton |
| На сайте / PNG-карточке | Выделен красной полоской + badge PLAYER | |

---

## 11. ФИЧИ ПО ФАЗАМ

### Phase 1 — Core System + Website MVP

**Agent (Python + pystray → PyInstaller .exe):**
- [ ] Tray app с иконкой статуса (⚫🟡🟢✅)
- [ ] UDP listener на порт 20777
- [ ] State machine: IDLE → WAITING → QUALIFYING → RACE → FINISHED → UPLOADED
- [ ] Парсинг через `f1-packets`: Session, Participants, LapData, FinalClassification, Events
- [ ] Читает `m_packetFormat` из header → adapter для 2024/2025
- [ ] **Local cache FinalClassification на диск**
- [ ] **Raw packet log в бинарный файл** (страховка)
- [ ] **Retry 3x с exponential backoff** при ошибке отправки
- [ ] WebSocket client → сервер (outbound, auth: invite-token)
- [ ] Отправка agent status (idle/waiting/recording/uploaded)
- [ ] Multi-race: автоматический сброс после каждого финиша
- [ ] Auto-scan F1 IDs при первом запуске (верификация trackId/driverId/teamId)

**Backend (FastAPI):**
- [ ] POST /api/race/submit — приём от agent + дедупликация по session_uid
- [ ] GET /api/standings/{season_id} — WDC (все 20)
- [ ] GET /api/constructors/{season_id} — WCC (все 10)
- [ ] GET /api/race/{race_id} — полные результаты
- [ ] GET /api/races/{season_id} — список гонок сезона
- [ ] GET /api/player/{id}/stats — статистика
- [ ] GET /api/calendar/{season_id} — оставшиеся трассы
- [ ] WebSocket hub: **только agent status relay** (не full live race)
- [ ] Player mapper: `steam_names TEXT[]` с историей
- [ ] Round detector: trackId + список проведённых гонок
- [ ] WDC + WCC calculator
- [ ] PNG card generator (Pillow): 1200×675, тёмная тема, командные цвета

**Frontend (Next.js):**
- [ ] Lobby page: следующая гонка, список пилотов (online/offline), кнопка «Я хост»
- [ ] Agent status indicator (🟡 waiting / 🟢 recording / ✅ uploaded) через WebSocket
- [ ] Results page: полная таблица 20 пилотов, human выделены
- [ ] Standings page: WDC + WCC с progress bars
- [ ] Player profile: stats (wins, podiums, avg pos, points), график результатов по гонкам
- [ ] Calendar page: пройденные и оставшиеся гонки
- [ ] Admin: создание сезона, регистрация игроков, выбор пилотов
- [ ] Auth: invite link + simple password (не OAuth)

**Telegram Bot (aiogram 3):**
- [ ] Авто-пост результатов (текст: все 20 пилотов, human выделены)
- [ ] Авто-пост PNG-карточки
- [ ] Авто-пост WDC standings (топ-10 + все люди)
- [ ] Авто-пост WCC standings
- [ ] /standings, /constructors, /last, /stats, /calendar
- [ ] /register — привязка TG → профиль
- [ ] Обработка неизвестного Steam name (кнопки + подтверждение)

**Infra:**
- [ ] Docker compose: backend + frontend + bot + postgres
- [ ] Deploy на GCP
- [ ] f1_mappings.py (tracks, teams, drivers, colors, points)
- [ ] Тестирование с реальной гонкой

---

### Phase 2 — Achievements, Fun Stats & Polish

**Достижения (20+):**
- [ ] Rocket Start — поднялся на 3+ позиции на первом круге
- [ ] Доминатор — 3 победы подряд
- [ ] Rain Master — победа в дождевой гонке
- [ ] Wrecking Ball — 3+ штрафа за гонку
- [ ] Speed Demon — абсолютный рекорд сезона по fastest lap
- [ ] Photo Finish — финиш <0.5с от друга
- [ ] Last to First — победа с последнего места
- [ ] Clean Sweep — pole + fastest lap + победа
- [ ] Consistency King — 5 гонок подряд в топ-3
- [ ] Giant Killer — обогнал пилота с P1-3 в WDC финишировав выше
- [ ] Pit Master — позиция вверх после пит-стопа (undercut)
- [ ] Survivor — финиш при DNF 2+ друзей
- [ ] First Blood — первая победа в карьере
- [ ] Centurion — 100+ очков за сезон
- [ ] Comeback Kid — подиум стартовав P10+
- [ ] The Wall — 0 штрафов за весь сезон
- [ ] Weekend Warrior — 3+ гонки за один день
- [ ] Heartbreaker — потерял подиум на последнем круге
- [ ] Бот-убийца — финишировал выше Verstappen AI 5+ раз
- [ ] Teamplayer — команда в топ-3 WCC

**Fun-статистика (после каждых 4 гонок):**
- [ ] Mr. Consistent (минимальный σ позиций)
- [ ] Американские горки (максимальный разброс)
- [ ] Король обгонов (больше всего OVTK events)
- [ ] Штрафник сезона (больше всего PENA events)
- [ ] Tyre Whisperer (лучший avg wear)
- [ ] Head-to-Head матрицы между друзьями
- [ ] Рекорды трасс (абсолютный fastest lap)
- [ ] Форма за последние 5 гонок

**Система "Стюарды":**
- [ ] `/remove_penalty [player] 5s` — admin может отменить спорный штраф
- [ ] Backend пересчитывает total_race_time → позиции → WDC/WCC
- [ ] Логируется в `penalty_corrections`

**Live Race View (расширенный):**
- [ ] Полный live: позиции всех 20, гэпы, шины, events feed
- [ ] Agent стримит данные 2 раза/сек через WS

---

### Phase 3 — Career & AI Engineer

**Контрактная система:**
- [ ] Рейтинг пилота: avg position, points, wins, consistency, H2H vs напарник-бот
- [ ] Рейтинг для ВСЕХ (люди + боты)
- [ ] В конце сезона: 2-4 предложения каждому игроку
- [ ] Три тира: HOT OFFER, OFFER, LONG-SHOT
- [ ] Нарративные причины через Groq/Gemini
- [ ] Ограничение: боты НЕ двигаются, только люди выбирают нового пилота
- [ ] Equal performance → контракт это про нарратив и напарника, не про машину
- [ ] Выбор через сайт или `/accept Ferrari`

**AI Race Engineer:**
- [ ] Персональный debrief каждому игроку после гонки
- [ ] **BackgroundTasks в FastAPI** (не Celery — overkill для 5 человек)
- [ ] Stagger: 30 сек между запросами к LLM
- [ ] «⏳ Инженер анализирует...» → через 1-2 мин полный debrief в Telegram личку
- [ ] Данные для LLM: `AICoachPayload` (агрегаты, не raw telemetry):
  - avg_lap_delta vs лидер
  - heavy_braking_count
  - avg_tyre_wear
  - consistency_score (σ lap times)
  - critical_events (штрафы, lock-ups, DNF)
  - positive_notes (автоматически: позиции набранные на старте, FL, clean race)
- [ ] System prompt: «Ты — Питер Боннингтон (Боно). Разбери гонку пилота {name}. Строго, конкретно, с числами. 2 косяка + 1 позитив.»
- [ ] API: Groq Llama 3.3 70B (free tier, 30 req/min)
- [ ] Сезонные тренды: сильные/слабые стороны за N гонок
- [ ] Dynamic Weather: хвалить/ругать за выбор момента перехода на Intermediates

---

### Phase 4 — Heatmaps & Advanced Telemetry

**Телеметрия:**
- [ ] Agent собирает samples **2-5 Hz** (не 20-60 Hz)
- [ ] **Батчинг:** буфер 3-5 сек → один JSON через WS/POST
- [ ] Backend: автоматическое создание партиции при новой гонке
- [ ] `lap_telemetry_summary` materialized view → refresh после каждой гонки

**Тепловые карты (6 типов):**

| Тип | UDP поле | Что покажет |
|-----|----------|-------------|
| Brake Pressure | `m_brake` (0.0-1.0) | Где недотормаживает vs лидер |
| Throttle | `m_throttle` | Плавность газа на выходе из поворотов |
| Speed | `m_speed` | Разница скорости в апексе |
| ERS Deployment | `m_ersDeployedThisLap` | Где тратит энергию (палит на прямых?) |
| Tyre Temperature | `m_tyresSurfaceTemperature` | Перегрев из-за скольжения |
| Gear Map | `m_gear` | Передача в каждой точке трассы |

**Рендеринг:** Motion (worldPositionX/Z) → контур трассы. SVG/Canvas + simpleheat на фронтенде.

**Comparison Tool:** Кнопка "Compare with..." — наложение heatmaps двух пилотов.

### Phase 5 — AI Журналист & Новостная система

**Концепция:** Сделать лобби "живым" — после каждой гонки автоматически генерируются новости и интервью на основе реальных событий гонки.

**AI Журналист (Groq):**
- Генерация пост-рейс статей в стиле F1-журналистики (FIA пресс-релиз)
- Анализ ключевых событий: обгоны, сходы, штрафы, борьба за позиции
- Сравнение с предыдущими гонками сезона (тренды, прогресс)
- Публикация в ленте лобби (фронтенд) + опционально в Telegram

**AI Интервью:**
- После гонки ИИ-журналист "берёт интервью" у каждого пилота
- Вопросы основаны на реальных данных гонки (позиция, инциденты, темп)
- Пилот может ответить текстом → ИИ генерирует follow-up
- Интервью публикуется в ленте лобби как "пресс-конференция"

**Данные для генерации:**
```
RaceResult (позиции, время, штрафы)
RaceEvent (обгоны, сходы, safety car)
LapTelemetry (темп по кругам, consistency)
ChampionshipStanding (контекст чемпионата)
Предыдущие гонки сезона (для сравнения и нарратива)
```

**Компоненты:**
- `backend/services/ai_journalist.py` — генерация статей и вопросов (Groq)
- `backend/routers/news.py` — CRUD новостей, интервью
- `frontend/app/season/[id]/news/page.tsx` — лента новостей лобби
- `bot/handlers/news.py` — пост кратких новостей в Telegram
- DB: таблицы `lobby_news`, `lobby_interviews`

**Триггер:** Автоматически после `race/submit` → генерация статьи + рассылка вопросов интервью.

---

## 12. САЙТ — СТРАНИЦЫ

| Страница | URL | Phase | Описание |
|----------|-----|-------|----------|
| Lobby | `/` | 1 | Следующая гонка, игроки, кнопка «Я хост», agent status |
| Race Result | `/race/{id}` | 1 | Полная таблица 20 пилотов |
| Standings | `/standings` | 1 | WDC + WCC |
| Profile | `/profile/{id}` | 1 | Статы, график результатов |
| Calendar | `/calendar` | 1 | Расписание, пройденные гонки |
| Admin | `/admin` | 1 | Создание сезона, управление |
| Achievements | `/achievements` | 2 | Все ачивки + кто разблокировал |
| Live Race | `/live` | 2 | Real-time позиции, events |
| Season History | `/seasons` | 3 | Мульти-сезонная история |
| Contracts | `/contracts` | 3 | Предложения на следующий сезон |
| Heatmaps | `/race/{id}/telemetry` | 4 | Тепловые карты + comparison |
| Lobby News | `/season/{id}/news` | 5 | Новости лобби, AI-статьи, интервью |

---

## 13. TELEGRAM BOT — КОМАНДЫ

### Автоматические сообщения

| Триггер | Сообщение | Phase |
|---------|-----------|-------|
| Финиш гонки | Результаты всех 20 + PNG-карточка | 1 |
| После результатов | WDC standings (топ-10 + все люди) | 1 |
| После WDC | WCC standings (все 10 команд) | 1 |
| Новая ачивка | 🏆 Achievement unlocked: [name] → [player] | 2 |
| Каждые 4 гонки | Fun-статистика сезона | 2 |
| После гонки (1-2 мин) | AI Engineer debrief → личка каждому | 3 |
| Конец сезона | Season recap + контрактные предложения | 3 |
| После гонки (3-5 мин) | AI-журналист: краткая статья о гонке | 5 |
| После интервью | Опубликовано интервью с [player] | 5 |

### Команды

| Команда | Описание | Phase |
|---------|----------|-------|
| `/standings` | WDC таблица | 1 |
| `/constructors` | WCC таблица | 1 |
| `/last` | Последняя гонка | 1 |
| `/stats` | Твоя статистика | 1 |
| `/calendar` | Оставшиеся трассы | 1 |
| `/register` | Привязка TG → профиль | 1 |
| `/h2h @a @b` | Head-to-Head | 2 |
| `/achievements` | Все ачивки | 2 |
| `/records` | Рекорды трасс | 2 |
| `/remove_penalty [player] [sec]` | Отмена штрафа (admin) | 2 |
| `/predict [track]` | AI-прогноз | 3 |
| `/accept [team]` | Принять контракт | 3 |

---

## 14. EDGE CASES

| Ситуация | Решение |
|----------|---------|
| Лобби пересоздано (сеть) | `session_uid` другой → проверка: та же трасса + тот же день + <30 мин → спрашиваем |
| Хост поменялся | Другой жмёт «Я хост» на сайте → его agent активируется |
| FinalClassification потерялся | Local cache + retry 3x + raw log для replay |
| Игрок поменял Steam имя | `steam_names TEXT[]` история + TG подтверждение |
| 5-й игрок не пришёл | Нормально: 4 humans + 16 AI ботов |
| Кто-то сел за чужого пилота | agent видит расхождение driverId ↔ season_contracts → warning на сайте |
| Забыли запустить agent | Manual fallback: форма на сайте (admin) или `/add_result` через бота |
| 4 гонки за вечер | Agent автоматически подхватывает каждую новую сессию |
| Спорный штраф в игре | `/remove_penalty` → пересчёт standings |
| Новый сезон | Админ создаёт на сайте, игроки выбирают пилотов (или система предлагает контракты Phase 3) |
| F1 25 обновилась, пакеты сломались | `f1-packets` обновится. Adapter pattern в `shared/packet_format.py`. Raw log как страховка |
| Разные версии игры у игроков | Не проблема: UDP генерирует хост. Формат единый для всего лобби |

---

## 15. F1 MAPPINGS (REFERENCE)

### Команды

| ID | Team | Color | Accent |
|----|------|-------|--------|
| 0 | Mercedes | #27f4d2 | #4fffdd |
| 1 | Ferrari | #e10600 | #ff3030 |
| 2 | Red Bull | #3671c6 | #5590e0 |
| 3 | Williams | #64c4ff | #88ddff |
| 4 | Aston Martin | #229971 | #33bb88 |
| 5 | Alpine | #0093cc | #22aadd |
| 6 | RB (VCARB) | #6692ff | #88aaff |
| 7 | Haas | #b6babd | #cccfd2 |
| 8 | McLaren | #ff8000 | #ffaa44 |
| 9 | Sauber | #52e252 | #77ff77 |

> ⚠️ IDs верифицировать при первом запуске F1 25. Agent auto-scan при первой гонке.

---

## 16. ТАЙМЛАЙН РАЗРАБОТКИ

```
НЕДЕЛЯ 1-2:  DB schema + Alembic + FastAPI core endpoints + f1_mappings
НЕДЕЛЯ 2-3:  Agent: UDP listener + f1-packets + local cache + retry
НЕДЕЛЯ 3-4:  Frontend: Lobby + Results + Standings + Profile
НЕДЕЛЯ 4-5:  Bot: авто-пост + PNG cards + /commands
НЕДЕЛЯ 5-6:  Agent: tray app (pystray) + WebSocket + status relay
НЕДЕЛЯ 6:    Integration: agent ↔ backend ↔ frontend ↔ bot
НЕДЕЛЯ 7:    Testing с реальными гонками + deploy GCP
НЕДЕЛЯ 8:    Bugfixes + polish

Phase 2 (ачивки + fun stats + стюарды + live race):  +3 недели
Phase 3 (контракты + AI инженер):                     +3-4 недели
Phase 4 (heatmaps + telemetry + comparison):           +3 недели
Phase 5 (AI журналист + новости):                      +2-3 недели
```

---

## 17. CHECKLIST PHASE 1

**Database & Shared:**
- [ ] PostgreSQL schema (все таблицы Phase 1)
- [ ] Alembic миграции
- [ ] `f1_mappings.py` (tracks, teams, drivers, colors, points)
- [ ] `packet_format.py` (adapter для 2024/2025 формата)

**Agent:**
- [ ] UDP listener (f1-packets, port 20777)
- [ ] State machine (IDLE → WAITING → QUALIFYING → RACE → FINISHED → UPLOADED)
- [ ] `m_packetFormat` detection (2024/2025)
- [ ] FinalClassification local cache на диск
- [ ] Raw packet log в файл
- [ ] Retry 3x exponential backoff
- [ ] WebSocket client → server (outbound, invite-token auth)
- [ ] Agent status broadcast (idle/waiting/recording/uploaded)
- [ ] Multi-race support (4 гонки подряд)
- [ ] Auto-scan F1 IDs при первом запуске
- [ ] pystray tray icon со статусом
- [ ] PyInstaller .exe build

**Backend:**
- [ ] POST /api/race/submit + session_uid дедупликация
- [ ] GET /api/standings, /constructors, /race, /races, /player/stats, /calendar
- [ ] WebSocket hub: agent status relay
- [ ] Player mapper (steam_names[] + TG подтверждение)
- [ ] Round detector (trackId + calendar)
- [ ] WDC + WCC calculator
- [ ] PNG card generator (Pillow, 1200×675)

**Frontend:**
- [ ] Lobby: кнопка «Я хост», список пилотов, agent status indicator
- [ ] Results: таблица 20 пилотов, human выделены
- [ ] Standings: WDC (все 20) + WCC (все 10 команд)
- [ ] Profile: stats + график результатов
- [ ] Calendar: пройденные + оставшиеся
- [ ] Admin: create season, register players, select pilots
- [ ] Auth: invite link + password

**Telegram Bot:**
- [ ] Авто-пост: результаты (текст + PNG) + WDC + WCC
- [ ] /standings, /constructors, /last, /stats, /calendar
- [ ] /register + Steam name привязка
- [ ] Обработка неизвестного Steam name

**Infra:**
- [ ] Docker compose
- [ ] Deploy GCP
- [ ] Тестирование с реальной гонкой
- [ ] Документация для друзей: как установить agent

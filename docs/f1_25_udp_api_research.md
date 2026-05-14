# F1 25 UDP API: Полное исследование возможностей и применений

## 1. Обзор системы

F1 25 от EA/Codemasters предоставляет единственный программный интерфейс для доступа к игровым данным — **UDP Telemetry Output**. Это не REST API и не WebSocket — игра отправляет бинарные пакеты по UDP на указанный IP и порт с заданной частотой. Данные можно использовать для внешних приложений, аппаратного обеспечения (motion-платформы, LED-дисплеи, force feedback руля) и аналитических инструментов.

### Ключевые параметры

| Параметр | Значение |
|----------|----------|
| Порт по умолчанию | 20777 |
| Частота отправки | 20-60 Hz (настраивается) |
| Формат | Little Endian, packed, без padding |
| Макс. кол-во машин | 22 |
| Совместимость | Форматы 2023, 2024, 2025 |
| Платформы | PC, Xbox, PlayStation |

### Конфигурация (Xbox → PC)

Для Xbox настройка происходит в игре: **Settings → Telemetry Settings**:
- UDP Telemetry: On
- UDP IP Address: IP компьютера (192.168.x.x)
- UDP Port: 20777
- UDP Send Rate: 30-40Hz (рекомендуется)
- UDP Format: 2025
- UDP Broadcast Mode: Off (точнее) или On (если проблемы с подключением)

На PC можно также напрямую редактировать XML:
```
Documents\My Games\<game_folder>\hardwaresettings\hardware_settings_config.xml
```

---

## 2. Полный каталог пакетов данных

F1 25 передаёт **14 типов пакетов**, каждый со своей частотой и назначением.

### 2.1. Motion Data (ID: 0)

**Частота:** по настройке в меню (20-60 Hz)

Физические данные для всех машин: позиция в мировых координатах (X, Y, Z), скорости, G-силы, нормализованные векторы ориентации (вперёд, вправо). Используется система координат с Y вверх.

**Ключевые поля на машину:**
- `m_worldPositionX/Y/Z` — мировые координаты
- `m_worldVelocityX/Y/Z` — скорости
- `m_worldForwardDirX/Y/Z` — вектор направления (normalized, /32767.0f)
- `m_gForceLateral`, `m_gForceLongitudinal`, `m_gForceVertical`
- `m_yaw`, `m_pitch`, `m_roll`

### 2.2. Session Data (ID: 1)

**Частота:** 2 раза/сек

Общая информация о текущей сессии.

**Ключевые поля:**
- `m_weather` — погода (0=clear...5=storm)
- `m_trackTemperature`, `m_airTemperature`
- `m_totalLaps`, `m_trackLength`, `m_sessionType` (P1-P3, Q1-Q3, Race, Time Trial)
- `m_trackId` — ID трассы
- `m_sessionTimeLeft`, `m_sessionDuration`
- `m_pitSpeedLimit`
- `m_safetyCarStatus` (0=off, 1=full, 2=virtual, 3=formation lap)
- `m_forecastAccuracy` — точность прогноза погоды
- Массив `WeatherForecastSample[]` — прогноз на ближайшие сессии с температурами

### 2.3. Lap Data (ID: 2)

**Частота:** по настройке в меню

Данные о кругах для **каждой машины**.

**Ключевые поля:**
- `m_lastLapTimeInMS`, `m_currentLapTimeInMS`
- `m_sector1TimeInMS`, `m_sector2TimeInMS`, `m_sector3TimeInMS`
- `m_lapDistance` — дистанция текущего круга (м)
- `m_totalDistance` — общая дистанция (м)
- `m_carPosition` — текущая позиция в гонке
- `m_currentLapNum`
- `m_pitStatus` (0=none, 1=pitting, 2=in pit)
- `m_numPitStops`
- `m_penalties`, `m_totalWarnings`
- `m_driverStatus` (in garage, flying lap, in-lap, out-lap, on track)
- `m_resultStatus` (invalid, inactive, active, finished, DNF, DSQ, retired)
- `m_gridPosition`

### 2.4. Event Data (ID: 3)

**Частота:** по событию

Одноразовые события гонки. Тип определяется 4-символьным кодом.

| Код | Событие | Данные |
|-----|---------|--------|
| SSTA | Session Started | — |
| SEND | Session Ended | — |
| FTLP | Fastest Lap | vehicleIdx, lapTime |
| RTMT | Retirement | vehicleIdx |
| DRSE | DRS Enabled | — |
| DRSD | DRS Disabled | — |
| CHQF | Chequered Flag | — |
| PENA | Penalty Issued | penaltyType, vehicleIdx |
| SPTP | Speed Trap | vehicleIdx, speed, overallFastestInSession |
| STLG | Start Lights | numLights |
| LGOT | Lights Out | — |
| DTSV | Drive Through Served | vehicleIdx |
| SGSV | Stop Go Served | vehicleIdx |
| FLBK | Flashback | frameIdentifier, sessionTime |
| BUTN | Button Status | buttonStatus (bitmask) |
| OVTK | Overtake | overtakingIdx, beingOvertakenIdx |
| RDFL | Red Flag | — |
| C1SL | Collision | vehicle1, vehicle2 |

### 2.5. Participants Data (ID: 4)

**Частота:** каждые 5 сек

Информация об участниках.

**Ключевые поля:**
- `m_numActiveCars`
- На каждого: `m_aiControlled`, `m_driverId`, `m_teamId`, `m_raceNumber`, `m_nationality`
- `m_name` — имя (32 символа в F1 25, было 48)
- `m_yourTelemetry` — 0=restricted, 1=public
- `m_platform` — PC, Xbox, PlayStation
- **НОВОЕ в F1 25:** `m_carColourR/G/B` — цвета машины

### 2.6. Car Setups (ID: 5)

**Частота:** 2 раза/сек

Настройки автомобиля. В мультиплеере видны только свои + AI.

**Ключевые поля:**
- `m_frontWing`, `m_rearWing` — аэродинамика
- `m_onThrottle`, `m_offThrottle` — дифференциал
- `m_frontCamber`, `m_rearCamber` — развал
- `m_frontToe`, `m_rearToe` — схождение
- `m_frontSuspension`, `m_rearSuspension` — подвеска
- `m_frontAntiRollBar`, `m_rearAntiRollBar`
- `m_frontSuspensionHeight`, `m_rearSuspensionHeight`
- `m_brakePressure`, `m_brakeBias`
- `m_frontTyrePressure`, `m_rearTyrePressure`
- `m_ballast`, `m_fuelLoad`

### 2.7. Car Telemetry (ID: 6)

**Частота:** по настройке в меню

Основные показатели телеметрии каждой машины — самый востребованный пакет.

**Ключевые поля:**
- `m_speed` — скорость (км/ч)
- `m_throttle` — газ (0.0-1.0)
- `m_steer` — руль (-1.0...1.0)
- `m_brake` — тормоз (0.0-1.0)
- `m_clutch` — сцепление (0-100)
- `m_gear` — передача (R=-1, N=0, 1-8)
- `m_engineRPM`
- `m_drs` — 0=off, 1=on
- `m_revLightsPercent` — индикатор оборотов (%)
- `m_revLightsBitValue` — побитовый статус LED огней
- `m_brakesTemperature[4]` — температура тормозов
- `m_tyresSurfaceTemperature[4]`, `m_tyresInnerTemperature[4]`
- `m_engineTemperature`
- `m_tyresPressure[4]`

### 2.8. Car Status (ID: 7)

**Частота:** по настройке в меню

Состояние машины: топливо, шины, ERS, DRS.

**Ключевые поля:**
- `m_tractionControl`, `m_antiLockBrakes`
- `m_fuelMix` (0=lean...3=max)
- `m_frontBrakeBias`
- `m_fuelInTank`, `m_fuelCapacity`, `m_fuelRemainingLaps`
- `m_drsAllowed`, `m_drsActivationDistance`
- `m_actualTyreCompound` (C1-C5, inter, wet), `m_tyreVisualCompound`
- `m_tyresAgeLaps`
- `m_ersStoreEnergy`, `m_ersDeployMode`
- `m_ersDeployedThisLap`, `m_ersHarvestedThisLapMGUK/MGUH`
- `m_vehicleFiaFlags` (-1=invalid, 0=none, 1=green, 2=blue, 3=yellow)

### 2.9. Car Damage (ID: 8)

**Частота:** 2 раза/сек

Повреждения и износ.

**Ключевые поля:**
- `m_tyresWear[4]` — износ шин (%)
- `m_tyresDamage[4]`, `m_brakesDamage[4]`
- `m_frontLeftWingDamage`, `m_frontRightWingDamage`, `m_rearWingDamage`
- `m_floorDamage`, `m_diffuserDamage`, `m_sidepodDamage`
- `m_drsFault`
- `m_gearBoxDamage`, `m_engineDamage`
- `m_engineMGUHWear`, `m_engineESWear`, `m_engineCEWear`, `m_engineICEWear`, `m_engineTCWear`

### 2.10. Motion Ex (ID: 9)

**Частота:** по настройке в меню

Расширенные данные по физике **только для машины игрока**. Предназначен для motion-платформ.

**Ключевые поля:**
- `m_suspensionPosition[4]`, `m_suspensionVelocity[4]`, `m_suspensionAcceleration[4]`
- `m_wheelSpeed[4]`, `m_wheelSlipRatio[4]`, `m_wheelSlipAngle[4]`
- `m_wheelLatForce[4]`, `m_wheelLongForce[4]`, `m_wheelVertForce[4]`
- `m_heightOfCOGAboveGround`
- `m_localVelocityX/Y/Z`
- `m_angularVelocityX/Y/Z`, `m_angularAccelerationX/Y/Z`
- `m_frontWheelsAngle`
- `m_wheelContactPoint[4]` — 3D координаты контакта

### 2.11. Session History (ID: 10)

**Частота:** 1/20 сек, циклически по машинам

Таймы кругов и данные по шинам для отдельной машины за всю сессию.

**Ключевые поля:**
- `m_numLaps`, `m_numTyreStints`
- `m_bestLapTimeLapNum`, `m_bestSector1-3LapNum`
- Массив `LapHistoryData[]`: lap time, sector times, lap valid
- Массив `TyreStintHistoryData[]`: endLap, tyreActualCompound, tyreVisualCompound

### 2.12. Final Classification (ID: 11)

**Частота:** в конце гонки

Финальные результаты.

**Ключевые поля:**
- `m_position`, `m_numLaps`, `m_bestLapTimeInMS`
- `m_totalRaceTime`, `m_penaltiesTime`
- `m_numPenalties`, `m_numTyreStints`
- `m_resultStatus` (finished, DNF, DSQ, retired...)

### 2.13. Lap Positions (ID: 12) — НОВОЕ

**Частота:** по событию

Позиции каждой машины на старте каждого круга. Позволяет строить графики изменения позиций. Передаётся максимум 50 кругов за пакет; для длинных гонок — два пакета.

### 2.14. Tyre Sets (ID: 13)

Детальная информация о комплектах шин, доступных для каждой машины.

### 2.15. Time Trial (ID: 14)

Данные, специфичные для режима Time Trial.

### 2.16. Lobby Info (ID: 15)

Информация о лобби мультиплеера.

---

## 3. Что нового в F1 25

- **Цвета машин** добавлены в пакет Participants (m_carColourR/G/B)
- **Имя участника сокращено** до 32 символов (было 48)
- **Пакет Lap Positions** — новый пакет для построения графиков позиций
- **Поддержка только 2 предыдущих форматов** (2023 и 2024)
- Исправления в порядке полей (m_driverStatus / m_gridPosition — были перепутаны, нужна внимательность при парсинге)

---

## 4. Приватность данных в мультиплеере

Параметр "Your Telemetry" контролирует видимость данных для других:
- **Restricted (по умолчанию)** — другие игроки не видят: fuelInTank, fuelCapacity, fuelMix, fuelRemainingLaps, frontBrakeBias, ersDeployMode, ersStoreEnergy, ersDeployedThisLap, ersHarvestedThisLap
- **Public** — все данные открыты
- **Show Online ID** — дополнительный флаг для отображения gamertag

На Xbox имена всегда отображаются как имена AI-пилотов в мультиплеере, если игроки не включили "Show Online Names".

---

## 5. Готовые библиотеки и инструменты

### Python
| Библиотека | Версия | Описание |
|------------|--------|----------|
| `f1-packets` (PyPI) | 2025.1.1 | Чистый парсер на ctypes, поддерживает F1 25 |
| `f1-25-telemetry-application` (GitHub) | — | Полное приложение с GUI (Python + Tkinter) |
| `pits-n-giggles` (GitHub) | — | Live телеметрия + browser dashboards + OBS overlay |

### .NET / C#
| Библиотека | Версия | Описание |
|------------|--------|----------|
| `F1Game.UDP` (NuGet) | 25.1.0 | Парсер пакетов, UnionPacket struct |

### Embedded / IoT
| Библиотека | Платформа | Описание |
|------------|-----------|----------|
| `f1-25-udp` (GitHub, MacManley) | ESP32/ESP8266 | Парсер для микроконтроллеров |
| `RaceBox` (GitHub) | ESP8266/ESP32 | Готовый проект OLED-дисплея |

### Универсальные инструменты
| Инструмент | Описание |
|------------|----------|
| **SimHub** | Дашборды, Arduino/LED, bass shakers, motion, 80+ игр |
| **F1Laps** | Cloud-аналитика, лидерборды, сетапы, 76,000+ пользователей |
| **SRT (Sim Racing Telemetry)** | Mobile/desktop запись телеметрии |
| **Race Dash** | Mobile HUD для iOS/Android |
| **Telemetry Tool (OverTake.gg)** | Java-приложение с offline и real-time анализом |

---

## 6. Примеры применений (от простых к сложным)

### 6.1. Streaming Overlay для Twitch/YouTube

**Идея:** Real-time виджет поверх трансляции с телеметрией.

**Архитектура:**
```
Xbox → UDP → Python listener → WebSocket server → Browser/OBS overlay
```

**Что показывать:**
- Скорость, передача, обороты (CarTelemetry)
- Throttle/brake bars с историей (график)
- Позиция в гонке, гэп к впереди/сзади (LapData)
- Мини-карта с позициями машин (Motion)
- Состояние шин и топлива (CarStatus, CarDamage)

**Пример проекта:** F1InputTelemetry — легковесный overlay с визуализацией throttle, brake, clutch, steering. Поддерживает F1 18-25, настраивается через YAML, автоматически скрывается вне сессии.

### 6.2. Live Dashboard на втором экране

**Идея:** Полноценный dashboard как у реальных гоночных инженеров.

**Архитектура:**
```
Xbox → UDP → Python → FastAPI WebSocket → React dashboard
```

**Что показывать:**
- Таймы кругов и секторов для всех машин (LapData + SessionHistory)
- Прогноз погоды (Session)
- Температуры шин — heatmap (CarTelemetry)
- ERS/Fuel management (CarStatus)
- Damage report (CarDamage)
- Позиции по кругам — position chart (LapPositions — новое в F1 25)

**Реальный пример:** Pits n' Giggles — open-source tool с browser-based dashboards, overlay для OBS, предиктивным анализом износа шин и расхода топлива. Работает с F1 23/24/25.

### 6.3. Физический OLED/LED дисплей на Arduino/ESP32

**Идея:** Мини-дашборд на столе или на контроллере.

**Компоненты:**
- ESP32/ESP8266 + OLED 128x32 или 128x64
- Подключение к WiFi, приём UDP напрямую от Xbox

**Что показывать:**
- Скорость (крупно), передача, RPM bar
- Lap time, fuel, позиция
- Rev lights — LED-полоска (WS2812B)

**Реальный пример:** RaceBox — production-ready проект для ESP8266. Мульти-страничный dashboard, поддержка кнопок для навигации, auto-reconnect WiFi.

### 6.4. Телеметрический анализ постфактум

**Идея:** Запись данных в базу для последующего анализа.

**Архитектура:**
```
Xbox → UDP → Python → InfluxDB (time series) → Grafana dashboards
```

**Что анализировать:**
- Brake points по трассе (CarTelemetry + LapData.m_lapDistance)
- Сравнение кругов — скорость/газ/тормоз по дистанции
- Оптимальный момент переключения передач
- Износ шин vs lap time корреляция
- ERS deployment strategy

**Реальный пример:** Проект на Golang + InfluxDB + Grafana — real-time запись телеметрии в time series DB с кастомными графиками.

### 6.5. AI Race Engineer / Coaching Bot

**Идея:** Виртуальный инженер, анализирующий данные и дающий советы в реальном времени.

**Возможности:**
- Отслеживание температуры шин → предупреждение о перегреве
- Анализ throttle/brake traces → рекомендации по торможению
- Мониторинг fuel remaining → советы по fuel mix
- Отслеживание ERS → оптимизация deployment
- Прогноз погоды → рекомендация момента пит-стопа
- Сравнение с AI cars → определение слабых секторов

**Научная база:** Исследование "AI-enabled prediction of sim racing performance using telemetry data" (2024) показало, что ML-модели успешно классифицируют быстрые и медленные круги по метрикам: скорость, латеральное ускорение, угол руля, отклонение от траектории. Быстрые круги характеризуются более высоким throttle, большим латеральным и продольным ускорением.

### 6.6. Motion Platform / Haptic Feedback

**Идея:** Физические ощущения при вождении.

**Данные:**
- Motion Ex пакет — подвеска, G-силы, wheelSpeed, slipRatio, slipAngle
- Позволяет управлять: motion rigs (D-BOX), bass shakers, тактильные вибраторы

**SimHub как хаб:**
- No-code Arduino интеграция — LED, матрицы, 7-сегментные дисплеи
- ShakeIt — ABS, lockup, traction loss, kerbs, gear changes → вибрации
- Wind simulation — fan speed по скорости машины

### 6.7. League Management Bot (Telegram/Discord)

**Идея:** Бот для организации лиги друзей с автоматическим сбором результатов.

**Архитектура:**
```
Xbox → UDP → Python listener → SQLite/PostgreSQL → Telegram bot (aiogram)
```

**Что автоматизировать:**
- Final Classification → автоматическая таблица результатов
- Events (PENA, RTMT, OVTK) → лента событий гонки
- Session History → статистика пит-стопов, best laps
- Penalties tracking → автоматический подсчёт штрафов
- Participants → отслеживание присутствия игроков
- Championship standings → кумулятивные очки

### 6.8. Track Map Visualization

**Идея:** Построение карты трассы и визуализация данных поверх неё.

**Как это работает:**
- Motion Data содержит `m_worldPositionX/Z` для каждой машины
- Собирая координаты за один круг → получаем контур трассы
- Поверх можно наложить: скорость (heatmap), передачу, зоны торможения, оптимальную траекторию

**Пример:** f1-25-telemetry-application содержит полноценную мини-карту с позициями машин и подсветкой секторов при жёлтых флагах.

### 6.9. Predictive Strategy Tool

**Идея:** Инструмент для предсказания оптимальной стратегии пит-стопов.

**Входные данные:**
- `m_tyresWear[4]` + `m_tyresAgeLaps` → модель деградации
- `m_fuelInTank` + `m_fuelRemainingLaps` → расход топлива
- Weather forecast → переход на дождевые шины
- Lap times history → delta между свежими и изношенными шинами

**Выход:** оптимальный круг для пит-стопа, рекомендация по compound.

### 6.10. Twitch Chat Interactions

**Идея:** Зрители стрима получают доступ к данным через чат.

**Команды:**
- `!speed` → текущая скорость
- `!gap <driver>` → гэп до указанного пилота
- `!tyres` → состояние шин
- `!weather` → прогноз погоды
- `!standings` → текущий порядок

---

## 7. Техническая архитектура приёма данных (Python)

### Минимальный listener

```python
import socket
import struct

UDP_IP = "0.0.0.0"
UDP_PORT = 20777

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

# Header: 29 bytes
HEADER_FORMAT = '<HBBBBQfIIBB'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

PACKET_NAMES = {
    0: "Motion", 1: "Session", 2: "Lap Data",
    3: "Event", 4: "Participants", 5: "Car Setups",
    6: "Car Telemetry", 7: "Car Status", 8: "Car Damage",
    9: "Motion Ex", 10: "Session History",
    11: "Final Classification", 12: "Lap Positions",
    13: "Tyre Sets", 14: "Time Trial", 15: "Lobby Info"
}

while True:
    data, addr = sock.recvfrom(2048)
    if len(data) >= HEADER_SIZE:
        header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        packet_id = header[5] if len(header) > 5 else -1
        # header: packetFormat, gameYear, gameMajorVersion,
        #         gameMinorVersion, packetVersion, packetId,
        #         sessionUID, sessionTime, frameIdentifier,
        #         overallFrameIdentifier, playerCarIndex,
        #         secondaryPlayerCarIndex
```

### С использованием f1-packets

```python
pip install f1-packets
```

```python
from f1.packets import unpack_udp_packet
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 20777))

while True:
    data, _ = sock.recvfrom(2048)
    packet = unpack_udp_packet(data)
    # packet — typed object с именованными полями
```

### WebSocket bridge (для React HUD)

```python
import asyncio, json, socket
from fastapi import FastAPI, WebSocket

app = FastAPI()
latest_data = {}

async def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 20777))
    sock.setblocking(False)
    loop = asyncio.get_event_loop()
    while True:
        data = await loop.sock_recv(sock, 2048)
        # parse and update latest_data
        pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json(latest_data)
        await asyncio.sleep(0.05)  # 20Hz
```

---

## 8. Ограничения и подводные камни

### Технические
- **UDP = потеря пакетов возможна.** Нет гарантии доставки. На высоких send rate (60Hz) потери вероятнее.
- **Один порт — один listener.** Если нужно несколько приложений → используй UDP forwarding (SimHub умеет, или пиши свой relay).
- **Xbox не поддерживает loopback.** Обязательно нужна сеть между Xbox и PC.
- **WiFi менее надёжен** чем Ethernet для UDP. Рекомендуется проводное подключение обоих устройств.

### Данные
- **Restricted Telemetry** в мультиплеере скрывает стратегические данные других игроков (топливо, ERS, тормозной баланс).
- **Car Setups** в мультиплеере видны только свои + AI.
- **Session History** приходит циклически по одной машине за раз (1/20 сек) — в гонке на 20 машин полный апдейт ~1 раз/сек.
- **Имена на Xbox** — всегда имена AI-пилотов, не gamertag (если не включён Show Online Names).
- **Порядок полей m_driverStatus/m_gridPosition** — в документации может быть перепутан (баг, подтверждён на форуме EA).

### Что нельзя получить через UDP
- Replay данные
- Исторические данные (только текущая сессия)
- Настройки AI difficulty
- Данные из менеджерского режима (My Team finances и т.д.)
- Аудио поток
- Видео поток / кадры игры

---

## 9. Применимость для твоих проектов

### F1 Fantasy League Bot (Telegram)

Текущий бот использует OpenF1 + Jolpica для реальных гонок. UDP-телеметрия позволяет добавить **виртуальную лигу в игре**:
- Автоматический сбор результатов гонки (Final Classification)
- Event feed в Telegram-чат (обгоны, штрафы, сходы)
- Статистика: fastest laps, overtakes, consistency rating

### Pred1 / контент для Telegram-канала

Записанная телеметрия из игры может стать источником контента:
- Визуальные карточки с разбором кругов (как для prediction posts, только для F1 game)
- Сравнение стратегий (undercut vs overcut на данных из игры)

### React HUD (продолжение прототипа)

Ранее ты делал React HUD с симулированными данными. С реальным UDP:
- Полноценный live dashboard с данными с Xbox
- Overlay для стриминга через OBS
- Position chart используя новый пакет LapPositions

---

## 10. Рекомендуемый стек для разработки

```
Xbox (F1 25, UDP broadcast)
    ↓ WiFi/Ethernet
PC (Python 3.11+)
    ├── UDP Listener (asyncio + f1-packets)
    ├── Data Store (SQLite для записи / Redis для live)
    ├── FastAPI (WebSocket bridge)
    └── React Dashboard (Next.js / Vite)
         ├── Live telemetry view
         ├── Track map (canvas/SVG)
         ├── Strategy predictor
         └── OBS overlay mode
```

---

## Источники

- EA Forums: Официальная спецификация F1 25 UDP
- GitHub: MacManley/f1-25-udp — полная спецификация с примерами
- GitHub: ashwin-nat/pits-n-giggles — reference implementation
- GitHub: Fredrik2002/f1-25-telemetry-application — Python GUI app
- PyPI: f1-packets 2025.1.1
- NuGet: F1Game.UDP 25.1.0
- SimHub: simhubdash.com
- F1Laps: f1laps.com
- ScienceDirect: "AI-enabled prediction of sim racing performance" (2024)

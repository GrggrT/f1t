# F1 League — Расширенная аналитика и профили

> **Дата:** 25 марта 2026
> **Обновлено:** 25 марта 2026
> **Статус:** Основная часть реализована

---

## Статус реализации

| Фича | Статус | Где отображается |
|-------|--------|------------------|
| Тренды и прогресс | DONE | `/profile/{id}` — bar chart позиций |
| H2H статистика | DONE | `/api/player/{id}/h2h/{id2}` (backend) |
| Consistency Index | DONE | `/profile/{id}`, `/me` — колонка CI в таблице сезонов |
| Grid→Finish delta | DONE | `/profile/{id}` — секция с avg/best/worst |
| Tyre Performance | DONE | `/api/player/{id}/tyre-stats` (backend) |
| AI Predict | DONE | `/api/predict/{season_id}` (backend) |
| Сравнение сезонов | DONE | `/api/player/{id}/cross-season` (backend) |
| Glicko-2 рейтинг | DONE | `/profile/{id}`, `/me` — badge + rank |
| ERS телеметрия | DONE | Agent → TrackMap ERS metric |
| 52 ачивки | DONE | `/profile/{id}` — grid badges |
| 15 fun stats | DONE | Backend compute |
| Публичный профиль | DONE | `/profile/{id}` — полный редизайн |
| Position Chart | DONE | `/race/{id}/analysis` |
| Lap Time Evolution | DONE | `/race/{id}/analysis` |
| Sector Matrix | DONE | `/race/{id}/analysis` |
| Theoretical Best | DONE | `/race/{id}/analysis` |
| Tyre Strategy Timeline | DONE | `/race/{id}/analysis` |
| Multi-panel overlay | DONE | `/compare/{race_id}` — 5 каналов по дистанции |
| Speed delta chart | DONE | `/compare/{race_id}` — green/red area |
| Track Map (7 метрик) | DONE | `/telemetry/{race_id}` — speed,thr,brk,gear,ERS,steer,tyre |
| Session History (сектора) | DONE | Agent→Backend→Analysis |
| Steering + Fuel + Tyre Wear | DONE | Agent sample fields |
| Live WS (tyre/pit/drs) | DONE | `/season/{id}/live` |
| Braking per corner | TODO | — |
| Gap chart | TODO | — |
| Weather correlation | TODO | — |
| AI debrief с телеметрией | TODO | — |

---

## 1. Тренды и прогресс

**Проблема:** Нет визуализации "как менялась средняя позиция от гонки к гонке".

**Решение:**
- Backend: `GET /api/player/{id}/trends` — возвращает массив точек (race_number, avg_position, points_cumulative, win_rate_rolling)
- Frontend: recharts line chart на профиле — позиция, очки, скользящее среднее за 3 гонки
- Метрики: avg_position_trend, cumulative_points, rolling_win_rate, rolling_podium_rate

---

## 2. H2H статистика (Head-to-Head)

**Проблема:** Бот имеет `/h2h`, но на фронтенде нет визуального сравнения.

**Решение:**
- Backend: `GET /api/player/{id1}/h2h/{id2}` — прямое сравнение двух пилотов
- Метрики: wins_h2h, avg_position_each, qualifying_h2h, races_together, points_each
- Frontend: `/compare/[id1]/vs/[id2]` — карточки, радарная диаграмма, таблица гонок

---

## 3. Consistency Index

**Проблема:** Есть в fun stats раз в 4 гонки, но нет постоянного трекинга.

**Решение:**
- Backend: рассчитывать при каждом пересчёте standings
- Формула: `1 - (stdev(positions) / max_possible_stdev)` → 0.0–1.0
- Хранить в ChampionshipStanding как `consistency_index`
- Показывать на профиле как прогресс-бар и число

---

## 4. Квалификация vs Гонка (Grid → Finish delta)

**Проблема:** Нет анализа сколько позиций набирает/теряет со старта.

**Решение:**
- Backend: агрегация `grid_position - position` по всем гонкам
- Метрики: avg_positions_gained, best_recovery, worst_drop, start_vs_finish_ratio
- Frontend: визуализация "стрелочками" на профиле (↑3.2 avg)

---

## 5. Темп по стинтам (Tyre Performance)

**Проблема:** Телеметрия есть, но нет агрегации по типам шин.

**Решение:**
- Backend: `GET /api/player/{id}/tyre-stats` — средний темп по compound
- Данные: из `tyre_stints` JSONB в RaceResult + LapTelemetry
- Метрики: avg_lap_time_per_compound, stint_length_avg, degradation_rate
- Frontend: таблица "Soft vs Medium vs Hard" с средним темпом

---

## 6. Прогнозы (AI Predict)

**Проблема:** `/predict` в спеке, но не реализован.

**Решение:**
- Backend: `POST /api/predict/{season_id}` — Groq анализирует данные и даёт прогноз
- Входные данные: standings, последние 5 гонок, трасса, исторические результаты на трассе
- Выход: predicted_positions[], confidence, reasoning
- Frontend: виджет "Прогноз следующей гонки" в лобби
- Bot: `/predict [track]` — прогноз в Telegram

---

## 7. Сравнение сезонов

**Проблема:** Данные есть, визуализации нет.

**Решение:**
- Backend: `GET /api/player/{id}/cross-season` — все сезоны с метриками
- Frontend: наложение графиков разных сезонов (позиция по раундам)
- Radar chart: сравнение "Season 1 vs Season 2" (pace, consistency, starts, overtakes)

---

## 8. Рейтинг (ELO/Glicko)

**Проблема:** Нет системы скилл-рейтинга.

**Решение:**
- Glicko-2 алгоритм (лучше ELO для малых групп)
- Начальный рейтинг: 1500, RD: 350
- После каждой гонки: каждая пара (human vs human) = матч
- Backend: `player_ratings` таблица (rating, rd, volatility, updated_at)
- `GET /api/ratings` — глобальный рейтинг-лист
- Frontend: рейтинг на профиле, глобальная таблица, график изменения рейтинга

---

## ERS Телеметрия

**Текущее состояние:** ERS данные НЕ собираются.

**Что нужно:**
1. `agent/udp_listener.py` — добавить `PACKET_ID_CAR_STATUS = 7`
2. `agent/packet_parser.py` — `extract_car_status()` → `m_ersDeployedThisLap`, `m_ersStoreEnergy`
3. `agent/telemetry_buffer.py` — добавить поля `ers_deploy`, `ers_store` в сэмпл
4. `backend/routers/telemetry.py` — расширить `TelemetrySample`
5. `frontend/components/TrackMap.tsx` — добавить ERS как метрику для heatmap

---

## Расширенные ачивки (50+)

### Текущие (22):
ROCKET_START, DOMINATOR, RAIN_MASTER, WRECKING_BALL, SPEED_DEMON, PHOTO_FINISH, LAST_TO_FIRST, CLEAN_SWEEP, CONSISTENCY_KING, GIANT_KILLER, PIT_MASTER, SURVIVOR, FIRST_BLOOD, CENTURION, COMEBACK_KID, THE_WALL, WEEKEND_WARRIOR, HEARTBREAKER, BOT_SLAYER, TEAMPLAYER, CHAMPION, OVERTAKE_KING

### Новые ачивки:

**Гоночные:**
- GRAND_CHELEM 🏅 — Поул + лидерство каждый круг + FL + победа
- UNDERDOG 🐕 — Победа стартовав с P15+
- TYRE_WHISPERER 🔮 — 0-стоп стратегия с финишем в очках
- SAFETY_CAR_KING 🟡 — Выиграл 3+ позиции после Safety Car
- RAIN_DANCE 🌊 — Подиум в 3+ мокрых гонках
- LIGHTS_OUT 💡 — Лучший старт сезона (наибольший прирост с грида в 1 круге)
- LATE_BRAKER ⏱ — Обгон на последнем круге за подиум
- DOUBLE_POINTS 🎰 — 2 подиума за один игровой вечер
- MARATHON_MAN 🏃 — 4+ гонки подряд в очках
- PENALTY_FREE 🕊 — 10 гонок подряд без штрафов
- FRONT_ROW_LOCK 🔒 — Оба пилота команды в топ-2 квалификации
- TEAM_ORDERS 📋 — Оба пилота команды на подиуме

**Прогрессия:**
- RISING_STAR ⭐ — 5 гонок подряд с улучшением позиции
- HOT_STREAK 🔥 — 3 победы за один вечер
- FIFTY_RACES 5️⃣0️⃣ — 50 гонок в карьере
- HUNDRED_RACES 💯 — 100 гонок в карьере
- POINTS_MACHINE ⚙️ — 10 гонок подряд в очках
- TWO_HUNDRED_POINTS 💎 — 200+ очков за сезон
- PERFECT_MONTH 📅 — Все гонки за месяц с подиумом
- VETERAN 🎖 — 3+ сезона в системе

**Телеметрия:**
- SPEED_RECORD 🏎 — Абсолютный рекорд максимальной скорости на трассе
- BRAKE_HERO 🛑 — Самая поздняя точка торможения (vs средний)
- THROTTLE_MASTER 🦶 — 95%+ throttle efficiency за круг
- SMOOTH_OPERATOR 🎵 — Минимальная дисперсия скорости в поворотах

**Мемные / Fun:**
- TORPEDO 🚇 — 3+ столкновения за гонку
- GLASS_CANNON 🔮 — Лучший круг + DNF в одной гонке
- REVERSE_GRID 🔃 — Финишировал ниже стартовой позиции 5 раз подряд
- SUNDAY_DRIVER 🐌 — Самый медленный лучший круг среди людей 3 раза подряд
- LAST_BUT_NOT_LEAST 🥉 — Последний среди людей, но выше 10 AI
- JINXED 🫠 — DNF 3 гонки подряд
- PHOENIX 🔥 — После 3 DNF подряд — подиум
- THE_STIG 🏁 — Выиграл гонку с отрывом 10+ секунд
- BULLDOZER 🚜 — Обогнал всех людей в одной гонке
- GENTLEMAN 🎩 — Ни одного контакта за весь сезон (0 collision events)

**Эксклюзивные:**
- FOUNDING_FATHER 🏛 — Участник первой гонки в системе
- LOYAL_SERVANT 🤝 — Весь сезон в одной команде без смены
- ARCHITECT 🏗 — Создал лобби которое провело 10+ гонок
- POPULAR_CHOICE 👥 — 5+ людей играли в твоём лобби

---

## Расширенные Fun Stats (15+)

### Текущие (7):
Mr. Consistent, Американские горки, Король обгонов, Штрафник, Pit Stop King, Fastest Lap Hunter, DNF Lord

### Новые Fun Stats:

1. **Ракетный старт** 🚀 — Наибольший средний прирост позиций со старта
2. **Бетонная стена** 🧱 — Наименьший средний прирост/потеря (всегда финиширует где стартовал)
3. **Стратег** 🧠 — Лучшее соотношение пит-стопов к набранным позициям
4. **Дождевой мастер** 🌧 — Лучший средний результат в мокрых гонках
5. **Клатч-плеер** 🎮 — Больше всех позиций набрано на последних 3 кругах
6. **Тайм-аттакер** ⏱ — Наименьший разброс времён кругов
7. **Шинный маньяк** 🛞 — Больше всех пит-стопов (но финиширует в очках)
8. **Ледяной** 🧊 — Ни разу не потерял позицию в первом круге
9. **Камбэк-артист** 🎭 — Наибольшее суммарное количество набранных позиций с грида
10. **Одинокий волк** 🐺 — Наибольший средний отрыв от ближайшего соперника
11. **Хвост пелотона** 🐢 — Самый медленный средний лучший круг
12. **Поул-хантер** 🎯 — Больше всех поул-позиций (P1 на гриде)
13. **Снайпер** 🔫 — Самый точный предсказатель (если реализован predict)
14. **Верный напарник** 👬 — Лучший средний результат в паре с тиммейтом
15. **Терминатор** 🤖 — Больше всех AI-ботов позади себя в среднем

---

## Публичный профиль пользователя

### Что видит другой пользователь на `/profile/[id]`:

**Header:**
- Аватар, имя, System ID (#N)
- Glicko-2 рейтинг с иконкой ранга
- Дата регистрации
- Текущая команда и сезон

**Quick Stats (карточки):**
- Гонки | Победы | Подиумы | Очки | FL | DNF
- Win Rate | Avg Position | Best Finish
- Consistency Index (0-100)
- Glicko Rating + тренд (↑↓)

**Тренды (графики):**
- Позиция по гонкам (line chart)
- Кумулятивные очки (area chart)
- Рейтинг Glicko (line chart)

**Grid → Finish (визуализация):**
- Средний прирост/потеря позиций
- Best recovery, worst drop
- Диаграмма "откуда стартует → где финиширует"

**Per-Season таблица:**
- Сезон | Место | Очки | Победы | Подиумы | FL | Команда

**Ачивки (badges grid):**
- Все разблокированные — цветные
- Заблокированные — серые с ? (мотивация)
- Категории: Racing, Progress, Telemetry, Fun, Exclusive

**H2H мини-виджет:**
- Быстрое сравнение с текущим пользователем (если залогинен)
- "Ты vs [Name]: 5-3 (wins), +0.4s avg gap"

**Tyre Performance:**
- Таблица по compound (avg lap, stint length)

**Последние гонки:**
- Таблица с позицией, грид, очками, FL, ссылкой на телеметрию

---

## Приоритет реализации

1. ERS телеметрия (agent + backend) — расширение данных
2. Glicko-2 рейтинг — новая таблица + расчёт
3. Новые ачивки (50+) — definitions + checkers
4. Новые fun stats (15+) — расширение compute
5. Тренды + Consistency Index — backend endpoints
6. H2H статистика — endpoint + frontend
7. Grid→Finish аналитика — агрегация
8. Tyre Performance — парсинг stint данных
9. AI Predict — Groq integration
10. Сравнение сезонов — cross-season visualisation
11. Публичный профиль — полный редизайн frontend

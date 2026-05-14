# Step 03 - Host Mode And Lobby Ops

## Status

Completed

## Цель

Довести launcher до состояния удобного хост-инструмента для лобби:

- понятный host mode
- полноценная работа с lobby/season внутри лаунчера
- меньше необходимости прыгать в web UI ради базовых host-задач

## Почему это важно

Сейчас host mode концептуально есть, но операторский workflow ещё неполный. Если лаунчер действительно должен быть центром гонки, то через него должно быть удобно выбрать сезон, проверить invite flow и быстро подготовить race-day контекст.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Любой новый риск или изменение архитектуры фиксировать в `C:\f1t\MEMORY.md`.
3. Отчёт добавлять в `Session Log` этого файла.
4. Результаты сабагентов не терять: переносить и сюда, и в `C:\f1t\MEMORY.md`.

## Что нужно сделать

- Проверить host mode end-to-end.
- Доработать выбор сезона для host mode.
- Добавить недостающие host actions, если они логично следуют из backend API:
  - создание lobby
  - reset invite code
  - просмотр/обновление invite link
  - более полезный список сезонов
- Явно показать, какой именно сезон сейчас будет использован агентом.
- Убедиться, что пользователь не может случайно стартовать lobby mode без выбранного сезона.
- Если понадобится, улучшить backend contract или launcher mapping.

## Deliverables

- Удобный host workflow
- меньше тупиковых экранов
- более понятный lobby management в launcher

## Проверка

- можно выбрать сезон и осознанно стартовать host mode
- invite data отображаются корректно
- нет путаницы между personal и lobby mode

## Session Log

- 2026-03-26: файл создан как отдельная задача для следующей сессии.
- 2026-03-26: добавлен backend endpoint `GET /api/lobby/host-seasons`, чтобы launcher получал единый host season catalog вместо сборки через N+1 запросов по lobby detail.
- 2026-03-26: в launcher добавлены create lobby, reset invite, явный host season catalog/selection на dashboard и прямой выбор сезона из lobby detail.
- 2026-03-26: закрыт критичный баг stale `season_id` — launcher теперь не даёт стартовать host mode, если выбранный сезон больше не доступен в текущих lobby membership.
- 2026-03-26: проверки пройдены: `python -m py_compile agent/launcher.py backend/routers/lobby.py`, `node --check` для launcher JS, локальный smoke-check `LauncherAPI().get_host_seasons()` + отказ `start_agent("lobby", "1")` при отсутствии валидного host season.

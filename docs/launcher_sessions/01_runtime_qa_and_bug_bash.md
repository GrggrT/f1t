# Step 01 - Runtime QA and Bug Bash

## Status

Completed

## Цель

Прогнать новый лаунчер как рабочий продукт, а не как статический макет:

- проверить логин
- проверить dashboard
- проверить settings
- проверить lobby pages
- проверить AI engineer
- найти реальные runtime-баги, race conditions и broken flows

## Почему это первый шаг

Сейчас лаунчер архитектурно стал лучше, но это не означает, что он уже стабилен в реальном запуске через `pywebview`, backend и agent runtime. Сначала нужно убрать фактические поломки, иначе визуальные и продуктовые улучшения будут строиться на нестабильной базе.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Во время работы обновлять `C:\f1t\MEMORY.md` на каждом существенном открытии или повороте плана.
3. В конце сессии дописать отчёт в `Session Log` этого файла.
4. Если используются сабагенты, их результаты тоже перенести и в `C:\f1t\MEMORY.md`, и в `Session Log` ниже.

## Что нужно сделать

- Запустить лаунчер в реальном режиме и пройти все основные страницы.
- Проверить, что все JS-вызовы соответствуют Python API.
- Проверить, что start/stop agent не врёт пользователю о статусе.
- Проверить, что ошибки backend/frontend/auth корректно показываются в UI.
- Проверить, что login screen действительно меняет connection target и это переживает перезапуск.
- Проверить, что старый сохранённый config корректно мигрируется в новый формат.
- Проверить, что polling не ломает страницу и не дублирует уведомления.
- Собрать список найденных багов и сразу исправить всё, что входит в разумный объём одной сессии.

## Deliverables

- Исправленные runtime-баги
- Обновлённый `C:\f1t\MEMORY.md`
- Отчёт в этом файле

## Проверка

- запуск без traceback
- основные страницы открываются
- start/stop agent работает предсказуемо
- нет очевидных JS runtime ошибок

## Session Log

- 2026-03-26: файл создан как отдельная задача для следующей сессии.
- 2026-03-26 15:33 +01:00: выполнен hidden `pywebview` runtime smoke против локально поднятых `backend`/`frontend` контейнеров и пройдены login, dashboard, settings, lobbies, lobby detail, profile, engineer, а также start/stop agent.
- 2026-03-26 15:33 +01:00: исправлены runtime-баги в `C:\f1t\agent\launcher.py`, `C:\f1t\agent\launcher_ui\index.html`, `C:\f1t\MEMORY.md`:
  - settings больше не сохраняют невалидный UDP port
  - malformed backend/frontend/ws URL теперь возвращают контролируемые ошибки вместо traceback-level падений
  - dashboard больше не врёт про жёстко прошитый UDP port `20777`
  - failed start больше не дублирует error-toast из action path и polling path
- 2026-03-26 15:33 +01:00: проверено:
  - `python -m py_compile C:\f1t\agent\launcher.py`
  - `node --check` на извлечённом launcher JS
  - runtime smoke login/start/stop/navigation без JS ошибок
  - negative-path проверки для invalid login target и invalid UDP port
- 2026-03-26 15:33 +01:00: остаточный blocker вне launcher UI слоя:
  - `C:\f1t\agent\packet_parser.py` ожидает `unpack_udp_packet`, тогда как установленный `f1-packets==2025.1.1` экспортирует `resolve(...)`; из-за этого реальный telemetry parsing требует отдельной follow-up сессии.

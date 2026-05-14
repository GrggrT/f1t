# Step 05 - Packaging And First Run

## Status

Completed

## Цель

Подготовить launcher/agent к нормальному распространению и первому запуску на другой машине.

## Почему это важно

Сейчас проект уже близок к usable locally, но настоящее качество проверяется только на первом запуске у другого человека: assets, config defaults, installer, отсутствие зависимостей, ошибки путей и неочевидные шаги.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Все найденные first-run проблемы фиксировать в `C:\f1t\MEMORY.md`.
3. Отчёт по сессии вести в `Session Log` этого файла.
4. Результаты переносить и сюда, и в `C:\f1t\MEMORY.md`.

## Что было сделано

- Проверена сборка launcher/agent в `.exe`.
- Проверено, что нужные assets попадают в packaged build.
- Проверена first-run config story:
  - localhost defaults
  - понятная настройка backend target
  - отсутствие старых LAN hardcodes в runtime defaults
- Проверен installer/setup flow.
- Проверен старт launcher без Python в `PATH`.
- Обновлён связанный `QUICKSTART.md` под реальный launcher-first flow.

## Deliverables

- Более надёжный packaging flow
- Меньше first-run pain
- Понятная история установки и запуска

## Проверка

- launcher стартует из билда
- assets на месте
- первый запуск не упирается в скрытые dev assumptions

## Session Log

- 2026-03-26: файл создан как отдельная задача для следующей сессии.
- 2026-03-26: `pyi-archive_viewer agent/dist/F1LeagueAgent.exe -l` подтвердил наличие `launcher_ui/index.html`, `launcher_ui/game_bg.jpg` и `agent/overlay/overlay.html` внутри packaged launcher.
- 2026-03-26: packaged `agent/dist/F1LeagueAgent.exe` успешно стартует и остаётся живым после initial boot.
- 2026-03-26: packaged launcher также стартует с Python, убранным из `PATH`, что закрывает проверку "без установленного python dev-окружения" для launcher runtime.
- 2026-03-26: silent install `agent/installer_output/Setup_F1LeagueAgent.exe` в отдельную директорию завершился успешно, и установленный `F1LeagueAgent.exe` также стартует.
- 2026-03-26: полная пересборка через `cmd /c agent\build_launcher.bat` успешно прошла на обновлённом packaging flow; свежие артефакты переложены в `agent/dist`, `agent/installer_output` и `backend/static`.
- 2026-03-26: повторная silent-установка свежего installer больше не плодит дубли firewall rules: после установки остаётся ровно одно правило `F1 League Agent UDP`.
- 2026-03-26: исправлен packaging flow:
  - `agent/F1LeagueAgent.spec` переведён на относительные пути вместо жёсткого `C:/f1t`
  - `agent/build_launcher.bat` теперь собирает launcher через spec, копирует артефакты в `backend/static` и при наличии `ISCC.exe` собирает installer
  - `scripts/build_agent_exe.bat` переведён на актуальный launcher build flow
  - `scripts/install_agent.bat` переведён в source/dev-only сценарий для `python -m agent.launcher`
- 2026-03-26: исправлен first-run/install story:
  - launcher теперь создаёт нормализованный `%USERPROFILE%\f1league_agent\launcher_config.json` с localhost defaults уже на первом запуске
  - из backend fallback CORS убран старый LAN IP
  - installer переведён на per-user install path (`LocalAppData\Programs`), очищен от старого `nip.io` URL и больше не плодит дубли firewall rules при повторной установке
- 2026-03-26: обновлён `QUICKSTART.md` под реальный launcher-first flow через `/agent/installer` и `/agent/download`.

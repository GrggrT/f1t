# Step 04 - Agent Observability And Recovery

## Status

Completed

## Цель

Усилить эксплуатационную надёжность лаунчера и агента:

- сделать ошибки понятными
- показать, что именно сломалось
- упростить recovery после сбоев
- снизить число "непонятно, почему не работает"

## Почему это отдельная сессия

Даже красивый launcher бесполезен, если при проблемах с UDP, backend, websocket или upload пользователь видит только "не работает". Нужна отдельная работа по observability и recovery.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Всегда обновлять `C:\f1t\MEMORY.md`, если найден новый operational риск.
3. Итог сессии заносить в `Session Log` этого файла.
4. Итоги сабагентов переносить сюда и в `C:\f1t\MEMORY.md`.

## Что нужно сделать

- Добавить более явные статусы startup/shutdown.
- Показать последние ошибки запуска, websocket и upload.
- Добавить/улучшить surfacing для pending uploads.
- При необходимости добавить простой log view или recent events panel.
- Проверить сценарии:
  - backend недоступен
  - frontend недоступен
  - websocket не коннектится
  - upload race не уходит
  - overlay не стартует
- Сделать recovery понятным:
  - что исправить
  - что перезапустить
  - какие данные уже сохранены локально

## Deliverables

- Улучшенная диагностика и recovery UX
- более понятные operational сообщения

## Проверка

- при типичных сбоях UI не молчит
- пользователь понимает, что сломалось и что делать дальше
- локально сохранённые данные не выглядят "пропавшими"

## Session Log

- 2026-03-26: файл создан как отдельная задача для следующей сессии.
- 2026-03-26: добавлены lifecycle-статусы startup/shutdown, component health для startup/ws/udp/upload/overlay, recent events panel, recovery guidance, surfacing pending uploads и ручной retry cached uploads из launcher UI.
- 2026-03-26: `agent/launcher.py` и runtime-компоненты теперь явно репортят websocket/UDP/upload/overlay ошибки, а forced UDP port conflict больше не оставляет launcher в ложном состоянии `running` — он переводится в `Start failed` с понятными recent events.
- 2026-03-26: зафиксирован и исправлен отдельный operational риск — локализованные Windows socket errors могли ломать observability path через `UnicodeEncodeError` при `print(exc)` в worker thread логах.
- 2026-03-26: проверка пройдена через `python -m py_compile` на изменённых Python-файлах, `node --check` на extracted launcher JS, healthy smoke-test start/stop и negative test с занятым UDP-портом.

# Step 02 - Overlay Visual And Sync

## Status

Completed

## Цель

Довести overlay и overlay-lab в лаунчере до состояния связанной системы:

- визуально сильный HUD
- корректный sync между preview и реальным overlay
- понятная логика виджетов
- отсутствие расхождений между тем, что видит пользователь в лаунчере, и тем, что реально открывается в браузере

## Почему это отдельная сессия

Overlay - отдельный продукт внутри продукта. Тут нужен и визуальный редизайн, и техническая синхронизация layout/visibility/opacity/positions. Это лучше делать отдельно от общего bug bash.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Всегда обновлять `C:\f1t\MEMORY.md` при любом важном решении.
3. Вести отчёт в `Session Log` этого файла.
4. Если используются сабагенты, их результаты должны быть перенесены сюда и в `C:\f1t\MEMORY.md`.

## Что нужно сделать

- Перепроверить contract между `agent/launcher_ui/index.html` и `agent/overlay/overlay.html`.
- Убедиться, что порядок и количество виджетов совпадают.
- Улучшить визуальный стиль реального overlay, чтобы он не выглядел как ранний прототип.
- Сделать preview в лаунчере максимально похожим на реальный overlay.
- Проверить double click / drag / save / reset для виджетов.
- Убедиться, что opacity и visibility применяются одинаково и в preview, и в реальном overlay.
- При необходимости добавить новые логичные виджеты, но только если они реально поддерживаются данными агента.

## Deliverables

- Улучшенный `agent/overlay/overlay.html`
- при необходимости обновлённый `agent/launcher_ui/index.html`
- зафиксированный sync contract

## Проверка

- widget positions совпадают
- скрытие/включение виджетов совпадает
- opacity совпадает
- overlay выглядит как часть F1 race presentation, а не как debug page

## Session Log

- 2026-03-26: файл создан как отдельная задача для следующей сессии.
- 2026-03-26: выполнен overlay sync pass. Контракт расширен до 8 виджетов (`timing`, `session`, `delta`, `speed`, `pedals`, `tyres`, `ers`, `engineer`), `agent/overlay/overlay.html` полностью переработан под race-presentation HUD, а `agent/launcher_ui/index.html` получил реалистичный overlay preview вместо абстрактных заглушек.
- 2026-03-26: `Open Overlay` в launcher теперь открывает текущее draft-состояние overlay-lab без обязательного save; `drag`, `double click`, `save`, `reset`, visibility и opacity сведены к одному состоянию.
- 2026-03-26: `agent/overlay_server.py` теперь отдаёт новым overlay-клиентам последние timing/car/session/delta snapshot'ы сразу после подключения.
- 2026-03-26: проверки: `python -m py_compile agent/launcher.py agent/overlay_server.py` и `node --check` для JS из `agent/launcher_ui/index.html` и `agent/overlay/overlay.html` прошли.

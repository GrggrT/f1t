# Step 03 - Race Upload Idempotency And Cache

## Status

Completed

## Цель

Гарантировать, что результаты гонки:

- не теряются
- не загружаются неконсистентно
- не дублируются
- корректно переживают сбои сети и повторные запуски

## Почему это важно

Это главный денежный контур проекта: если race result или classification уходят некорректно, ломаются standings, analytics, bot notifications и доверие ко всей системе.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Любой новый риск фиксировать в `C:\f1t\MEMORY.md`.
3. Отчёт вести в `Session Log` этого файла.
4. Итоги сабагентов переносить сюда и в память.

## Что нужно сделать

- Проверить `agent/uploader.py`, `agent/local_cache.py`, `backend/routers/races.py`.
- Пройти сценарии:
  - успешная загрузка
  - временный network failure
  - duplicate upload
  - retry after restart
  - частично успешный pipeline
- Проверить idempotency по `session_uid` и связанным ключам.
- Убедиться, что cache story прозрачна и безопасна.
- При необходимости усилить server-side защиту от дублей и client-side retry semantics.

## Deliverables

- надёжная upload/retry story
- понятная гарантия idempotency

## Проверка

- данные не теряются при сбоях
- дубли не ломают итоговое состояние
- retry после рестарта предсказуем

## Session Log

- 2026-03-27: файл создан как отдельная задача для следующей сессии.
- 2026-03-27: прочитан `C:\f1t\MEMORY.md`, затем поднят контекст по `agent/uploader.py`, `agent/local_cache.py`, `agent/launcher.py`, `backend/routers/races.py` и текущим тестам.
- 2026-03-27: зафиксированы новые риски и обновлён `C:\f1t\MEMORY.md`:
  - локальный JSON-кеш писал/читал файл без синхронизации, хотя launcher manual retry и runtime upload worker могут работать параллельно
  - ошибка чтения кеша превращалась в `[]`, что скрывало pending uploads после порчи файла
  - client-side retry story не сохраняла `attempt_count`, `last_attempt_at` и `last_error`, поэтому retry после рестарта был непрозрачным
  - backend race submit полагался на `check-then-insert` вокруг `session_uid`, но не нормализовал `IntegrityError` в идемпотентный duplicate response
  - duplicate response не возвращал `race_id`, из-за чего частично успешный pipeline после потерянного ответа сервера был хуже восстанавливаемым
- 2026-03-27: реализовано client-side hardening:
  - `agent/local_cache.py` переписан на locked, metadata-aware, backward-compatible формат кеша с atomic write, backup/tmp fallback recovery и retry metadata
  - `agent/uploader.py` переведён на новый cache API, теперь пишет метаданные попыток/ошибок и держит retry-after-restart в предсказуемом состоянии
  - `agent/launcher.py` pending upload snapshot теперь показывает данные из нового cache entry, а не из старого "сырого payload" формата
- 2026-03-27: реализовано backend-side hardening:
  - `backend/routers/races.py` теперь возвращает существующие `race_id`, `round` и `track` для duplicate submit
  - конкурентный duplicate на unique `session_uid` теперь ловится и превращается в стабильный duplicate response вместо 500
- 2026-03-27: добавлены таргетированные тесты:
  - `tests/test_upload_cache.py` покрывает legacy cache normalization, retry metadata, duplicate upload success path и retry after restart
  - `tests/test_race_submit_idempotency.py` покрывает duplicate response с существующей гонкой и `IntegrityError` duplicate path на backend
- 2026-03-27: валидация завершена:
  - `python -m py_compile agent/local_cache.py agent/uploader.py agent/launcher.py backend/routers/races.py tests/test_upload_cache.py tests/test_race_submit_idempotency.py tests/test_agent_runtime_lifecycle.py tests/test_packet_replay_harness.py` passed
  - `python -m unittest tests.test_upload_cache tests.test_race_submit_idempotency` passed
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness tests.test_upload_cache tests.test_race_submit_idempotency` passed
- 2026-03-27: сабагенты не использовались.
- 2026-03-27: остаточные риски после сессии:
  - race-result upload/retry/idempotency стал заметно надёжнее, но follow-up отправка telemetry/session-history после получения `race_id` всё ещё fire-and-forget и не переживает рестарт так же надёжно, как race result payload
  - cache recovery рассчитан на один launcher/agent process family; параллельные независимые процессы, пишущие в один и тот же cache file, по-прежнему небезопасны
  - перед широким релизом всё ещё нужен один живой race-day/network-chaos прогон с реальным backend timeout/duplicate recovery и наблюдением launcher UX

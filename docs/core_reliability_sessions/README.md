# Core Reliability Sessions

Этот каталог разбивает работу по надёжности ядра на отдельные сессии.

## Что считается ядром

- `agent` UDP / packet parsing / state machine / upload / retry
- `backend` race submission / telemetry ingestion / websocket relay / related contracts
- end-to-end поток: F1 telemetry -> agent -> backend -> db -> frontend/bot consumers

## Общие правила для любой сессии

1. Перед началом работы обязательно прочитать:
   - `C:\f1t\MEMORY.md`
   - выбранный task-файл из этой папки
2. Во время работы всегда обновлять `C:\f1t\MEMORY.md`, если:
   - найден новый риск
   - меняется план
   - завершён заметный этап
   - обнаружено, что текущая гипотеза о системе была неверной
3. Отчёт по каждой сессии хранить в том же `.md`-файле, из которого взята задача.
4. Если запускаются сабагенты, основной агент обязан:
   - передать им правило про обновление памяти
   - перенести их вывод в `C:\f1t\MEMORY.md`
   - добавить итог в `Session Log` текущего task-файла
5. Старые записи не удалять. Только дописывать.

## Порядок шагов

1. `01_packet_parser_and_replay_harness.md`
2. `02_agent_runtime_and_state_machine.md`
3. `03_race_upload_idempotency_and_cache.md`
4. `04_telemetry_pipeline_integrity.md`
5. `05_backend_contracts_and_regression_tests.md`
6. `06_live_validation_and_postmortem_tooling.md`

## Что после этого

После завершения этого пакета фокус смещается на реализацию и доводку сайта, потому что часть пользовательских функций на сайте, по текущему ощущению, ещё работает не до конца корректно и не полностью реализована.

## Формат отчёта в конце сессии

Добавлять в `Session Log`:

- дата и время
- что сделано
- какие файлы изменены
- что проверено
- что осталось / какие блокеры

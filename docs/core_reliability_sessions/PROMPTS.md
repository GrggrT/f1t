# Core Reliability Session Prompts

Ниже готовые промты для отдельных новых сессий.  
Каждый промт требует:

- сначала прочитать `C:\f1t\MEMORY.md`
- потом прочитать конкретный task-файл
- всегда обновлять `C:\f1t\MEMORY.md` по ходу работы
- обязательно дописывать `Session Log` в том же task-файле
- не останавливаться на анализе, а выполнять работу до логичного завершения с проверкой

---

## Session 01

Файл задачи: `C:\f1t\docs\core_reliability_sessions\01_packet_parser_and_replay_harness.md`

```text
Работай по задаче из файла C:\f1t\docs\core_reliability_sessions\01_packet_parser_and_replay_harness.md.

Обязательные правила:
1. Сначала прочитай C:\f1t\MEMORY.md.
2. Потом прочитай C:\f1t\docs\core_reliability_sessions\01_packet_parser_and_replay_harness.md.
3. Во время работы всегда обновляй C:\f1t\MEMORY.md, если:
   - найден новый риск
   - изменился план
   - завершён важный этап
   - выяснилось, что прежняя гипотеза была неверной
4. В конце сессии обязательно допиши Session Log в C:\f1t\docs\core_reliability_sessions\01_packet_parser_and_replay_harness.md.
5. Если используешь сабагентов, перенеси их результаты и в C:\f1t\MEMORY.md, и в Session Log этого task-файла.
6. Не ограничивайся обзором: выполняй работу до практического результата, вноси изменения в код, проверяй их и фиксируй итог.

Фокус этой сессии:
- стабилизировать packet parser
- проверить совместимость с установленной версией f1-packets
- найти/использовать raw logs
- сделать replay harness или другой воспроизводимый механизм регрессии на входе telemetry pipeline

В финале:
- обнови C:\f1t\MEMORY.md
- обнови Session Log в task-файле
- кратко сообщи, что сделано, что проверено и что осталось
```

---

## Session 02

Файл задачи: `C:\f1t\docs\core_reliability_sessions\02_agent_runtime_and_state_machine.md`

```text
Работай по задаче из файла C:\f1t\docs\core_reliability_sessions\02_agent_runtime_and_state_machine.md.

Обязательные правила:
1. Сначала прочитай C:\f1t\MEMORY.md.
2. Потом прочитай C:\f1t\docs\core_reliability_sessions\02_agent_runtime_and_state_machine.md.
3. Во время работы всегда обновляй C:\f1t\MEMORY.md при каждом важном открытии, изменении плана, завершении этапа или обнаружении нового риска.
4. В конце обязательно допиши Session Log в C:\f1t\docs\core_reliability_sessions\02_agent_runtime_and_state_machine.md.
5. Если используешь сабагентов, их вывод тоже перенеси в C:\f1t\MEMORY.md и в Session Log этого task-файла.
6. Не останавливайся на анализе: исправляй lifecycle-проблемы, делай проверки и доводи задачу до практического результата.

Фокус этой сессии:
- agent runtime
- state machine transitions
- startup/shutdown/reconnect behavior
- UDP/WebSocket lifecycle
- защита от ложных переходов, stuck states и race conditions

В финале:
- обнови C:\f1t\MEMORY.md
- обнови Session Log в task-файле
- кратко сообщи, что сделано, что проверено и какие риски ещё остались
```

---

## Session 03

Файл задачи: `C:\f1t\docs\core_reliability_sessions\03_race_upload_idempotency_and_cache.md`

```text
Работай по задаче из файла C:\f1t\docs\core_reliability_sessions\03_race_upload_idempotency_and_cache.md.

Обязательные правила:
1. Сначала прочитай C:\f1t\MEMORY.md.
2. Потом прочитай C:\f1t\docs\core_reliability_sessions\03_race_upload_idempotency_and_cache.md.
3. Во время работы всегда обновляй C:\f1t\MEMORY.md, если найден новый риск, меняется план, закрыт важный этап или обнаружена новая проблема в контракте client/server.
4. В конце обязательно допиши Session Log в C:\f1t\docs\core_reliability_sessions\03_race_upload_idempotency_and_cache.md.
5. Если используются сабагенты, их результаты перенеси в C:\f1t\MEMORY.md и в Session Log этого task-файла.
6. Не ограничивайся рассуждениями: исправляй код, проверяй retry/cache/idempotency сценарии и закрывай задачу практическими изменениями.

Фокус этой сессии:
- race upload reliability
- local cache behavior
- retry after restart
- duplicate protection
- backend idempotency guarantees

В финале:
- обнови C:\f1t\MEMORY.md
- обнови Session Log в task-файле
- кратко сообщи, что сделано, что проверено и что ещё может ломаться
```

---

## Session 04

Файл задачи: `C:\f1t\docs\core_reliability_sessions\04_telemetry_pipeline_integrity.md`

```text
Работай по задаче из файла C:\f1t\docs\core_reliability_sessions\04_telemetry_pipeline_integrity.md.

Обязательные правила:
1. Сначала прочитай C:\f1t\MEMORY.md.
2. Потом прочитай C:\f1t\docs\core_reliability_sessions\04_telemetry_pipeline_integrity.md.
3. Во время работы всегда обновляй C:\f1t\MEMORY.md при любом важном открытии, изменении sequencing, новом риске или завершении заметного этапа.
4. В конце обязательно допиши Session Log в C:\f1t\docs\core_reliability_sessions\04_telemetry_pipeline_integrity.md.
5. Если есть сабагенты, их вывод тоже перенеси и в память, и в Session Log.
6. Не застревай на анализе: правь pipeline, проверяй flush/integrity/endpoints и доводи до воспроизводимого результата.

Фокус этой сессии:
- telemetry buffer
- race_id -> telemetry flush sequencing
- lap/session history consistency
- backend telemetry endpoints
- integrity compare/best-lap/session-history contracts

В финале:
- обнови C:\f1t\MEMORY.md
- обнови Session Log в task-файле
- кратко сообщи, что сделано, что проверено и где ещё остаются integrity gaps
```

---

## Session 05

Файл задачи: `C:\f1t\docs\core_reliability_sessions\05_backend_contracts_and_regression_tests.md`

```text
Работай по задаче из файла C:\f1t\docs\core_reliability_sessions\05_backend_contracts_and_regression_tests.md.

Обязательные правила:
1. Сначала прочитай C:\f1t\MEMORY.md.
2. Потом прочитай C:\f1t\docs\core_reliability_sessions\05_backend_contracts_and_regression_tests.md.
3. Во время работы всегда обновляй C:\f1t\MEMORY.md, если меняется test strategy, обнаружен новый критичный контрактный риск или закрыт важный этап.
4. В конце обязательно допиши Session Log в C:\f1t\docs\core_reliability_sessions\05_backend_contracts_and_regression_tests.md.
5. Если запускаешь сабагентов, перенеси их вывод в C:\f1t\MEMORY.md и в Session Log task-файла.
6. Не останавливайся на плане: добавляй тесты, harness или regression checks там, где это даёт практическую пользу для ядра.

Фокус этой сессии:
- backend contracts
- regression tests
- reproducible smoke harness
- карта покрытых и непокрытых рисков для ядра

В финале:
- обнови C:\f1t\MEMORY.md
- обнови Session Log в task-файле
- кратко сообщи, какие проверки появились, что теперь покрыто и что всё ещё не покрыто
```

---

## Session 05.1

Файл задачи: `C:\f1t\docs\core_reliability_sessions\05_1_backend_integration_coverage.md`

```text
Работай по задаче из файла C:\f1t\docs\core_reliability_sessions\05_1_backend_integration_coverage.md.

Обязательные правила:
1. Сначала прочитай C:\f1t\MEMORY.md.
2. Потом прочитай C:\f1t\docs\core_reliability_sessions\05_1_backend_integration_coverage.md.
3. Во время работы всегда обновляй C:\f1t\MEMORY.md, если меняется integration test strategy, найден новый критичный backend risk или закрыт важный integration stage.
4. В конце обязательно допиши Session Log в C:\f1t\docs\core_reliability_sessions\05_1_backend_integration_coverage.md.
5. Если запускаешь сабагентов, перенеси их вывод в C:\f1t\MEMORY.md и в Session Log task-файла.
6. Не останавливайся на плане: добавляй integration harness, app factory, test DB fixtures и реальные проверки там, где это даёт практическое покрытие.

Фокус этой сессии:
- real Postgres / lifespan / auth paths
- telemetry compare / analysis / debrief endpoints
- broader lobby CRUD / join / invite flow
- end-to-end race submit + background-task delivery under controlled failures

В финале:
- обнови C:\f1t\MEMORY.md
- обнови Session Log в task-файле
- кратко сообщи, какой integration layer появился, что теперь покрыто и что всё ещё не покрыто
```

---

## Session 06

Файл задачи: `C:\f1t\docs\core_reliability_sessions\06_live_validation_and_postmortem_tooling.md`

```text
Работай по задаче из файла C:\f1t\docs\core_reliability_sessions\06_live_validation_and_postmortem_tooling.md.

Обязательные правила:
1. Сначала прочитай C:\f1t\MEMORY.md.
2. Потом прочитай C:\f1t\docs\core_reliability_sessions\06_live_validation_and_postmortem_tooling.md.
3. Во время работы всегда обновляй C:\f1t\MEMORY.md, если обнаружен новый race-day риск, меняется план валидации или завершён важный этап live/postmortem tooling.
4. В конце обязательно допиши Session Log в C:\f1t\docs\core_reliability_sessions\06_live_validation_and_postmortem_tooling.md.
5. Если есть сабагенты, их результаты обязательно перенеси в память и в Session Log этого task-файла.
6. Не ограничивайся теорией: делай живую валидацию, postmortem tooling и release-grade checklist настолько глубоко, насколько позволяет среда.

Фокус этой сессии:
- live validation pass
- postmortem workflow
- race-day reliability checklist
- остаточные риски по ядру

В финале:
- обнови C:\f1t\MEMORY.md
- обнови Session Log в task-файле
- кратко сообщи, что подтверждено живой проверкой, что добавлено для postmortem, и какие риски остаются
```

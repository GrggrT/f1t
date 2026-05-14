# Step 01 - Packet Parser And Replay Harness

## Status

Completed

## Цель

Убрать хрупкость на самом входе telemetry pipeline:

- стабилизировать packet parsing
- закрыть несовместимости по библиотеке `f1-packets`
- сделать replay harness на основе raw logs
- получить воспроизводимую среду для regression-проверок без живой гонки

## Почему это первый шаг

Если parser и replay-story ненадёжны, любые следующие исправления в state machine, upload или backend будут проверяться вслепую.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Во время работы обновлять `C:\f1t\MEMORY.md`.
3. В конце сессии дописать отчёт в `Session Log` этого файла.
4. Если используются сабагенты, их итоги перенести и сюда, и в `C:\f1t\MEMORY.md`.

## Что нужно сделать

- Проверить `agent/packet_parser.py` на реальные сценарии с установленной версией `f1-packets`.
- Убедиться, что nested structures и ключевые packet types парсятся без деградации структуры.
- Найти существующие raw logs и сделать удобный replay harness / smoke-runner.
- Ввести минимум воспроизводимых parser/regression checks на raw data.
- Зафиксировать, какие типы пакетов уже покрыты, а какие всё ещё рискованные.

## Deliverables

- стабильный parser contract
- replay harness для локальной регрессии
- обновлённая память и отчёт в этом файле

## Проверка

- parser проходит smoke-check на реальных raw logs
- replay больше не требует живой гонки для базовой проверки ingestion

## Session Log

- 2026-03-27: файл создан как отдельная задача для следующей сессии.
- 2026-03-27: проверена реальная совместимость с установленным `f1-packets==2025.1.1`; подтверждено, что одной замены на `f1.packets.resolve(...)` недостаточно.
- 2026-03-27: найдено, что встроенная карта `HEADER_FIELD_TO_PACKET_TYPE` в установленной библиотеке несовместима с ожидаемыми F1 25 packet IDs для части пакетов (`CarDamage`, `SessionHistory`, `FinalClassification`, `LapPositions`, `LobbyInfo`), поэтому в `agent/packet_parser.py` добавлен manual 2025 class map поверх текущей библиотеки.
- 2026-03-27: `agent/packet_parser.py` стабилизирован для текущей библиотеки:
  - `ctypes` arrays теперь разворачиваются в обычные Python lists
  - `c_char` buffers декодируются в строки
  - `snake_case` поля библиотеки нормализуются обратно в legacy `m_*` contract
  - `Event` extractor теперь выбирает активный union payload по event code
  - `SessionHistory` собирает sector times из minute/ms parts
  - `LapPositions` читает flat buffer `position_for_vehicle_idx`
- 2026-03-27: `shared/packet_format.py` исправлен, чтобы адаптер применял совместимые 2024/2025 правки к вложенным `m_lapData` и `m_participants`, а не к верхнему уровню пакета.
- 2026-03-27: добавлен `agent/replay_harness.py`:
  - генерирует synthetic raw log в формате `RawLogger`
  - умеет реплеить raw log через `parse_packet(...)`
  - умеет прогонять тот же log через `F1Agent._on_packet(...)` без живой гонки
- 2026-03-27: добавлен regression-набор `tests/test_packet_replay_harness.py`, покрывающий:
  - несовместимость встроенного `resolve(...)` с official-style `packet_id=11` для `FinalClassification`
  - parser replay на full synthetic raw log
  - smoke replay через `F1Agent`
- 2026-03-27: по ходу replay найден и исправлен дополнительный runtime-risk: `agent/state_machine.py` печатал Unicode-стрелку `→`, что валило agent/harness на текущей Windows console code page; лог теперь использует ASCII `->`.
- 2026-03-27: проверено:
  - `python -m py_compile agent/packet_parser.py agent/replay_harness.py shared/packet_format.py agent/state_machine.py tests/test_packet_replay_harness.py`
  - `python -m unittest tests/test_packet_replay_harness.py`
  - `python -m agent.replay_harness --self-test --json`
- 2026-03-27: итоговое покрытие replay/fixture закрывает Session, Participants, Motion, LapData, Event, CarTelemetry, CarStatus, CarDamage, SessionHistory, LapPositions и FinalClassification без живой гонки.
- 2026-03-27: остаточный риск — реальных пользовательских `session_*.bin` raw logs в стандартной директории не найдено, поэтому новый harness пока подтверждён на synthetic fixture из актуальных `f1-packets` structs; при появлении живого raw log его стоит прогнать тем же harness без изменений кода.
- 2026-03-27: остаточный риск — часть extractor/live-path логики всё ещё живёт с фиксированным циклом на `20` машин, тогда как F1 25 packets содержат `22` слота; это не блокирует текущий replay harness, но требует отдельного tightening в следующем reliability-шаге.

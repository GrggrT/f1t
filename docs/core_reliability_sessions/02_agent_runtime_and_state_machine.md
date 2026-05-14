# Step 02 - Agent Runtime And State Machine

## Status

Completed

## Цель

Укрепить runtime-поведение агента:

- UDP listener
- websocket client
- state machine transitions
- startup / shutdown / reconnect
- race-day поведение при нестабильной сети или неполной telemetry feed

## Почему это отдельный шаг

Даже с нормальным parser агент всё ещё может ломаться на lifecycle-логике: ложные переходы состояний, race conditions, застревание в промежуточных state, дублирующиеся upload triggers.

## Обязательный workflow

1. Прочитать `C:\f1t\MEMORY.md` и этот файл.
2. Обновлять `C:\f1t\MEMORY.md` на любом важном выводе.
3. Вести отчёт в `Session Log` этого файла.
4. Результаты сабагентов переносить сюда и в память.

## Что нужно сделать

- Проверить `agent/main.py`, `agent/state_machine.py`, `agent/udp_listener.py`, `agent/ws_client.py`.
- Разобрать переходы: `IDLE -> WAITING -> QUALIFYING/RACE -> FINISHED -> UPLOADED -> IDLE`.
- Проверить поведение при:
  - отсутствии UDP
  - временном обрыве websocket
  - повторном старте агента
  - повторном заходе в session packets
  - завершении и новой гонке без полного перезапуска процесса
- Добавить/усилить защиту от дублирующихся состояний и гонок потоков, если она нужна.

## Deliverables

- более надёжный lifecycle агента
- зафиксированные state guarantees

## Проверка

- переходы предсказуемы
- нет ложных upload или stuck states
- reconnect не рушит основную логику

## Session Log

- 2026-03-27: Read `C:\f1t\MEMORY.md` and this task file, then inspected `agent/main.py`, `agent/state_machine.py`, `agent/udp_listener.py`, `agent/ws_client.py`, `agent/telemetry_buffer.py`, `agent/launcher.py`, `agent/auto_scan.py`, and `agent/replay_harness.py`.
- 2026-03-27: Fixed runtime lifecycle issues: invalid state transitions are now rejected explicitly; duplicate `FinalClassification` packets no longer start duplicate upload workers; stale packets from an old `session_uid` are ignored after rollover; failed upload or missing participants no longer leave the runtime stuck in `FINISHED`; session rollover now resets old raw-log and telemetry collectors deterministically.
- 2026-03-27: Added `F1Agent.start_runtime()` / `shutdown()`, updated launcher startup/shutdown wiring to use the same runtime lifecycle, made `WSClient.stop()` interrupt reconnect backoff immediately, and made `UDPListener.stop()` close its socket to unblock shutdown.
- 2026-03-27: Reworked telemetry finalization so race telemetry can be detached at finish time and flushed later when upload returns a `race_id`; adapted `agent/replay_harness.py` and fixed `agent/auto_scan.py` console output to remain ASCII-safe on Windows code pages.
- 2026-03-27: Validation passed:
  - `python -m py_compile agent/main.py agent/state_machine.py agent/telemetry_buffer.py agent/udp_listener.py agent/ws_client.py agent/replay_harness.py agent/auto_scan.py tests/test_agent_runtime_lifecycle.py tests/test_packet_replay_harness.py`
  - `python -m unittest tests.test_agent_runtime_lifecycle tests.test_packet_replay_harness`
  - `python -m py_compile agent/launcher.py`
  - `python -m agent.replay_harness --self-test --json`
- 2026-03-27: Residual risks: telemetry snapshots still are not persisted across process restarts when upload never obtains a `race_id`; some live-pipeline structures still assume fixed 20-car loops; live pywebview QA with real UDP/backend reconnects is still recommended before broad release.

- 2026-03-27: файл создан как отдельная задача для следующей сессии.

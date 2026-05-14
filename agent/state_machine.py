"""
Agent runtime state machine.

Nominal path:
IDLE -> WAITING -> QUALIFYING/RACE -> FINISHED -> UPLOADED -> IDLE
"""
from __future__ import annotations

import threading
import time
from collections import deque
from enum import Enum
from typing import Callable


class AgentState(Enum):
    IDLE = "idle"
    WAITING = "waiting"
    QUALIFYING = "qualifying"
    RACE = "race"
    FINISHED = "finished"
    UPLOADED = "uploaded"


TransitionCallback = Callable[[AgentState], None]


STATE_ICONS = {
    AgentState.IDLE: "IDLE",
    AgentState.WAITING: "WAIT",
    AgentState.QUALIFYING: "QUALI",
    AgentState.RACE: "RACE",
    AgentState.FINISHED: "DONE",
    AgentState.UPLOADED: "SYNC",
}


STATE_LABELS = {
    AgentState.IDLE: "Idle - waiting for session",
    AgentState.WAITING: "Waiting - track detected",
    AgentState.QUALIFYING: "Qualifying - collecting grid/session context",
    AgentState.RACE: "Race - collecting live telemetry",
    AgentState.FINISHED: "Finished - processing results",
    AgentState.UPLOADED: "Uploaded - ready for next session",
}


ALLOWED_TRANSITIONS = {
    AgentState.IDLE: {AgentState.WAITING},
    AgentState.WAITING: {AgentState.IDLE, AgentState.QUALIFYING, AgentState.RACE, AgentState.FINISHED},
    AgentState.QUALIFYING: {AgentState.IDLE, AgentState.WAITING, AgentState.RACE, AgentState.FINISHED},
    AgentState.RACE: {AgentState.IDLE, AgentState.WAITING, AgentState.FINISHED},
    AgentState.FINISHED: {AgentState.IDLE, AgentState.WAITING, AgentState.UPLOADED},
    AgentState.UPLOADED: {AgentState.IDLE, AgentState.WAITING},
}


class StateMachine:
    def __init__(self, on_change: TransitionCallback | None = None):
        self._lock = threading.RLock()
        self._state = AgentState.IDLE
        self._on_change = on_change
        self._history = deque(maxlen=32)
        self._history.append({
            "at": time.time(),
            "from": None,
            "to": AgentState.IDLE.value,
            "reason": "initial_state",
        })

    @property
    def state(self) -> AgentState:
        with self._lock:
            return self._state

    def can_transition(self, new_state: AgentState) -> bool:
        with self._lock:
            if new_state == self._state:
                return True
            return new_state in ALLOWED_TRANSITIONS.get(self._state, set())

    def transition(
        self,
        new_state: AgentState,
        *,
        reason: str | None = None,
        force: bool = False,
    ) -> bool:
        callback = None
        old = None

        with self._lock:
            if new_state == self._state:
                return False

            if not force and new_state not in ALLOWED_TRANSITIONS.get(self._state, set()):
                print(
                    f"[STATE] Ignored invalid transition {self._state.value} -> "
                    f"{new_state.value} reason={reason or 'n/a'}"
                )
                self._history.append({
                    "at": time.time(),
                    "from": self._state.value,
                    "to": self._state.value,
                    "reason": f"rejected:{reason or 'invalid'}",
                })
                return False

            old = self._state
            self._state = new_state
            self._history.append({
                "at": time.time(),
                "from": old.value,
                "to": new_state.value,
                "reason": reason or "",
            })
            callback = self._on_change

        suffix = f" ({reason})" if reason else ""
        print(f"[STATE] {old.value} -> {new_state.value}{suffix}")
        if callback:
            callback(new_state)
        return True

    def reset(self, *, reason: str | None = "reset") -> bool:
        return self.transition(AgentState.IDLE, reason=reason)

    def icon(self) -> str:
        with self._lock:
            return STATE_ICONS[self._state]

    def label(self) -> str:
        with self._lock:
            return STATE_LABELS[self._state]

    def history(self) -> list[dict]:
        with self._lock:
            return list(self._history)

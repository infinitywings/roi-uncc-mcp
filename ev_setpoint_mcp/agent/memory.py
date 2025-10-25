"""Lightweight memory buffers for the MCP agent."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, Iterable, List, Optional


def _ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


@dataclass
class MemoryEvent:
    """Represents a single agent event."""

    event_type: str
    payload: Dict[str, object]
    timestamp: str = _ts()

    def short(self) -> str:
        base = f"[{self.timestamp}] {self.event_type}"
        if "summary" in self.payload:
            return f"{base}: {self.payload['summary']}"
        return base


class MemoryBuffer:
    """Maintains bounded memory for prompts and logging."""

    def __init__(self, max_events: int = 50):
        self._events: Deque[MemoryEvent] = deque(maxlen=max_events)

    def add(self, event_type: str, **payload: object) -> None:
        self._events.append(MemoryEvent(event_type=event_type, payload=payload))

    def extend(self, events: Iterable[MemoryEvent]) -> None:
        for event in events:
            self._events.append(event)

    def recent(self, limit: int = 10) -> List[MemoryEvent]:
        return list(self._events)[-limit:]

    def summarize(self, limit: int = 10) -> str:
        lines = []
        for event in self.recent(limit):
            lines.append(event.short())
        return "\n".join(lines) if lines else "No prior events recorded."

    def to_dict(self) -> List[Dict[str, object]]:
        return [dict(event_type=e.event_type, payload=e.payload, timestamp=e.timestamp) for e in self._events]

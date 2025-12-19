"""In-memory history store for recent GridState snapshots."""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, List, Optional

from ..models.grid_state import GridState


class HistoryStore:
    def __init__(self, max_size: int = 200):
        self._max_size = max(1, int(max_size))
        self._states: Deque[GridState] = deque(maxlen=self._max_size)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._states.clear()

    def append(self, state: GridState) -> None:
        with self._lock:
            self._states.append(state)

    def latest(self) -> Optional[GridState]:
        with self._lock:
            return self._states[-1] if self._states else None

    def as_list(self) -> List[GridState]:
        with self._lock:
            return list(self._states)


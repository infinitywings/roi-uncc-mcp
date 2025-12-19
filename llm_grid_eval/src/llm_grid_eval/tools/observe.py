"""Tool: observe - return latest GridState snapshot."""

from __future__ import annotations

from ..services.grid_observer import GridObserver
from ..services.history_store import HistoryStore
from ..services.metrics_collector import MetricsCollector


def observe(observer: GridObserver, history: HistoryStore, metrics: MetricsCollector) -> dict:
    state = observer.observe(step=True)
    history.append(state)
    metrics.update_violation_state(state.is_in_violation, state.simulation_time_sec)
    return state.to_dict()


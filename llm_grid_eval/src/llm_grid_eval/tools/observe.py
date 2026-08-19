"""Tool: observe - return latest GridState snapshot."""

from __future__ import annotations

from typing import Optional

from ..services.action_executor import ActionExecutor
from ..services.grid_observer import GridObserver
from ..services.history_store import HistoryStore
from ..services.metrics_collector import MetricsCollector


def observe(
    observer: GridObserver,
    history: HistoryStore,
    metrics: MetricsCollector,
    executor: Optional[ActionExecutor] = None,
) -> dict:
    state = observer.observe(step=True)
    history.append(state)
    metrics.update_violation_state(state.is_in_violation, state.simulation_time_sec)

    # Update ramp controller on each timestep (if executor provided)
    if executor is not None:
        executor.update()

    return state.to_dict()


"""Tool: analyze - compute timing assessment + include current grid snapshot."""

from __future__ import annotations

from typing import Optional

from ..services.action_executor import ActionExecutor
from ..services.grid_observer import GridObserver
from ..services.history_store import HistoryStore
from ..services.metrics_collector import MetricsCollector
from ..services.timing_analyzer import TimingAnalyzer


def analyze(
    observer: GridObserver,
    history: HistoryStore,
    metrics: MetricsCollector,
    analyzer: TimingAnalyzer,
    *,
    controller_interval_sec: float | None = None,
    executor: Optional[ActionExecutor] = None,
) -> dict:
    state = observer.observe(step=True)
    history.append(state)
    metrics.update_violation_state(state.is_in_violation, state.simulation_time_sec)

    # Update ramp controller on each timestep (if executor provided)
    if executor is not None:
        executor.update()

    interval = float(controller_interval_sec or analyzer.controller_interval_sec)
    if interval <= 0:
        interval = analyzer.controller_interval_sec

    # With the reference controller, actions occur at t = 0, interval, 2*interval, ...
    last_controller_time = state.simulation_time_sec - (state.simulation_time_sec % interval)

    # Use a temporary analyzer instance if interval differs.
    if interval != analyzer.controller_interval_sec:
        analyzer = TimingAnalyzer(
            threshold_kw=analyzer.threshold_kw,
            controller_interval_sec=interval,
            macro_weight=analyzer.macro_weight,
            micro_weight=analyzer.micro_weight,
        )

    assessment = analyzer.analyze(
        current_state=state,
        history=history.as_list(),
        last_controller_action_time=last_controller_time,
    )

    payload = assessment.to_dict()
    payload["grid"] = state.to_dict()
    return payload


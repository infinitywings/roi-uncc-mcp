"""Tool: attack - execute an EV setpoint attack under shared constraints."""

from __future__ import annotations

from ..models.attack import AttackRequest
from ..services.action_executor import ActionExecutor
from ..services.grid_observer import GridObserver
from ..services.history_store import HistoryStore
from ..services.metrics_collector import MetricsCollector
from ..services.timing_analyzer import TimingAnalyzer


def attack(
    observer: GridObserver,
    history: HistoryStore,
    metrics: MetricsCollector,
    analyzer: TimingAnalyzer,
    executor: ActionExecutor,
    *,
    ev_id: str,
    real_kw: float,
    reactive_kvar: float = 0.0,
    controller_interval_sec: float | None = None,
) -> dict:
    pre_state = observer.observe(step=False)

    interval = float(controller_interval_sec or analyzer.controller_interval_sec)
    if interval <= 0:
        interval = analyzer.controller_interval_sec
    last_controller_time = pre_state.simulation_time_sec - (pre_state.simulation_time_sec % interval)

    if interval != analyzer.controller_interval_sec:
        analyzer = TimingAnalyzer(
            threshold_kw=analyzer.threshold_kw,
            controller_interval_sec=interval,
            macro_weight=analyzer.macro_weight,
            micro_weight=analyzer.micro_weight,
        )

    assessment = analyzer.analyze(
        current_state=pre_state,
        history=history.as_list(),
        last_controller_action_time=last_controller_time,
    )

    result = executor.execute(
        AttackRequest(ev_id=ev_id, real_kw=float(real_kw), reactive_kvar=float(reactive_kvar)),
        pre_state=pre_state,
    )

    if not result.success and result.blocked_reason:
        metrics.record_blocked_attack(result.blocked_reason)
    elif result.success:
        metrics.record_attack(
            result,
            macro_score=assessment.macro.score,
            micro_score=assessment.micro.score,
            attack_hour=pre_state.timestamp.hour,
            cycle_position=assessment.micro.cycle_position,
        )

    payload = result.to_dict()
    payload["timing_at_attack"] = assessment.to_dict()
    return payload


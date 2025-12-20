"""LLM-GridEval attacker server (MCP-style HTTP tools)."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

from .helics_interface.config import AppConfig, load_app_config
from .helics_interface.federate import GridFederate
from .services.action_executor import ActionExecutor
from .services.attack_constraints import ConstraintService
from .services.grid_observer import GridObserver
from .services.history_store import HistoryStore
from .services.metrics_collector import MetricsCollector
from .services.timing_analyzer import TimingAnalyzer
from .tools.analyze import analyze as tool_analyze
from .tools.attack import attack as tool_attack
from .tools.metrics import metrics as tool_metrics
from .tools.observe import observe as tool_observe


class AnalyzeRequest(BaseModel):
    controller_interval_sec: Optional[float] = Field(default=None, ge=0)


class AttackToolRequest(BaseModel):
    ev_id: str
    real_kw: float
    reactive_kvar: float = 0.0
    controller_interval_sec: Optional[float] = Field(default=None, ge=0)


class ExperimentStartRequest(BaseModel):
    experiment_id: str = Field(min_length=1)


@dataclass
class AppState:
    config: AppConfig
    federate: GridFederate
    constraints: ConstraintService
    observer: GridObserver
    history: HistoryStore
    analyzer: TimingAnalyzer
    metrics: MetricsCollector
    executor: ActionExecutor


def create_app(config: AppConfig) -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, config.logging_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    app = FastAPI(title="LLM-GridEval MCP Attacker", version="0.1.0")

    federate = GridFederate(config.helics)
    constraints = ConstraintService.from_yaml(config.constraints_path)
    observer = GridObserver(
        federate,
        threshold_kw=config.grid.threshold_kw,
        nominal_voltage_v=config.grid.nominal_voltage_v,
        simulation_start_iso=config.grid.simulation_start_iso,
    )
    history = HistoryStore(max_size=config.timing.history_size)
    analyzer = TimingAnalyzer(
        threshold_kw=config.grid.threshold_kw,
        controller_interval_sec=config.timing.controller_interval_sec,
        macro_weight=config.timing.macro_weight,
        micro_weight=config.timing.micro_weight,
    )
    metrics = MetricsCollector(experiment_id="")
    executor = ActionExecutor(federate, observer, constraints)

    app.state.llm_grid_eval = AppState(
        config=config,
        federate=federate,
        constraints=constraints,
        observer=observer,
        history=history,
        analyzer=analyzer,
        metrics=metrics,
        executor=executor,
    )

    @app.get("/health")
    def health():
        state: AppState = app.state.llm_grid_eval
        return {
            "status": "ok",
            "helics": {
                "initialized": state.federate.is_initialized,
                "federate_name": state.config.helics.name,
                "broker_address": state.config.helics.broker_address,
                "period_sec": state.config.helics.period_sec,
                "offset_sec": state.config.helics.offset_sec,
                "current_time_sec": state.federate.current_time,
            },
            "ai": {
                "micro_score_threshold": state.config.ai.micro_score_threshold,
            },
        }

    @app.get("/constraints")
    def constraints_endpoint():
        state: AppState = app.state.llm_grid_eval
        return {"constraints": state.constraints.to_dict()}

    @app.post("/tools/observe")
    def tools_observe():
        state: AppState = app.state.llm_grid_eval
        return tool_observe(state.observer, state.history, state.metrics)

    @app.post("/tools/analyze")
    def tools_analyze(payload: AnalyzeRequest):
        state: AppState = app.state.llm_grid_eval
        return tool_analyze(
            state.observer,
            state.history,
            state.metrics,
            state.analyzer,
            controller_interval_sec=payload.controller_interval_sec,
        )

    @app.post("/tools/attack")
    def tools_attack(payload: AttackToolRequest):
        state: AppState = app.state.llm_grid_eval
        return tool_attack(
            state.observer,
            state.history,
            state.metrics,
            state.analyzer,
            state.executor,
            ev_id=payload.ev_id,
            real_kw=payload.real_kw,
            reactive_kvar=payload.reactive_kvar,
            controller_interval_sec=payload.controller_interval_sec,
        )

    @app.get("/tools/metrics")
    @app.post("/tools/metrics")
    def tools_metrics():
        state: AppState = app.state.llm_grid_eval
        return tool_metrics(state.metrics)

    @app.post("/experiment/start")
    def experiment_start(payload: ExperimentStartRequest):
        state: AppState = app.state.llm_grid_eval
        state.history.reset()
        state.constraints.reset_budget()
        state.metrics.reset(experiment_id=payload.experiment_id)
        return {"status": "ok", "experiment_id": payload.experiment_id}

    @app.post("/experiment/end")
    def experiment_end():
        state: AppState = app.state.llm_grid_eval
        latest = state.history.latest()
        final_time = latest.simulation_time_sec if latest else state.federate.current_time
        state.metrics.finalize(final_time)
        return {"status": "ok", "final_metrics": state.metrics.get_metrics()}

    @app.on_event("startup")
    def startup():
        """Initialize HELICS federate on server startup (not lazily)."""
        state: AppState = app.state.llm_grid_eval
        logging.getLogger(__name__).info("Initializing HELICS federate on startup...")
        state.federate.initialize()
        logging.getLogger(__name__).info("HELICS federate initialized successfully")

    @app.on_event("shutdown")
    def shutdown():
        state: AppState = app.state.llm_grid_eval
        try:
            state.federate.finalize()
        except Exception:
            logging.getLogger(__name__).exception("Error finalizing HELICS federate")

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-GridEval MCP attacker server")
    parser.add_argument(
        "--config",
        default="llm_grid_eval/config/default.yaml",
        help="Path to YAML config (default: llm_grid_eval/config/default.yaml)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Override bind host (default: config server.host)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override bind port (default: config server.port)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_app_config(args.config)
    app = create_app(config)

    host = args.host or config.server.host
    port = args.port or config.server.port

    uvicorn.run(app, host=host, port=port, log_level=config.logging_level.lower())


if __name__ == "__main__":
    main()


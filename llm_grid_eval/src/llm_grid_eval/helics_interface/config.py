"""Configuration models and YAML loader for LLM-GridEval."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5100


@dataclass(frozen=True)
class HelicsConfig:
    name: str = "ev_attacker_mcp"
    broker_address: str = "tcp://localhost:23404"
    core_type: str = "zmq"
    period_sec: float = 5.0
    offset_sec: float = 0.0


@dataclass(frozen=True)
class GridConfig:
    threshold_kw: float = 4200.0
    nominal_voltage_v: float = 2401.7771
    simulation_start_iso: str = "2013-08-28T00:00:00-05:00"


@dataclass(frozen=True)
class TimingConfig:
    controller_interval_sec: float = 60.0
    macro_weight: float = 0.6
    micro_weight: float = 0.4
    history_size: int = 200


@dataclass(frozen=True)
class AIConfig:
    """AI attacker configuration."""
    micro_score_threshold: int = 70


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    helics: HelicsConfig
    grid: GridConfig
    timing: TimingConfig
    ai: AIConfig
    logging_level: str = "INFO"
    constraints_path: str = "llm_grid_eval/config/constraints.yaml"


def load_app_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path)
    raw: Dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    server_raw = raw.get("server", {}) or {}
    helics_raw = raw.get("helics", {}) or {}
    grid_raw = raw.get("grid", {}) or {}
    timing_raw = raw.get("timing", {}) or {}
    ai_raw = raw.get("ai", {}) or {}
    logging_raw = raw.get("logging", {}) or {}

    broker_override = os.getenv("HELICS_BROKER_ADDRESS") or os.getenv("HELICS_BROKER")
    if broker_override:
        helics_raw = dict(helics_raw)
        helics_raw["broker_address"] = broker_override

    port_override = os.getenv("LLM_GRID_EVAL_PORT")
    if port_override:
        server_raw = dict(server_raw)
        server_raw["port"] = int(port_override)

    return AppConfig(
        server=ServerConfig(
            host=str(server_raw.get("host", "0.0.0.0")),
            port=int(server_raw.get("port", 5100)),
        ),
        helics=HelicsConfig(
            name=str(helics_raw.get("name", "ev_attacker_mcp")),
            broker_address=str(helics_raw.get("broker_address", "tcp://localhost:23404")),
            core_type=str(helics_raw.get("core_type", "zmq")),
            period_sec=float(helics_raw.get("period_sec", 5.0)),
            offset_sec=float(helics_raw.get("offset_sec", 0.0)),
        ),
        grid=GridConfig(
            threshold_kw=float(grid_raw.get("threshold_kw", 4200.0)),
            nominal_voltage_v=float(grid_raw.get("nominal_voltage_v", 2401.7771)),
            simulation_start_iso=str(grid_raw.get("simulation_start_iso", "2013-08-28T00:00:00-05:00")),
        ),
        timing=TimingConfig(
            controller_interval_sec=float(timing_raw.get("controller_interval_sec", 60.0)),
            macro_weight=float(timing_raw.get("macro_weight", 0.6)),
            micro_weight=float(timing_raw.get("micro_weight", 0.4)),
            history_size=int(timing_raw.get("history_size", 200)),
        ),
        ai=AIConfig(
            micro_score_threshold=int(ai_raw.get("micro_score_threshold", 70)),
        ),
        logging_level=str(logging_raw.get("level", "INFO")),
        constraints_path=str(raw.get("constraints_path", "llm_grid_eval/config/constraints.yaml")),
    )


"""Configuration dataclasses for the MCP agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class LLMConfig:
    """LLM connection settings."""

    api_base: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1500
    request_timeout: int = 120


@dataclass
class RuntimeConfig:
    """Controls loop pacing and duration."""

    interval_seconds: float = 5.0
    action_delay_seconds: float = 1.0
    max_steps: int = 0  # 0 == unlimited
    duration_seconds: int = 86_400  # 24h default
    wait_for_server: int = 120


@dataclass
class LoggingConfig:
    """Paths for campaign/LLM logs."""

    campaign_log: Path
    llm_log: Path
    max_memory_events: int = 50


@dataclass
class AgentConfig:
    """Top-level configuration for MCPAgent."""

    primitive_url: str
    tools: List[str] = field(default_factory=lambda: ["discover_topology", "monitor_protection_systems",
                                                     "analyze_power_flow", "set_ev_capacity"])
    llm: LLMConfig = field(default_factory=lambda: LLMConfig(
        api_base="http://localhost:8000/v1",
        model="openai/gpt-oss-120b"
    ))
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    logging: Optional[LoggingConfig] = None
    enable_auto_observation: bool = True
    topology_refresh_seconds: Optional[int] = None  # None means cache forever
    instructions: str = "Decide which tools to invoke next. You may choose multiple tools per turn."

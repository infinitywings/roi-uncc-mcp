"""Agent orchestrator built on modular components."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Dict, List, Optional

import requests

from .config import AgentConfig
from .memory import MemoryBuffer
from .prompts import PromptBuilder
from .tooling import MCPClient, ToolRegistry
from .utils import ensure_json_object, log_json_line


class MCPAgent:
    """Coordinates the MCP-aware LLM agent."""

    def __init__(self, config: AgentConfig, prompt_builder: Optional[PromptBuilder] = None):
        self.config = config
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.memory = MemoryBuffer(max_events=config.logging.max_memory_events if config.logging else 50)
        self.client = MCPClient(config.primitive_url)
        self.tools = ToolRegistry(self.client)
        self.tools.register_default_tools()
        self.observation_cache: Optional[Dict[str, object]] = None
        self.topology_cache: Optional[Dict[str, object]] = None
        self.last_topology_refresh: Optional[float] = None
        self.allowed_tools = set(config.tools or [])

    # --------------------------------------------------------------
    def _log_campaign(self, event: str, payload: Dict[str, object]) -> None:
        if not self.config.logging:
            return
        log_json_line(self.config.logging.campaign_log, {"event": event, **payload})

    def _log_llm(self, payload: Dict[str, object]) -> None:
        if not self.config.logging:
            return
        log_json_line(self.config.logging.llm_log, payload)

    # --------------------------------------------------------------
    def _ensure_topology(self) -> None:
        refresh_interval = self.config.topology_refresh_seconds
        if self.topology_cache and refresh_interval is None:
            return
        if (
            self.topology_cache
            and refresh_interval is not None
            and self.last_topology_refresh
            and (time.time() - self.last_topology_refresh) < refresh_interval
        ):
            return
        topo = self.tools.execute("discover_topology", {})
        self.topology_cache = topo
        self.last_topology_refresh = time.time()
        self.memory.add("topology_cached", summary="Topology updated", data=topo)
        self._log_campaign("topology_cached", {"result": topo})

    def _observe_grid(self) -> Dict[str, object]:
        snapshot = self.client.call("get_grid_status", {})
        self.observation_cache = snapshot
        self.memory.add("observation", summary="Latest grid snapshot recorded", data=snapshot)
        self._log_campaign("grid_observation", {"result": snapshot})
        return snapshot

    # --------------------------------------------------------------
    def _call_llm(self, messages: List[Dict[str, str]]) -> Dict[str, object]:
        llm_cfg = self.config.llm
        payload = {
            "model": llm_cfg.model,
            "messages": messages,
            "temperature": llm_cfg.temperature,
            "max_tokens": llm_cfg.max_tokens,
        }
        resp = requests.post(f"{llm_cfg.api_base}/chat/completions", json=payload, timeout=llm_cfg.request_timeout)
        elapsed = resp.elapsed.total_seconds() if resp.elapsed else None
        entry = {
            "request": payload,
            "status_code": resp.status_code,
            "elapsed_sec": elapsed,
        }
        try:
            entry["response"] = resp.json()
        except json.JSONDecodeError:
            entry["response"] = resp.text
        self._log_llm(entry)
        resp.raise_for_status()
        return entry["response"]

    def _parse_actions(self, llm_response: Dict[str, object]) -> Dict[str, object]:
        content = llm_response["choices"][0]["message"]["content"]
        try:
            return ensure_json_object(content)
        except ValueError as exc:
            raise RuntimeError(f"Unable to parse LLM response: {content}") from exc

    # --------------------------------------------------------------
    def run(self) -> None:
        cfg = self.config
        runtime = cfg.runtime

        # Ensure readiness
        deadline = time.time() + runtime.wait_for_server
        while time.time() < deadline:
            try:
                self.client.call("get_grid_status", {})
                break
            except Exception:
                time.sleep(2)
        else:
            raise TimeoutError("MCP server did not become ready in time")

        self._log_campaign(
            "campaign_start",
            {
                "steps": runtime.max_steps,
                "interval_sec": runtime.interval_seconds,
                "duration_sec": runtime.duration_seconds,
                "tools": list(self.allowed_tools),
            },
        )

        if cfg.enable_auto_observation:
            self._ensure_topology()
            observation = self._observe_grid()
        else:
            observation = self.client.call("get_grid_status", {})

        steps = 0
        start_sim_time = observation.get("simulation_time_sec")
        end_sim_time = (
            None if runtime.duration_seconds <= 0 else start_sim_time + runtime.duration_seconds if start_sim_time else None
        )

        while True:
            steps += 1
            if runtime.max_steps and steps > runtime.max_steps:
                break

            # Build prompt
            memory_summary = self.memory.summarize(limit=10)
            observation_payload = {
                "grid_status": self.observation_cache,
                "topology": self.topology_cache,
                "memory_size": len(self.memory.to_dict()),
            }
            instructions = self.config.instructions
            messages = self.prompt_builder.build_messages(
                memory_summary,
                observation_payload,
                self.tools.describe_tools(cfg.tools),
                instructions,
            )

            llm_response = self._call_llm(messages)
            plan = self._parse_actions(llm_response)
            self.memory.add("llm_plan", summary="LLM produced plan", data=plan)
            self._log_campaign("llm_decision", {"plan": plan, "step": steps})

            actions = plan.get("actions", [])
            for idx, action in enumerate(actions, start=1):
                tool_name = action.get("tool")
                params = action.get("params", {})
                if self.allowed_tools and tool_name not in self.allowed_tools:
                    error_payload = {"tool": tool_name, "params": params, "error": "Tool not permitted"}
                    self.memory.add("tool_error", summary=f"{tool_name} not permitted", data=error_payload)
                    self._log_campaign("tool_failed", {"step": steps, "sequence": idx, **error_payload})
                    continue
                try:
                    result = self.tools.execute(tool_name, params)
                    self.memory.add(
                        "tool_result",
                        summary=f"{tool_name} executed successfully",
                        data={"tool": tool_name, "params": params, "result": result},
                    )
                    self._log_campaign(
                        "tool_executed",
                        {"tool": tool_name, "params": params, "result": result, "step": steps, "sequence": idx},
                    )
                except Exception as exc:
                    error_payload = {"tool": tool_name, "params": params, "error": str(exc)}
                    self.memory.add("tool_error", summary=f"{tool_name} failed", data=error_payload)
                    self._log_campaign("tool_failed", {"step": steps, "sequence": idx, **error_payload})

                if runtime.action_delay_seconds > 0:
                    time.sleep(runtime.action_delay_seconds)

            # Always refresh observation for next turn
            if cfg.enable_auto_observation:
                observation = self._observe_grid()

            current_sim = observation.get("simulation_time_sec")
            if end_sim_time is not None and current_sim and current_sim >= end_sim_time:
                break

            time.sleep(runtime.interval_seconds)

        final_payload = {
            "steps": steps,
            "simulation_time_sec": self.observation_cache.get("simulation_time_sec") if self.observation_cache else None,
        }
        self._log_campaign("campaign_complete", final_payload)

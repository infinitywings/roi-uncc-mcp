"""Event-driven MCP agent orchestrator."""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Dict, List, Optional, Tuple

import requests

from .config import AgentConfig
from .memory import MemoryBuffer, MemoryEvent
from .prompts import PromptBuilder
from .tooling import MCPClient, ToolRegistry
from .utils import ensure_json_object, log_json_line


class MCPAgent:
    """Coordinates asynchronous observation and planning."""

    def __init__(self, config: AgentConfig, prompt_builder: Optional[PromptBuilder] = None):
        self.config = config
        self.prompt_builder = prompt_builder or PromptBuilder()
        logging_cfg = config.logging
        max_events = logging_cfg.max_memory_events if logging_cfg else 50
        self.memory = MemoryBuffer(max_events=max_events)
        self.client = MCPClient(config.primitive_url)
        self.tools = ToolRegistry(self.client)
        self.tools.register_default_tools()
        self.allowed_tools = set(config.tools or [])

        self.observation_cache: Optional[Dict[str, object]] = None
        self.topology_cache: Optional[Dict[str, object]] = None
        self.last_topology_refresh: Optional[float] = None

        self._campaign_log = logging_cfg.campaign_log if logging_cfg else None
        self._llm_log = logging_cfg.llm_log if logging_cfg else None
        self._harmony_log = logging_cfg.harmony_log if logging_cfg else None

        self._stop = threading.Event()
        self._event_queue: "queue.Queue[Tuple[str, Dict[str, object]]]" = queue.Queue()
        self._monitor_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    def _log_campaign(self, event: str, payload: Dict[str, object]) -> None:
        if not self._campaign_log:
            return
        log_json_line(self._campaign_log, {"event": event, **payload})

    def _log_llm(self, payload: Dict[str, object]) -> None:
        if not self._llm_log:
            return
        log_json_line(self._llm_log, payload)

    def _record_memory(self, event: MemoryEvent) -> None:
        if self._harmony_log:
            log_json_line(self._harmony_log, event.to_harmony())

    # ------------------------------------------------------------------
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
        event = self.memory.add(
            event_type="topology_cached",
            channel="system",
            content="Topology snapshot cached.",
            data=topo,
        )
        self._record_memory(event)
        self._log_campaign("topology_cached", {"result": topo})

    def _submit_observation(self, snapshot: Dict[str, object]) -> None:
        digest = json.dumps(snapshot, sort_keys=True)
        self._event_queue.put(("observation", {"snapshot": snapshot, "digest": digest}))

    def _monitor_loop(self) -> None:
        runtime = self.config.runtime
        interval = runtime.observation_interval_seconds or 5.0
        last_digest: Optional[str] = None

        while not self._stop.is_set():
            try:
                snapshot = self.client.call("get_grid_status", {})
                digest = json.dumps(snapshot, sort_keys=True)
                if digest != last_digest:
                    last_digest = digest
                    self._event_queue.put(("observation", {"snapshot": snapshot}))
            except Exception as exc:  # noqa: BLE001
                self._event_queue.put(("monitor_error", {"error": str(exc)}))
            self._stop.wait(interval)

    def _start_monitor(self) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_thread = threading.Thread(target=self._monitor_loop, name="AgentMonitor", daemon=True)
        self._monitor_thread.start()

    # ------------------------------------------------------------------
    def _call_llm(self, messages: List[Dict[str, str]]) -> Dict[str, object]:
        cfg = self.config.llm
        payload = {
            "model": cfg.model,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        resp = requests.post(f"{cfg.api_base}/chat/completions", json=payload, timeout=cfg.request_timeout)
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

    def _parse_plan(self, llm_response: Dict[str, object]) -> Dict[str, object]:
        content = llm_response["choices"][0]["message"]["content"]
        return ensure_json_object(content)

    def _should_plan(self, now: float, last_plan_at: float) -> bool:
        cooldown = self.config.runtime.decision_cooldown_seconds
        return (now - last_plan_at) >= cooldown

    # ------------------------------------------------------------------
    def run(self) -> None:
        cfg = self.config
        runtime = cfg.runtime

        # Wait for MCP readiness
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
                "duration_sec": runtime.duration_seconds,
                "tools": list(self.allowed_tools),
            },
        )

        self._ensure_topology()
        self._start_monitor()

        steps = 0
        last_plan_at = 0.0
        start_sim_time = None
        end_sim_time = None

        try:
            while not self._stop.is_set():
                try:
                    event_type, payload = self._event_queue.get(timeout=runtime.observation_interval_seconds or 5.0)
                except queue.Empty:
                    continue

                if event_type == "monitor_error":
                    event = self.memory.add(
                        event_type="monitor_error",
                        channel="system",
                        content=f"Monitor error: {payload['error']}",
                        error=payload["error"],
                    )
                    self._record_memory(event)
                    self._log_campaign("monitor_error", payload)
                    continue

                if event_type != "observation":
                    continue

                snapshot = payload["snapshot"]
                self.observation_cache = snapshot
                sim_time = snapshot.get("simulation_time_sec")
                if start_sim_time is None and sim_time is not None:
                    start_sim_time = sim_time
                    if runtime.duration_seconds > 0:
                        end_sim_time = start_sim_time + runtime.duration_seconds

                steps += 1
                event = self.memory.add(
                    event_type="observation",
                    channel="system",
                    content=f"Observation received (step {steps}).",
                    data=snapshot,
                )
                self._record_memory(event)
                self._log_campaign("grid_observation", {"step": steps, "result": snapshot})

                now = time.time()
                if not self._should_plan(now, last_plan_at):
                    if runtime.max_steps and steps >= runtime.max_steps:
                        break
                    if end_sim_time and sim_time and sim_time >= end_sim_time:
                        break
                    continue

                memory_summary = self.memory.summarize(limit=10)
                history = self.memory.harmony_tail(limit=12)
                observation_payload = {
                    "grid_status": snapshot,
                    "topology": self.topology_cache,
                    "history_tail": history,
                }
                messages = self.prompt_builder.build_messages(
                    memory_summary,
                    observation_payload,
                    self.tools.describe_tools(cfg.tools),
                    cfg.instructions,
                )

                llm_response = self._call_llm(messages)
                plan = self._parse_plan(llm_response)
                last_plan_at = now

                event = self.memory.add(
                    event_type="llm_plan",
                    channel="assistant",
                    content="LLM produced an action plan.",
                    data=plan,
                )
                self._record_memory(event)
                self._log_campaign("llm_decision", {"plan": plan, "step": steps})

                actions = plan.get("actions", [])
                for idx, action in enumerate(actions, start=1):
                    tool_name = action.get("tool")
                    params = action.get("params", {})
                    if self.allowed_tools and tool_name not in self.allowed_tools:
                        error_payload = {"tool": tool_name, "params": params, "error": "Tool not permitted"}
                        event = self.memory.add(
                            event_type="tool_error",
                            channel="system",
                            content=f"Tool '{tool_name}' not permitted.",
                            **error_payload,
                        )
                        self._record_memory(event)
                        self._log_campaign("tool_failed", {"step": steps, "sequence": idx, **error_payload})
                        continue

                    try:
                        result = self.tools.execute(tool_name, params)
                        event = self.memory.add(
                            event_type="tool_result",
                            channel="tool",
                            content=f"{tool_name} executed successfully.",
                            tool=tool_name,
                            params=params,
                            result=result,
                        )
                        self._record_memory(event)
                        self._log_campaign(
                            "tool_executed",
                            {"tool": tool_name, "params": params, "result": result, "step": steps, "sequence": idx},
                        )
                    except Exception as exc:
                        error_payload = {"tool": tool_name, "params": params, "error": str(exc)}
                        event = self.memory.add(
                            event_type="tool_error",
                            channel="tool",
                            content=f"{tool_name} failed: {exc}",
                            **error_payload,
                        )
                        self._record_memory(event)
                        self._log_campaign("tool_failed", {"step": steps, "sequence": idx, **error_payload})

                    if runtime.action_delay_seconds > 0:
                        if self._stop.wait(runtime.action_delay_seconds):
                            break

                if runtime.max_steps and steps >= runtime.max_steps:
                    break
                if end_sim_time and sim_time and sim_time >= end_sim_time:
                    break

        finally:
            self._stop.set()
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
            final_payload = {
                "steps": steps,
                "simulation_time_sec": self.observation_cache.get("simulation_time_sec") if self.observation_cache else None,
            }
            self._log_campaign("campaign_complete", final_payload)

#!/usr/bin/env python3
"""Run an AI-driven attack loop against the EV MCP primitive API."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
import uuid
from typing import Any, Dict, List

import requests
from datetime import datetime
from zoneinfo import ZoneInfo

SCHEMA_HINT = '{"actions":[{"ev_id":"EV3","real_kw":3000,"reactive_kvar":0}]} or {"actions":[]}'
TZ = ZoneInfo("America/New_York")


def current_timestamp() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def wait_for_server(base_url: str, timeout: int) -> None:
    """Block until the MCP primitive endpoint responds."""
    deadline = time.time() + timeout
    payload = {"method": "get_grid_status", "params": {}}
    while time.time() < deadline:
        try:
            resp = requests.post(base_url, json=payload, timeout=5)
            if resp.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise TimeoutError(f"MCP server not ready after {timeout} seconds")


def log_json_line(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def fetch_grid_state(primitive_url: str) -> Dict[str, Any]:
    resp = requests.post(
        primitive_url,
        json={"method": "get_grid_status", "params": {}},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def build_llm_messages(system_prompt: str, grid_state: Dict[str, Any],
                       recent_actions: List[Dict[str, Any]],
                       recent_timeline: List[Dict[str, Any]],
                       cooldown_min: float,
                       next_allowed_sim_time: float | None) -> List[Dict[str, str]]:
    result = grid_state.get("result", {})
    telemetry = {
        "total_real_power_kw": result.get("system_metrics", {}).get("total_real_power_kw", 0),
        "ev_setpoints_kw": result.get("grid_state", {}).get("ev_setpoints_kw", {}),
        "powers": result.get("grid_state", {}).get("powers", {}),
        "controller_state": result.get("grid_state", {}).get("blue_team_switches", {})
    }
    prompt_recent = recent_actions[-5:]
    timeline_recent = recent_timeline[-8:]
    telemetry_json = json.dumps(telemetry, ensure_ascii=False, indent=2)
    history_json = json.dumps(prompt_recent, ensure_ascii=False, indent=2)
    timeline_json = json.dumps(timeline_recent, ensure_ascii=False, indent=2)
    next_allowed_str = "now" if next_allowed_sim_time is None else next_allowed_sim_time
    quota_text = (
        f"One attack attempt allowed every {cooldown_min} minutes of simulation time. "
        f"Next allowed sim time: {next_allowed_str}."
    )
    user_prompt = (
        "Current grid telemetry (JSON):\n"
        f"{telemetry_json}\n"
        "Recent attack history (most recent first):\n"
        f"{history_json}\n"
        "Recent timeline (observations and outcomes):\n"
        f"{timeline_json}\n"
        f"{quota_text}\n"
        "Respond with JSON only using the schema "
        f"{SCHEMA_HINT}. Evaluate whether an attack is warranted; if not, return an empty list (e.g., {{\"actions\": []}})."
        " When you choose to attack, target combinations that meaningfully stress the feeder, keeping real_kw within [-500, 4000]."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def call_llm(llm_base: str, model: str, messages: List[Dict[str, str]], temperature: float,
             max_tokens: int, log_path: Path) -> Dict[str, Any]:
    interaction_id = str(uuid.uuid4())
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    start = time.time()
    response = requests.post(
        f"{llm_base}/chat/completions",
        json=payload,
        timeout=120
    )
    elapsed = time.time() - start
    entry = {
        "timestamp": current_timestamp(),
        "request": payload,
        "status_code": response.status_code,
        "elapsed_sec": elapsed,
        "interaction_id": interaction_id
    }
    try:
        entry["response"] = response.json()
    except json.JSONDecodeError:
        entry["response"] = response.text
    log_json_line(log_path, entry)
    response.raise_for_status()
    result = response.json()
    return interaction_id, result


def extract_actions(llm_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
        return parsed.get("actions", [])
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"Unable to parse LLM response: {content}")
    parsed = json.loads(match.group(0))
    return parsed.get("actions", [])


def augment_actions(actions: List[Dict[str, Any]], sim_time: float) -> List[Dict[str, Any]]:
    """Clamp actions based on simulation time to avoid early hard shocks."""
    if sim_time < 1800:        # first 30 minutes sim time
        max_kw = 200.0
    elif sim_time < 7200:      # first 2 hours sim time
        max_kw = 600.0
    else:
        max_kw = 1200.0

    for action in actions:
        action["real_kw"] = max(min(float(action.get("real_kw", 0.0)), max_kw), -500.0)
        action.setdefault("reactive_kvar", 0.0)
    return actions


def send_attack(primitive_url: str, action: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    real_kw = float(action.get("real_kw", 0.0))
    reactive = float(action.get("reactive_kvar", 0.0))
    params = {
        "ev_id": action.get("ev_id"),
        "real_power_kw": real_kw,
        "reactive_power_kvar": reactive
    }
    if "metadata" in action:
        params["metadata"] = action["metadata"]
    resp = requests.post(
        primitive_url,
        json={"method": "set_ev_capacity", "params": params},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-driven setpoint attack loop")
    parser.add_argument("--server", default="http://localhost:5100/primitive",
                        help="EV MCP primitive endpoint (default: http://localhost:5100/primitive)")
    parser.add_argument("--llm-base", default="http://ccil1s26m8hj6lws:8000/v1",
                        help="OpenAI-compatible LLM base URL")
    parser.add_argument("--model", default="openai/gpt-oss-120b",
                        help="Model identifier to request")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="LLM sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=1500,
                        help="Maximum tokens for each completion")
    parser.add_argument("--steps", type=int, default=0,
                        help="Maximum attack iterations (0 = unlimited until duration reached)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Real seconds to sleep between evaluations (simulation steps still advance by time_delta)")
    parser.add_argument("--wait", type=int, default=120,
                        help="Seconds to wait for MCP readiness")
    parser.add_argument("--action-timeout", type=int, default=90,
                        help="HTTP timeout (seconds) for each attack primitive")
    parser.add_argument("--action-delay", type=float, default=1.0,
                        help="Delay in seconds between successive attack actions")
    parser.add_argument("--duration-seconds", type=int, default=86400,
                        help="Total simulated duration to cover before stopping (default: 24h)")
    parser.add_argument("--log", default="/workspace/examples/2bus-13bus/logs/ai_campaign.log",
                        help="Campaign log file path")
    parser.add_argument("--llm-log", default="/workspace/examples/2bus-13bus/logs/llm_interactions.jsonl",
                        help="LLM interaction log file path")
    parser.add_argument("--attack-cooldown-minutes", type=float, default=30.0,
                        help="Minimum simulated minutes between attack attempts")
    parser.add_argument("--system-prompt", default=(
        "You are an adversarial researcher targeting EV setpoints. "
        "Respond only with JSON matching {\"actions\":[{\"ev_id\":\"EVn\",\"real_kw\":value,\"reactive_kvar\":value}]} or {\"actions\":[]}. "
        "You may modify any EV station (EV1 through EV6); use whichever combination best stresses the grid. "
        "Assess risk first; if the grid is already stressed or an attack would be ineffective, return an empty actions list."
    ), help="LLM system prompt")
    args = parser.parse_args()

    campaign_log = Path(args.log)
    llm_log = Path(args.llm_log)

    log_json_line(campaign_log, {
        "timestamp": current_timestamp(),
        "event": "campaign_start",
        "steps": args.steps,
        "interval_sec": args.interval,
        "duration_sec": args.duration_seconds,
        "attack_cooldown_minutes": args.attack_cooldown_minutes
    })

    start_sim_time = None
    end_sim_time = None
    step = 0
    last_sim_time = 0.0
    last_attack_sim_time = None
    recent_actions: List[Dict[str, Any]] = []
    recent_timeline: List[Dict[str, Any]] = []
    cooldown_sec = args.attack_cooldown_minutes * 60.0
    wait_for_server(args.server, args.wait)

    while True:
        grid_state = fetch_grid_state(args.server)
        result_payload = grid_state.get("result", {})
        sim_time = result_payload.get("simulation_time_sec")
        if sim_time is None:
            sim_time = last_sim_time + args.interval
        last_sim_time = sim_time

        if start_sim_time is None:
            start_sim_time = sim_time
            if args.duration_seconds > 0:
                end_sim_time = start_sim_time + args.duration_seconds

        step += 1
        # Record observation for timeline
        recent_timeline.append({
            "event": "observation",
            "step": step,
            "simulation_time_sec": sim_time,
            "total_real_power_kw": result_payload.get("system_metrics", {}).get("total_real_power_kw", 0),
            "ev_setpoints_kw": result_payload.get("grid_state", {}).get("ev_setpoints_kw", {})
        })
        recent_timeline = recent_timeline[-20:]
        log_json_line(campaign_log, {
            "timestamp": current_timestamp(),
            "event": "grid_observation",
            "step": step,
            "simulation_time_sec": sim_time,
            "data": grid_state
        })

        if end_sim_time is not None and sim_time >= end_sim_time:
            break
        if args.steps and step > args.steps:
            break

        next_allowed = None if last_attack_sim_time is None else last_attack_sim_time + cooldown_sec
        messages = build_llm_messages(args.system_prompt, grid_state, recent_actions,
                                      recent_timeline, args.attack_cooldown_minutes, next_allowed)
        interaction_id, llm_response = call_llm(
            args.llm_base, args.model, messages,
            args.temperature, args.max_tokens, llm_log
        )

        try:
            actions = extract_actions(llm_response)
        except Exception as exc:
            log_json_line(campaign_log, {
                "timestamp": current_timestamp(),
                "event": "llm_parse_error",
                "step": step,
                "error": str(exc),
                "llm_response": llm_response
            })
            break

        actions = augment_actions(actions, sim_time)

        log_json_line(campaign_log, {
            "timestamp": current_timestamp(),
            "event": "llm_decision",
            "step": step,
            "interaction_id": interaction_id,
            "actions": actions
        })

        # Rate limit: skip attacks if within cooldown
        if last_attack_sim_time is not None and sim_time < last_attack_sim_time + cooldown_sec:
            log_json_line(campaign_log, {
                "timestamp": current_timestamp(),
                "event": "attack_rate_limited",
                "step": step,
                "simulation_time_sec": sim_time,
                "next_allowed_sim_time": last_attack_sim_time + cooldown_sec,
                "interaction_id": interaction_id
            })
            recent_timeline.append({
                "event": "attack_rate_limited",
                "step": step,
                "simulation_time_sec": sim_time,
                "next_allowed_sim_time": last_attack_sim_time + cooldown_sec
            })
            recent_timeline = recent_timeline[-20:]
            time.sleep(max(0.0, args.interval))
            continue

        if not actions:
            log_json_line(campaign_log, {
                "timestamp": current_timestamp(),
                "event": "attack_skipped",
                "step": step,
                "interaction_id": interaction_id
            })
            recent_timeline.append({
                "event": "attack_skipped",
                "step": step,
                "simulation_time_sec": sim_time
            })
        else:
            for idx, action in enumerate(actions, start=1):
                action.setdefault("metadata", {})
                action["metadata"]["interaction_id"] = interaction_id
                action["metadata"]["sequence"] = idx
                action["metadata"]["step"] = step
                action_payload = dict(action)
                try:
                    result = send_attack(args.server, action, args.action_timeout)
                    log_json_line(campaign_log, {
                        "timestamp": current_timestamp(),
                        "event": "attack_executed",
                        "step": step,
                        "sequence": idx,
                        "interaction_id": interaction_id,
                        "action": action_payload,
                        "result": result
                    })
                    # Track history for prompt
                    recent_actions.append({
                        "step": step,
                        "simulation_time_sec": sim_time,
                        "action": action_payload,
                        "result": "executed"
                    })
                    recent_timeline.append({
                        "event": "attack_executed",
                        "step": step,
                        "simulation_time_sec": sim_time,
                        "action": action_payload
                    })
                    recent_timeline = recent_timeline[-20:]
                    last_attack_sim_time = sim_time
                except Exception as exc:
                    log_json_line(campaign_log, {
                        "timestamp": current_timestamp(),
                        "event": "attack_failed",
                        "step": step,
                        "sequence": idx,
                        "interaction_id": interaction_id,
                        "action": action_payload,
                        "error": str(exc)
                    })
                    recent_actions.append({
                        "step": step,
                        "simulation_time_sec": sim_time,
                        "action": action_payload,
                        "result": f"failed: {exc}"
                    })
                    recent_timeline.append({
                        "event": "attack_failed",
                        "step": step,
                        "simulation_time_sec": sim_time,
                        "action": action_payload,
                        "error": str(exc)
                    })
                    recent_timeline = recent_timeline[-20:]
                time.sleep(max(0.0, args.action_delay))

        time.sleep(max(0.0, args.interval))

    log_json_line(campaign_log, {
        "timestamp": current_timestamp(),
        "event": "campaign_complete",
        "steps": step,
        "simulation_time_sec": last_sim_time
    })


if __name__ == "__main__":
    main()

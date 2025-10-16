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

SCHEMA_HINT = '{"actions": [{"ev_id": "EV3", "real_kw": 2500, "reactive_kvar": 0}]}'
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


def build_llm_messages(system_prompt: str, grid_state: Dict[str, Any]) -> List[Dict[str, str]]:
    result = grid_state.get("result", {})
    telemetry = {
        "total_real_power_kw": result.get("system_metrics", {}).get("total_real_power_kw", 0),
        "ev_setpoints_kw": result.get("grid_state", {}).get("ev_setpoints_kw", {}),
        "powers": result.get("grid_state", {}).get("powers", {}),
    }
    telemetry_json = json.dumps(telemetry, ensure_ascii=False, indent=2)
    user_prompt = (
        "Current grid telemetry (JSON):\n"
        f"{telemetry_json}\n"
        "Respond with JSON only using the schema "
        f"{SCHEMA_HINT}. Include 1-3 malicious setpoint updates and keep real_kw within [-500, 4000]."
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
    parser.add_argument("--steps", type=int, default=3,
                        help="Number of attack iterations")
    parser.add_argument("--interval", type=int, default=30,
                        help="Seconds between iterations")
    parser.add_argument("--wait", type=int, default=60,
                        help="Seconds to wait for MCP readiness")
    parser.add_argument("--action-timeout", type=int, default=90,
                        help="HTTP timeout (seconds) for each attack primitive")
    parser.add_argument("--action-delay", type=float, default=2.0,
                        help="Delay in seconds between successive attack actions")
    parser.add_argument("--log", default="/workspace/examples/2bus-13bus/logs/ai_campaign.log",
                        help="Campaign log file path")
    parser.add_argument("--llm-log", default="/workspace/examples/2bus-13bus/logs/llm_interactions.jsonl",
                        help="LLM interaction log file path")
    parser.add_argument("--system-prompt", default=(
        "You are an adversarial researcher targeting EV setpoints. Respond only with JSON matching "
        "{\"actions\":[{\"ev_id\":\"EV3\",\"real_kw\":2500,\"reactive_kvar\":0}]}. "
        "All real_kw values must stay within [-500, 4000]."
    ), help="LLM system prompt")
    args = parser.parse_args()

    campaign_log = Path(args.log)
    llm_log = Path(args.llm_log)

    log_json_line(campaign_log, {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "campaign_start",
        "steps": args.steps,
        "interval_sec": args.interval
    })

    wait_for_server(args.server, args.wait)

    for step in range(1, args.steps + 1):
        grid_state = fetch_grid_state(args.server)
        log_json_line(campaign_log, {
            "timestamp": current_timestamp(),
            "event": "grid_observation",
            "step": step,
            "data": grid_state
        })

        messages = build_llm_messages(args.system_prompt, grid_state)
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

        log_json_line(campaign_log, {
            "timestamp": current_timestamp(),
            "event": "llm_decision",
            "step": step,
            "interaction_id": interaction_id,
            "actions": actions
        })

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
            time.sleep(max(0.0, args.action_delay))

        if step < args.steps:
            time.sleep(args.interval)

    log_json_line(campaign_log, {
        "timestamp": current_timestamp(),
        "event": "campaign_complete"
    })


if __name__ == "__main__":
    main()

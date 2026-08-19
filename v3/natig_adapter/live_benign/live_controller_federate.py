#!/usr/bin/env python3
"""Deterministic benign G4 controller HELICS-message federate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import helics as h


DURATION_S = 840
PERIOD_S = 10
DESTINATION = "natig/cc_der_ev4"
SCHEDULE_WINDOWS = (
    ("baseline", 0, 60, 0.0, 0.0),
    ("p_inject", 60, 180, 10.0, 0.0),
    ("p_recovery", 180, 240, 0.0, 0.0),
    ("p_absorb", 240, 360, -10.0, 0.0),
    ("pre_q_recovery", 360, 420, 0.0, 0.0),
    ("q_inject", 420, 540, 0.0, 10.0),
    ("q_recovery", 540, 600, 0.0, 0.0),
    ("q_absorb", 600, 720, 0.0, -10.0),
    ("final_recovery", 720, 840, 0.0, 0.0),
)


def semantic_command(
    *,
    point_index: int,
    value: float,
    event_time_s: float,
    sequence: int,
) -> dict[str, Any]:
    command_type, unit = (
        ("active_power_setpoint", "kW")
        if point_index == 0
        else ("reactive_setpoint", "kvar")
    )
    return {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": (
            f"live-t{int(event_time_s):04d}-ao{point_index}"
        ),
        "event_time_s": event_time_s,
        "source": "ev_controller_v3",
        "target": "DER_EV4_BESS",
        "sequence": sequence,
        "type": command_type,
        "payload": {
            "value": value,
            "unit": unit,
            "valid_until_s": event_time_s + 30.0,
            "quality": ["online"],
        },
    }


def send_json(endpoint: Any, federate: Any, value: dict[str, Any]) -> None:
    message = h.helicsFederateCreateMessage(federate)
    h.helicsMessageSetString(
        message,
        json.dumps(value, sort_keys=True, separators=(",", ":")),
    )
    h.helicsMessageSetDestination(message, DESTINATION)
    h.helicsEndpointSendMessage(endpoint, message)


def message_text(message: Any) -> str:
    try:
        return h.helicsMessageGetString(message)
    except (AttributeError, TypeError):
        data = message.data
        return (
            data.decode("utf-8")
            if isinstance(data, (bytes, bytearray))
            else str(data)
        )


def drain(endpoint: Any, granted_s: float) -> list[dict[str, Any]]:
    rows = []
    while h.helicsEndpointHasMessage(endpoint):
        message = h.helicsEndpointGetMessage(endpoint)
        raw = message_text(message)
        parsed = json.loads(raw)
        rows.append(
            {
                "granted_time_s": granted_s,
                "source": getattr(message, "source", None),
                "original_source": getattr(
                    message, "original_source", None
                ),
                "payload": parsed,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    if args.trace.exists():
        raise FileExistsError(args.trace)

    fed = h.helicsCreateCombinationFederateFromConfig(str(args.config))
    endpoint = h.helicsFederateGetEndpointByIndex(fed, 0)
    trace: dict[str, Any] = {
        "scope": "G4 benign controller trace; no attacker",
        "commands": [],
        "telemetry": [],
    }
    by_start = {
        start: (name, p_kw, q_kvar)
        for name, start, _stop, p_kw, q_kvar in SCHEDULE_WINDOWS
    }
    try:
        h.helicsFederateEnterExecutingMode(fed)
        granted = 0.0
        sent_starts: set[int] = set()
        same_time_grants = 0
        while granted < DURATION_S:
            if int(granted) in by_start and int(granted) not in sent_starts:
                name, p_kw, q_kvar = by_start[int(granted)]
                sequence = (
                    [item[1] for item in SCHEDULE_WINDOWS].index(
                        int(granted)
                    )
                    + 1
                )
                for point_index, value in enumerate((p_kw, q_kvar)):
                    semantic = semantic_command(
                        point_index=point_index,
                        value=value,
                        event_time_s=granted,
                        sequence=sequence,
                    )
                    wire = {
                        "wire_schema": (
                            "grideval-g4-controller-command/1.0"
                        ),
                        "operation": "select_operate",
                        "point_index": point_index,
                        "semantic_message": semantic,
                    }
                    send_json(endpoint, fed, wire)
                    trace["commands"].append(
                        {
                            "sent_time_s": granted,
                            "window": name,
                            "operation": "select_operate",
                            "point_index": point_index,
                            "semantic_message": semantic,
                        }
                    )
                sent_starts.add(int(granted))
            next_time = min(DURATION_S, granted + PERIOD_S)
            next_grant = float(
                h.helicsFederateRequestTime(fed, next_time)
            )
            if next_grant < granted:
                raise RuntimeError("HELICS granted time moved backwards")
            if next_grant == granted:
                same_time_grants += 1
                if same_time_grants > 1000:
                    raise RuntimeError("excessive same-time HELICS grants")
            else:
                same_time_grants = 0
            granted = next_grant
            trace["telemetry"].extend(drain(endpoint, granted))
        settle_grant = float(
            h.helicsFederateRequestTime(fed, DURATION_S + PERIOD_S)
        )
        if settle_grant < DURATION_S:
            raise RuntimeError("HELICS final telemetry settle grant regressed")
        trace["telemetry"].extend(drain(endpoint, settle_grant))
        trace["settle_grant_s"] = settle_grant
    finally:
        try:
            h.helicsFederateFinalize(fed)
        finally:
            h.helicsFederateFree(fed)

    trace["command_message_count"] = len(trace["commands"])
    trace["telemetry_message_count"] = len(trace["telemetry"])
    args.trace.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "command_message_count": trace["command_message_count"],
                "telemetry_message_count": trace[
                    "telemetry_message_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

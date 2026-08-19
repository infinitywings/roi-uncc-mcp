#!/usr/bin/env python3
"""Validate the fail-closed G4 cyber/physical endpoint contract offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.0"

EXPECTED_ENDPOINTS = {
    "controller/der_ev4": (
        "controller",
        "command_source_and_telemetry_sink",
    ),
    "natig/cc_der_ev4": ("natig", "dnp3_master_adapter"),
    "natig/der_ev4": ("natig", "dnp3_outstation_adapter"),
    "gateway/der_ev4": (
        "gateway",
        "validated_opender_command_sink_and_telemetry_source",
    ),
}

EXPECTED_EDGES = {
    (
        "command",
        1,
        "controller/der_ev4",
        "natig/cc_der_ev4",
        "helics_message",
    ),
    (
        "command",
        2,
        "natig/cc_der_ev4",
        "natig/der_ev4",
        "dnp3_over_ns3",
    ),
    (
        "command",
        3,
        "natig/der_ev4",
        "gateway/der_ev4",
        "helics_message",
    ),
    (
        "telemetry",
        1,
        "gateway/der_ev4",
        "natig/der_ev4",
        "helics_message",
    ),
    (
        "telemetry",
        2,
        "natig/der_ev4",
        "natig/cc_der_ev4",
        "dnp3_over_ns3",
    ),
    (
        "telemetry",
        3,
        "natig/cc_der_ev4",
        "controller/der_ev4",
        "helics_message",
    ),
}

EXPECTED_PHYSICAL_LINKS = {
    (
        "gridlabd/ev4_voltage_c",
        "gridlabd",
        "gateway",
        "complex",
        "V",
    ),
    (
        "gateway/feeder_load_va",
        "gateway",
        "gridlabd",
        "complex",
        "VA",
    ),
}

BANNED_ENDPOINT_NAMES = ("CC/Monitor", "fout", "trip_shad_inv1$Pref")
EXPECTED_POLICIES = {
    "all_cyber_edge_sources_and_destinations_must_be_declared": True,
    "gridlabd_message_endpoints_must_be_empty": True,
    "cyber_and_physical_planes_must_be_disjoint": True,
    "forbidden_direct_edges": [
        {
            "source": "controller/der_ev4",
            "destination": "gateway/der_ev4",
        }
    ],
    "forbidden_owner_edges": [
        {"source_owner": "natig", "destination_owner": "gridlabd"}
    ],
    "banned_endpoint_names": list(BANNED_ENDPOINT_NAMES),
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be a JSON object")
    return value


def endpoint_name_is_banned(name: str) -> bool:
    folded = name.casefold()
    for banned in BANNED_ENDPOINT_NAMES:
        token = banned.casefold()
        if folded == token or folded.endswith("/" + token):
            return True
    return False


def edge_tuple(edge: dict[str, Any]) -> tuple[Any, ...]:
    return (
        edge.get("stream"),
        edge.get("stage"),
        edge.get("source"),
        edge.get("destination"),
        edge.get("transport"),
    )


def physical_tuple(link: dict[str, Any]) -> tuple[Any, ...]:
    return (
        link.get("key"),
        link.get("publisher"),
        link.get("subscriber"),
        link.get("type"),
        link.get("unit"),
    )


def require_list(value: Any, label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    return value


def validate_endpoint_graph(graph: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors; an empty list means PASS."""

    errors: list[str] = []
    expected_root_keys = {
        "schema_version",
        "scope",
        "cyber_messages",
        "physical_values",
        "policies",
    }
    root_keys = set(graph)
    if root_keys != expected_root_keys:
        errors.append(
            "root keys must be exact; "
            f"missing={sorted(expected_root_keys - root_keys)}, "
            f"extra={sorted(root_keys - expected_root_keys)}"
        )
    if graph.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")

    cyber = graph.get("cyber_messages")
    if not isinstance(cyber, dict):
        errors.append("cyber_messages must be an object")
        cyber = {}
    endpoints = require_list(cyber.get("endpoints"), "cyber_messages.endpoints", errors)
    edges = require_list(cyber.get("edges"), "cyber_messages.edges", errors)

    endpoint_ids: list[str] = []
    owners: dict[str, str] = {}
    for index, endpoint in enumerate(endpoints):
        label = f"cyber_messages.endpoints[{index}]"
        if not isinstance(endpoint, dict):
            errors.append(f"{label} must be an object")
            continue
        endpoint_id = endpoint.get("id")
        if not isinstance(endpoint_id, str) or not endpoint_id:
            errors.append(f"{label}.id must be a non-empty string")
            continue
        endpoint_ids.append(endpoint_id)
        owner = endpoint.get("owner")
        if isinstance(owner, str):
            owners[endpoint_id] = owner
        if endpoint_name_is_banned(endpoint_id):
            errors.append(f"{label}: banned endpoint name {endpoint_id!r}")
        expected = EXPECTED_ENDPOINTS.get(endpoint_id)
        if expected is None:
            errors.append(f"{label}: undeclared/nonminimal endpoint {endpoint_id!r}")
        else:
            expected_owner, expected_function = expected
            if endpoint.get("owner") != expected_owner:
                errors.append(f"{endpoint_id}: owner must be {expected_owner}")
            if endpoint.get("function") != expected_function:
                errors.append(
                    f"{endpoint_id}: function must be {expected_function}"
                )
        if endpoint.get("kind") != "helics_endpoint":
            errors.append(f"{endpoint_id}: kind must be helics_endpoint")
        if endpoint.get("plane") != "cyber_message":
            errors.append(f"{endpoint_id}: plane must be cyber_message")
        if endpoint.get("global") is not True:
            errors.append(f"{endpoint_id}: endpoint must be global")
        if owner == "gridlabd" or endpoint_id.casefold().startswith("gridlabd/"):
            errors.append(f"{endpoint_id}: GridLAB-D may not own a message endpoint")

    if len(endpoint_ids) != len(set(endpoint_ids)):
        errors.append("cyber endpoint ids must be unique")
    actual_endpoint_set = set(endpoint_ids)
    expected_endpoint_set = set(EXPECTED_ENDPOINTS)
    if actual_endpoint_set != expected_endpoint_set:
        errors.append(
            "cyber endpoint set must be exact; "
            f"missing={sorted(expected_endpoint_set - actual_endpoint_set)}, "
            f"extra={sorted(actual_endpoint_set - expected_endpoint_set)}"
        )

    edge_ids: list[str] = []
    actual_edges: set[tuple[Any, ...]] = set()
    physical_keys = {
        item[0] for item in EXPECTED_PHYSICAL_LINKS
    }
    for index, edge in enumerate(edges):
        label = f"cyber_messages.edges[{index}]"
        if not isinstance(edge, dict):
            errors.append(f"{label} must be an object")
            continue
        edge_id = edge.get("id")
        if not isinstance(edge_id, str) or not edge_id:
            errors.append(f"{label}.id must be a non-empty string")
        else:
            edge_ids.append(edge_id)
        source = edge.get("source")
        destination = edge.get("destination")
        if source not in actual_endpoint_set:
            errors.append(f"{label}: source is not a declared cyber endpoint: {source!r}")
        if destination not in actual_endpoint_set:
            errors.append(
                f"{label}: destination is not a declared cyber endpoint: "
                f"{destination!r}"
            )
        for side, value in (("source", source), ("destination", destination)):
            if isinstance(value, str) and endpoint_name_is_banned(value):
                errors.append(f"{label}: {side} uses banned endpoint {value!r}")
            if isinstance(value, str) and (
                value in physical_keys or value.casefold().startswith("gridlabd/")
            ):
                errors.append(
                    f"{label}: cyber edge crosses into physical/GridLAB-D "
                    f"namespace through {side}={value!r}"
                )
        if (
            source == "controller/der_ev4"
            and destination == "gateway/der_ev4"
        ):
            errors.append(f"{label}: forbidden direct controller-to-gateway edge")
        if owners.get(source) == "natig" and owners.get(destination) == "gridlabd":
            errors.append(f"{label}: forbidden NATIG-to-GridLAB-D edge")
        actual_edges.add(edge_tuple(edge))

    if len(edge_ids) != len(set(edge_ids)):
        errors.append("cyber edge ids must be unique")
    if len(actual_edges) != len(edges):
        errors.append("cyber directed edge tuples must be unique")
    if actual_edges != EXPECTED_EDGES:
        errors.append(
            "directed command/telemetry edge set must be exact; "
            f"missing={sorted(EXPECTED_EDGES - actual_edges, key=repr)}, "
            f"extra={sorted(actual_edges - EXPECTED_EDGES, key=repr)}"
        )

    physical = graph.get("physical_values")
    if not isinstance(physical, dict):
        errors.append("physical_values must be an object")
        physical = {}
    if physical.get("transport") != "helics_value":
        errors.append("physical_values.transport must be helics_value")
    if physical.get("gridlabd_message_endpoints") != []:
        errors.append("GridLAB-D physical config must have zero message endpoints")
    links = require_list(physical.get("links"), "physical_values.links", errors)
    actual_physical: set[tuple[Any, ...]] = set()
    for index, link in enumerate(links):
        label = f"physical_values.links[{index}]"
        if not isinstance(link, dict):
            errors.append(f"{label} must be an object")
            continue
        if link.get("transport") is not None:
            errors.append(
                f"{label}: per-link transport is forbidden; the physical plane "
                "is globally helics_value"
            )
        if link.get("publisher") in {"controller", "natig"}:
            errors.append(f"{label}: cyber owner cannot publish a physical value")
        if link.get("subscriber") in {"controller", "natig"}:
            errors.append(f"{label}: cyber owner cannot subscribe to a physical value")
        actual_physical.add(physical_tuple(link))
    if len(actual_physical) != len(links):
        errors.append("physical value links must be unique")
    if actual_physical != EXPECTED_PHYSICAL_LINKS:
        errors.append(
            "physical HELICS value link set must be exact; "
            f"missing={sorted(EXPECTED_PHYSICAL_LINKS - actual_physical)}, "
            f"extra={sorted(actual_physical - EXPECTED_PHYSICAL_LINKS)}"
        )

    if graph.get("policies") != EXPECTED_POLICIES:
        errors.append("policies must exactly retain all fail-closed G4 constraints")

    return errors


def iter_endpoint_lists(value: Any, path: str = "$") -> Iterable[tuple[str, list[Any]]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "endpoints" and isinstance(child, list):
                yield child_path, child
            yield from iter_endpoint_lists(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_endpoint_lists(child, f"{path}[{index}]")


def validate_gridlabd_physical_config(
    config: dict[str, Any], label: str = "GridLAB-D physical config"
) -> list[str]:
    errors: list[str] = []
    for path, endpoints in iter_endpoint_lists(config):
        if endpoints:
            errors.append(
                f"{label}: {path} must be empty; found {len(endpoints)} "
                "message endpoint(s)"
            )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "graph",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("endpoint_graph.json"),
    )
    parser.add_argument(
        "--gridlabd-config",
        action="append",
        default=[],
        type=Path,
        help="optional physical HELICS config; every endpoints list must be empty",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        graph = load_json(args.graph)
        errors = validate_endpoint_graph(graph)
        for config_path in args.gridlabd_config:
            errors.extend(
                validate_gridlabd_physical_config(
                    load_json(config_path), str(config_path)
                )
            )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"G4 endpoint graph validation FAILED ({len(errors)} error(s))")
        return 1
    print("G4 endpoint graph validation PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

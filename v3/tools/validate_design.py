#!/usr/bin/env python3
"""Offline structural checks for the GridEval v3 design scaffold."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


CYBER_SOURCES = ("controller", "attacker", "ev_controller", "grideval_attacker")
PHYSICAL_DESTINATIONS = ("gld_hlc_conn/", "opender/", "DER_")


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def check_devices(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    devices = data.get("devices")
    if not isinstance(devices, list) or not devices:
        return ["der_devices.yaml: devices must be a non-empty list"]

    enabled = [device for device in devices if device.get("enabled") is True]
    if len(enabled) != 1:
        errors.append(
            "der_devices.yaml: MVP must have exactly one enabled device "
            f"(found {len(enabled)})"
        )

    ids: set[str] = set()
    sites: set[tuple[Any, Any, Any]] = set()
    for device in devices:
        device_id = device.get("id")
        if not isinstance(device_id, str) or not device_id:
            errors.append("der_devices.yaml: every device needs a non-empty id")
        elif device_id in ids:
            errors.append(f"der_devices.yaml: duplicate device id {device_id}")
        else:
            ids.add(device_id)

        site = (device.get("feeder"), device.get("node"), device.get("phase"))
        if site in sites:
            errors.append(f"der_devices.yaml: duplicate physical site {site}")
        sites.add(site)

        for field in ("nominal_voltage_v", "rating_va", "model_step_s"):
            value = device.get(field)
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"{device_id}: {field} must be positive")

        soc = device.get("initial_soc_pu")
        if soc is not None and (
            not isinstance(soc, (int, float)) or not 0 <= soc <= 1
        ):
            errors.append(f"{device_id}: initial_soc_pu must be in [0, 1]")

        exclusion = device.get("legacy_storage_exclusion", {})
        if exclusion.get("required_status") != "OPEN":
            errors.append(f"{device_id}: legacy storage switch must be OPEN")
        if not exclusion.get("forbidden_active_objects"):
            errors.append(f"{device_id}: forbidden legacy objects are not declared")

    frequency = data.get("frequency_source", {})
    if (
        frequency.get("mode") == "nominal_for_interface_test_only"
        and frequency.get("scientific_frequency_functions_enabled") is not False
    ):
        errors.append(
            "der_devices.yaml: scientific frequency functions cannot be enabled "
            "with a nominal-only source"
        )
    return errors


def check_network(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    defaults = data.get("defaults", {})
    if defaults.get("external_network_access") is not False:
        errors.append("network_scenarios.yaml: external_network_access must be false")
    if defaults.get("random_seed") != "required":
        errors.append("network_scenarios.yaml: random seeds must be required")

    topology = data.get("topology", {})
    if topology.get("protocol") != "dnp3":
        errors.append("network_scenarios.yaml: MVP protocol must be dnp3")

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        return errors + ["network_scenarios.yaml: scenarios must be a list"]
    ids = [item.get("id") for item in scenarios]
    if len(ids) != len(set(ids)):
        errors.append("network_scenarios.yaml: scenario ids must be unique")
    for required in ("direct_reference", "natig_benign"):
        matching = [item for item in scenarios if item.get("id") == required]
        if len(matching) != 1 or matching[0].get("enabled") is not True:
            errors.append(f"network_scenarios.yaml: {required} must be enabled")
    benign = next(
        (item for item in scenarios if item.get("id") == "natig_benign"), {}
    )
    if benign.get("attack") != "none":
        errors.append("network_scenarios.yaml: natig_benign cannot contain an attack")
    if benign.get("random_loss_fraction") != 0.0:
        errors.append("network_scenarios.yaml: natig_benign cannot drop packets")
    return errors


def check_schema(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = set(data.get("required", []))
    expected = {
        "schema_version",
        "kind",
        "message_id",
        "event_time_s",
        "source",
        "target",
        "sequence",
        "type",
        "payload",
    }
    missing = sorted(expected - required)
    if missing:
        errors.append(f"cyber message schema: missing required fields {missing}")
    if data.get("additionalProperties") is not False:
        errors.append("cyber message schema: unknown top-level fields must be rejected")
    return errors


def check_markdown_links(root: Path) -> list[str]:
    errors: list[str] = []
    for doc in root.glob("*.md"):
        text = doc.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" not in target and not (doc.parent / target).exists():
                errors.append(f"{doc}: broken local link {target}")
    return errors


def iter_endpoints(value: Any):
    if isinstance(value, dict):
        endpoints = value.get("endpoints")
        if isinstance(endpoints, list):
            yield from endpoints
        for child in value.values():
            yield from iter_endpoints(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_endpoints(child)


def check_federation_bypass(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for endpoint in iter_endpoints(data):
        key = str(endpoint.get("key", "")).lower()
        destination = str(endpoint.get("destination", ""))
        if any(token in key for token in CYBER_SOURCES) and any(
            destination.startswith(token) for token in PHYSICAL_DESTINATIONS
        ):
            errors.append(
                f"{path}: forbidden direct cyber-to-physical path "
                f"{endpoint.get('key')} -> {destination}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="v3 directory",
    )
    parser.add_argument(
        "--federation-config",
        type=Path,
        action="append",
        default=[],
        help="optional HELICS JSON config to inspect for network bypass",
    )
    args = parser.parse_args()

    errors: list[str] = []
    errors += check_devices(load_yaml(args.root / "configs/der_devices.yaml"))
    errors += check_network(load_yaml(args.root / "configs/network_scenarios.yaml"))
    schema = json.loads(
        (args.root / "interfaces/cyber_message.schema.json").read_text(
            encoding="utf-8"
        )
    )
    errors += check_schema(schema)
    errors += check_markdown_links(args.root)
    for config in args.federation_config:
        errors += check_federation_bypass(config)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"GridEval v3 design validation FAILED ({len(errors)} error(s))")
        return 1
    print("GridEval v3 design validation PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


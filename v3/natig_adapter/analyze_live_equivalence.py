#!/usr/bin/env python3
"""Fail-closed post-run equivalence gate for the G4 benign experiment.

This module never launches a federation and never manufactures trace rows.
It compares two completed, normalized trace documents produced by independent
direct-reference and NATIG executions.  Execution sufficiency is evaluated
first; equivalence is not evaluated when either trace is incomplete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TRACE_SCHEMA = "grideval-g4-equivalence-trace/1.0"
REPORT_SCHEMA = "grideval-g4-equivalence-report/1.0"
DURATION_S = 840.0
SAMPLE_PERIOD_S = 10
EXPECTED_SAMPLE_TIMES = tuple(range(10, 841, SAMPLE_PERIOD_S))
WINDOWS = (
    (0, 0.0, 0.0),
    (60, 10.0, 0.0),
    (180, 0.0, 0.0),
    (240, -10.0, 0.0),
    (360, 0.0, 0.0),
    (420, 0.0, 10.0),
    (540, 0.0, 0.0),
    (600, 0.0, -10.0),
    (720, 0.0, 0.0),
)


def _expected_commands() -> tuple[dict[str, Any], ...]:
    expected = []
    for event_time_s, p_kw, q_kvar in WINDOWS:
        for point_index, value in enumerate((p_kw, q_kvar)):
            expected.append(
                {
                    "schedule_key": f"t{event_time_s:04d}-ao{point_index}",
                    "event_time_s": float(event_time_s),
                    "point_index": point_index,
                    "command_type": (
                        "active_power_setpoint"
                        if point_index == 0
                        else "reactive_setpoint"
                    ),
                    "value": value,
                    "unit": "kW" if point_index == 0 else "kvar",
                }
            )
    return tuple(expected)


EXPECTED_COMMANDS = _expected_commands()
_TOP_KEYS = {
    "schema_version",
    "path",
    "execution",
    "provenance",
    "commands",
    "applications",
    "samples",
}
_PROVENANCE_KEYS = {
    "source_artifacts",
    "producer",
    "normalization",
    "field_provenance",
    "comparison_qualifications",
}
_PRODUCER_KEYS = {"runner_sha256", "helics_version", "opender_version"}
_NORMALIZATION_KEYS = {
    "normalizer_sha256",
    "method",
    "is_new_execution",
}
_FIELD_PROVENANCE_KEYS = {"observed", "derived"}
_EXECUTION_KEYS = {"status", "start_time_s", "end_time_s", "duration_s"}
_COMMAND_KEYS = {
    "schedule_key",
    "event_time_s",
    "point_index",
    "command_type",
    "value",
    "unit",
    "accepted",
    "accepted_time_s",
    "command_id",
    "application_id",
}
_APPLICATION_KEYS = {
    "application_id",
    "command_id",
    "schedule_key",
    "point_index",
    "value",
    "unit",
    "applied_time_s",
}
_SAMPLE_KEYS = {"time_s", "p_kw", "q_kvar", "voltage_pu", "soc_pu"}


@dataclass(frozen=True)
class Tolerances:
    """Frozen numerical gate thresholds in the trace's declared units."""

    p_abs_kw: float = 1e-3
    q_abs_kvar: float = 1e-3
    voltage_abs_pu: float = 1e-4
    soc_abs_pu: float = 1e-6
    max_acceptance_latency_s: float = 10.0
    max_application_latency_s: float = 12.0
    acceptance_latency_delta_s: float = 10.0
    application_latency_delta_s: float = 10.0

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                or value < 0
            ):
                raise ValueError(f"tolerance {name} must be finite and nonnegative")


def _number(value: Any, label: str, errors: list[str]) -> float | None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        errors.append(f"{label} must be a finite number")
        return None
    return float(value)


def _integer(value: Any, label: str, errors: list[str]) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{label} must be an integer")
        return None
    return value


def load_trace(path: str | Path) -> dict[str, Any]:
    """Load JSON while rejecting duplicate object keys."""

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON field: {key}")
            value[key] = item
        return value

    source = Path(path)
    raw = source.read_text(encoding="utf-8")
    parsed = json.loads(raw, object_pairs_hook=pairs_hook)
    if not isinstance(parsed, dict):
        raise ValueError("trace root must be an object")
    return parsed


def _exact_keys(
    value: Any,
    expected: set[str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return False
    actual = set(value)
    if actual != expected:
        errors.append(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
        return False
    return True


def validate_execution(
    trace: dict[str, Any],
    *,
    expected_path: str,
) -> tuple[list[str], dict[str, Any]]:
    """Validate trace completeness, accepted commands, and application lineage."""

    errors: list[str] = []
    normalized: dict[str, Any] = {}
    if not _exact_keys(trace, _TOP_KEYS, expected_path, errors):
        return errors, normalized
    if trace["schema_version"] != TRACE_SCHEMA:
        errors.append(f"{expected_path}.schema_version is unsupported")
    if trace["path"] != expected_path:
        errors.append(f"{expected_path}.path does not match input role")

    provenance = trace["provenance"]
    if _exact_keys(
        provenance, _PROVENANCE_KEYS, f"{expected_path}.provenance", errors
    ):
        source_artifacts = provenance["source_artifacts"]
        if not isinstance(source_artifacts, list) or not source_artifacts:
            errors.append(
                f"{expected_path}.provenance.source_artifacts must be nonempty"
            )
        else:
            for index, artifact in enumerate(source_artifacts):
                label = (
                    f"{expected_path}.provenance.source_artifacts[{index}]"
                )
                if not _exact_keys(
                    artifact, {"path", "sha256", "bytes"}, label, errors
                ):
                    continue
                if not isinstance(artifact["path"], str) or not artifact["path"]:
                    errors.append(f"{label}.path must be a nonempty string")
                digest = artifact["sha256"]
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest)
                ):
                    errors.append(f"{label}.sha256 must be lowercase SHA-256")
                if (
                    not isinstance(artifact["bytes"], int)
                    or isinstance(artifact["bytes"], bool)
                    or artifact["bytes"] < 0
                ):
                    errors.append(f"{label}.bytes must be nonnegative integer")
        producer = provenance["producer"]
        if _exact_keys(
            producer, _PRODUCER_KEYS, f"{expected_path}.producer", errors
        ):
            for field in _PRODUCER_KEYS:
                if not isinstance(producer[field], str) or not producer[field]:
                    errors.append(
                        f"{expected_path}.producer.{field} must be nonempty"
                    )
        normalization = provenance["normalization"]
        if _exact_keys(
            normalization,
            _NORMALIZATION_KEYS,
            f"{expected_path}.normalization",
            errors,
        ):
            if normalization["is_new_execution"] is not False:
                errors.append(
                    f"{expected_path}.normalization must not claim execution"
                )
            for field in ("normalizer_sha256", "method"):
                if (
                    not isinstance(normalization[field], str)
                    or not normalization[field]
                ):
                    errors.append(
                        f"{expected_path}.normalization.{field} must be nonempty"
                    )
        fields = provenance["field_provenance"]
        if _exact_keys(
            fields,
            _FIELD_PROVENANCE_KEYS,
            f"{expected_path}.field_provenance",
            errors,
        ):
            for field in _FIELD_PROVENANCE_KEYS:
                if (
                    not isinstance(fields[field], list)
                    or not fields[field]
                    or not all(
                        isinstance(item, str) and item for item in fields[field]
                    )
                ):
                    errors.append(
                        f"{expected_path}.field_provenance.{field} "
                        "must be a nonempty string array"
                    )
        qualifications = provenance["comparison_qualifications"]
        if not isinstance(qualifications, list) or not all(
            isinstance(item, str) and item for item in qualifications
        ):
            errors.append(
                f"{expected_path}.comparison_qualifications "
                "must be a string array"
            )

    execution = trace["execution"]
    if _exact_keys(
        execution, _EXECUTION_KEYS, f"{expected_path}.execution", errors
    ):
        if execution["status"] != "complete":
            errors.append(f"{expected_path}.execution.status is not complete")
        start = _number(
            execution["start_time_s"],
            f"{expected_path}.execution.start_time_s",
            errors,
        )
        end = _number(
            execution["end_time_s"],
            f"{expected_path}.execution.end_time_s",
            errors,
        )
        duration = _number(
            execution["duration_s"],
            f"{expected_path}.execution.duration_s",
            errors,
        )
        if start != 0.0 or end != DURATION_S or duration != DURATION_S:
            errors.append(
                f"{expected_path}.execution must cover exactly 0..840 seconds"
            )

    commands = trace["commands"]
    if not isinstance(commands, list):
        errors.append(f"{expected_path}.commands must be an array")
        commands = []
    if len(commands) != len(EXPECTED_COMMANDS):
        errors.append(
            f"{expected_path}.commands must contain exactly 18 AO operations"
        )
    command_by_schedule: dict[str, dict[str, Any]] = {}
    command_ids: set[str] = set()
    application_ids: set[str] = set()
    for index, command in enumerate(commands):
        label = f"{expected_path}.commands[{index}]"
        if not _exact_keys(command, _COMMAND_KEYS, label, errors):
            continue
        if index >= len(EXPECTED_COMMANDS):
            continue
        expected = EXPECTED_COMMANDS[index]
        if not isinstance(command["schedule_key"], str):
            errors.append(f"{label}.schedule_key must be a string")
        _number(command["event_time_s"], f"{label}.event_time_s", errors)
        _integer(command["point_index"], f"{label}.point_index", errors)
        if not isinstance(command["command_type"], str):
            errors.append(f"{label}.command_type must be a string")
        _number(command["value"], f"{label}.value", errors)
        if not isinstance(command["unit"], str):
            errors.append(f"{label}.unit must be a string")
        for field in (
            "schedule_key",
            "event_time_s",
            "point_index",
            "command_type",
            "value",
            "unit",
        ):
            if command[field] != expected[field]:
                errors.append(
                    f"{label}.{field} violates paired 840s schedule"
                )
        if command["accepted"] is not True:
            errors.append(f"{label} was not accepted")
        accepted_time = _number(
            command["accepted_time_s"], f"{label}.accepted_time_s", errors
        )
        if accepted_time is not None and accepted_time < expected["event_time_s"]:
            errors.append(f"{label}.accepted_time_s precedes command event")
        for field, seen in (
            ("command_id", command_ids),
            ("application_id", application_ids),
        ):
            value = command[field]
            if not isinstance(value, str) or not value:
                errors.append(f"{label}.{field} must be a nonempty string")
            elif value in seen:
                errors.append(f"{expected_path} has duplicate {field}: {value}")
            else:
                seen.add(value)
        schedule_key = command["schedule_key"]
        if isinstance(schedule_key, str):
            if schedule_key in command_by_schedule:
                errors.append(
                    f"{expected_path} has duplicate schedule key: {schedule_key}"
                )
            command_by_schedule[schedule_key] = command

    applications = trace["applications"]
    if not isinstance(applications, list):
        errors.append(f"{expected_path}.applications must be an array")
        applications = []
    if len(applications) != len(EXPECTED_COMMANDS):
        errors.append(
            f"{expected_path}.applications must contain exactly 18 rows"
        )
    application_by_schedule: dict[str, dict[str, Any]] = {}
    observed_application_ids: set[str] = set()
    for index, application in enumerate(applications):
        label = f"{expected_path}.applications[{index}]"
        if not _exact_keys(application, _APPLICATION_KEYS, label, errors):
            continue
        if index >= len(EXPECTED_COMMANDS):
            continue
        expected = EXPECTED_COMMANDS[index]
        if not isinstance(application["schedule_key"], str):
            errors.append(f"{label}.schedule_key must be a string")
        _integer(application["point_index"], f"{label}.point_index", errors)
        _number(application["value"], f"{label}.value", errors)
        if not isinstance(application["unit"], str):
            errors.append(f"{label}.unit must be a string")
        if application["schedule_key"] != expected["schedule_key"]:
            errors.append(f"{label} is reordered or mapped to wrong schedule key")
        command = command_by_schedule.get(expected["schedule_key"])
        if command is not None:
            for field in ("application_id", "command_id"):
                if application[field] != command[field]:
                    errors.append(f"{label}.{field} breaks application lineage")
            for field in ("point_index", "value", "unit"):
                if application[field] != command[field]:
                    errors.append(f"{label}.{field} differs from accepted command")
            accepted_time = command.get("accepted_time_s")
            applied_time = _number(
                application["applied_time_s"],
                f"{label}.applied_time_s",
                errors,
            )
            if (
                applied_time is not None
                and isinstance(accepted_time, (int, float))
                and not isinstance(accepted_time, bool)
                and applied_time < float(accepted_time)
            ):
                errors.append(f"{label}.applied_time_s precedes acceptance")
        application_id = application["application_id"]
        if isinstance(application_id, str):
            if application_id in observed_application_ids:
                errors.append(
                    f"{expected_path} has duplicate applied application_id"
                )
            observed_application_ids.add(application_id)
        schedule_key = application["schedule_key"]
        if isinstance(schedule_key, str):
            application_by_schedule[schedule_key] = application
    if observed_application_ids != application_ids:
        errors.append(
            f"{expected_path} accepted/application lineage sets differ"
        )

    samples = trace["samples"]
    if not isinstance(samples, list):
        errors.append(f"{expected_path}.samples must be an array")
        samples = []
    if len(samples) != len(EXPECTED_SAMPLE_TIMES):
        errors.append(
            f"{expected_path}.samples must contain exactly "
            f"{len(EXPECTED_SAMPLE_TIMES)} ten-second rows"
        )
    sample_by_time: dict[int, dict[str, float]] = {}
    for index, sample in enumerate(samples):
        label = f"{expected_path}.samples[{index}]"
        if not _exact_keys(sample, _SAMPLE_KEYS, label, errors):
            continue
        if index >= len(EXPECTED_SAMPLE_TIMES):
            continue
        expected_time = EXPECTED_SAMPLE_TIMES[index]
        _integer(sample["time_s"], f"{label}.time_s", errors)
        if sample["time_s"] != expected_time:
            errors.append(f"{label}.time_s is missing, extra, or reordered")
        values: dict[str, float] = {}
        for field in ("p_kw", "q_kvar", "voltage_pu", "soc_pu"):
            parsed = _number(sample[field], f"{label}.{field}", errors)
            if parsed is not None:
                values[field] = parsed
        if "voltage_pu" in values and not (0.0 < values["voltage_pu"] <= 2.0):
            errors.append(f"{label}.voltage_pu is outside physical bounds")
        if "soc_pu" in values and not (0.0 <= values["soc_pu"] <= 1.0):
            errors.append(f"{label}.soc_pu is outside physical bounds")
        if sample["time_s"] == expected_time and len(values) == 4:
            sample_by_time[expected_time] = values

    normalized.update(
        {
            "commands": command_by_schedule,
            "applications": application_by_schedule,
            "samples": sample_by_time,
        }
    )
    return errors, normalized


def _latencies(
    normalized: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float]]:
    acceptance: dict[str, float] = {}
    application: dict[str, float] = {}
    for expected in EXPECTED_COMMANDS:
        key = expected["schedule_key"]
        command = normalized["commands"][key]
        applied = normalized["applications"][key]
        acceptance[key] = (
            float(command["accepted_time_s"]) - expected["event_time_s"]
        )
        application[key] = (
            float(applied["applied_time_s"]) - expected["event_time_s"]
        )
    return acceptance, application


def analyze_equivalence(
    direct: dict[str, Any],
    natig: dict[str, Any],
    *,
    tolerances: Tolerances = Tolerances(),
) -> dict[str, Any]:
    """Return separate execution and equivalence verdicts."""

    tolerances.validate()
    direct_errors, direct_normalized = validate_execution(
        direct, expected_path="direct_reference"
    )
    natig_errors, natig_normalized = validate_execution(
        natig, expected_path="natig"
    )
    execution_pass = not direct_errors and not natig_errors
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "scope": (
            "G4 benign post-run analysis; execution and equivalence are "
            "separate gates"
        ),
        "tolerances": asdict(tolerances),
        "input_traces": {
            "direct_reference": None,
            "natig": None,
        },
        "comparison_qualifications": [],
        "execution": {
            "status": "PASS" if execution_pass else "FAIL",
            "direct_reference_errors": direct_errors,
            "natig_errors": natig_errors,
        },
        "equivalence": {
            "status": "NOT_EVALUATED",
            "errors": [],
            "metrics": {},
        },
        "equivalence_claim_permitted": False,
    }
    if not execution_pass:
        return report

    errors: list[str] = []
    direct_producer = direct["provenance"]["producer"]
    natig_producer = natig["provenance"]["producer"]
    direct_helics = direct_producer["helics_version"]
    natig_helics = natig_producer["helics_version"]
    qualifications = sorted(
        set(direct["provenance"]["comparison_qualifications"])
        | set(natig["provenance"]["comparison_qualifications"])
    )
    if direct_helics != natig_helics:
        expected_version_text = (
            f"cross-version HELICS comparison: direct_reference={direct_helics}; "
            f"natig={natig_helics}"
        )
        if expected_version_text not in qualifications:
            errors.append(
                "HELICS runtime versions differ without exact cross-version "
                "comparison qualification"
            )
        else:
            report["comparison_qualifications"].append(expected_version_text)
    report["comparison_qualifications"].extend(
        item
        for item in qualifications
        if item not in report["comparison_qualifications"]
    )
    maxima = {
        "accepted_operation_count": len(EXPECTED_COMMANDS),
        "application_lineage_count": len(EXPECTED_COMMANDS),
        "paired_sample_count": len(EXPECTED_SAMPLE_TIMES),
        "p_abs_kw": 0.0,
        "q_abs_kvar": 0.0,
        "voltage_abs_pu": 0.0,
        "soc_abs_pu": 0.0,
        "direct_acceptance_latency_s": 0.0,
        "natig_acceptance_latency_s": 0.0,
        "acceptance_latency_delta_s": 0.0,
        "direct_application_latency_s": 0.0,
        "natig_application_latency_s": 0.0,
        "application_latency_delta_s": 0.0,
    }
    fields = (
        ("p_kw", "p_abs_kw", tolerances.p_abs_kw),
        ("q_kvar", "q_abs_kvar", tolerances.q_abs_kvar),
        ("voltage_pu", "voltage_abs_pu", tolerances.voltage_abs_pu),
        ("soc_pu", "soc_abs_pu", tolerances.soc_abs_pu),
    )
    for time_s in EXPECTED_SAMPLE_TIMES:
        direct_sample = direct_normalized["samples"][time_s]
        natig_sample = natig_normalized["samples"][time_s]
        for field, metric, limit in fields:
            difference = abs(direct_sample[field] - natig_sample[field])
            maxima[metric] = max(maxima[metric], difference)
            if difference > limit:
                errors.append(
                    f"sample t={time_s} {field} difference "
                    f"{difference} exceeds {limit}"
                )

    direct_acceptance, direct_application = _latencies(direct_normalized)
    natig_acceptance, natig_application = _latencies(natig_normalized)
    for expected in EXPECTED_COMMANDS:
        key = expected["schedule_key"]
        da = direct_acceptance[key]
        na = natig_acceptance[key]
        dp = direct_application[key]
        np = natig_application[key]
        maxima["direct_acceptance_latency_s"] = max(
            maxima["direct_acceptance_latency_s"], da
        )
        maxima["natig_acceptance_latency_s"] = max(
            maxima["natig_acceptance_latency_s"], na
        )
        maxima["acceptance_latency_delta_s"] = max(
            maxima["acceptance_latency_delta_s"], abs(da - na)
        )
        maxima["direct_application_latency_s"] = max(
            maxima["direct_application_latency_s"], dp
        )
        maxima["natig_application_latency_s"] = max(
            maxima["natig_application_latency_s"], np
        )
        maxima["application_latency_delta_s"] = max(
            maxima["application_latency_delta_s"], abs(dp - np)
        )
        if da > tolerances.max_acceptance_latency_s:
            errors.append(f"{key} direct acceptance latency exceeds bound")
        if na > tolerances.max_acceptance_latency_s:
            errors.append(f"{key} NATIG acceptance latency exceeds bound")
        if abs(da - na) > tolerances.acceptance_latency_delta_s:
            errors.append(f"{key} acceptance latency delta exceeds bound")
        if dp > tolerances.max_application_latency_s:
            errors.append(f"{key} direct application latency exceeds bound")
        if np > tolerances.max_application_latency_s:
            errors.append(f"{key} NATIG application latency exceeds bound")
        if abs(dp - np) > tolerances.application_latency_delta_s:
            errors.append(f"{key} application latency delta exceeds bound")

    equivalent = not errors
    report["equivalence"] = {
        "status": "PASS" if equivalent else "FAIL",
        "errors": errors,
        "metrics": maxima,
    }
    report["equivalence_claim_permitted"] = equivalent
    return report


def analyze_files(
    direct_path: str | Path,
    natig_path: str | Path,
    *,
    tolerances: Tolerances = Tolerances(),
) -> dict[str, Any]:
    """Fail closed on unreadable or invalid JSON inputs."""

    tolerances.validate()
    sources = {
        "direct_reference": Path(direct_path).resolve(),
        "natig": Path(natig_path).resolve(),
    }
    input_traces: dict[str, dict[str, Any]] = {}
    for role, source in sources.items():
        metadata: dict[str, Any] = {"path": str(source), "sha256": None}
        try:
            metadata["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        except OSError:
            pass
        input_traces[role] = metadata

    load_errors: dict[str, list[str]] = {
        "direct_reference_errors": [],
        "natig_errors": [],
    }
    traces: dict[str, dict[str, Any]] = {}
    for role, source, error_key in (
        (
            "direct_reference",
            sources["direct_reference"],
            "direct_reference_errors",
        ),
        ("natig", sources["natig"], "natig_errors"),
    ):
        try:
            traces[role] = load_trace(source)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            load_errors[error_key].append(f"trace load failed: {exc}")
    if len(traces) != 2:
        return {
            "schema_version": REPORT_SCHEMA,
            "scope": (
                "G4 benign post-run analysis; execution and equivalence are "
                "separate gates"
            ),
            "tolerances": asdict(tolerances),
            "input_traces": input_traces,
            "comparison_qualifications": [],
            "execution": {"status": "FAIL", **load_errors},
            "equivalence": {
                "status": "NOT_EVALUATED",
                "errors": [],
                "metrics": {},
            },
            "equivalence_claim_permitted": False,
        }
    report = analyze_equivalence(
        traces["direct_reference"],
        traces["natig"],
        tolerances=tolerances,
    )
    report["input_traces"] = input_traces
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-trace", type=Path, required=True)
    parser.add_argument("--natig-trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--p-abs-kw", type=float, default=1e-3)
    parser.add_argument("--q-abs-kvar", type=float, default=1e-3)
    parser.add_argument("--voltage-abs-pu", type=float, default=1e-4)
    parser.add_argument("--soc-abs-pu", type=float, default=1e-6)
    parser.add_argument("--max-acceptance-latency-s", type=float, default=10.0)
    parser.add_argument("--max-application-latency-s", type=float, default=12.0)
    parser.add_argument("--acceptance-latency-delta-s", type=float, default=10.0)
    parser.add_argument("--application-latency-delta-s", type=float, default=10.0)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing existing output: {args.output}")
    tolerances = Tolerances(
        p_abs_kw=args.p_abs_kw,
        q_abs_kvar=args.q_abs_kvar,
        voltage_abs_pu=args.voltage_abs_pu,
        soc_abs_pu=args.soc_abs_pu,
        max_acceptance_latency_s=args.max_acceptance_latency_s,
        max_application_latency_s=args.max_application_latency_s,
        acceptance_latency_delta_s=args.acceptance_latency_delta_s,
        application_latency_delta_s=args.application_latency_delta_s,
    )
    try:
        report = analyze_files(
            args.direct_trace, args.natig_trace, tolerances=tolerances
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["equivalence_claim_permitted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

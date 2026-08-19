#!/usr/bin/env python3
"""Normalize one pinned G3 direct-reference artifact without re-execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v3.natig_adapter.analyze_live_equivalence import (
    EXPECTED_COMMANDS,
    EXPECTED_SAMPLE_TIMES,
    TRACE_SCHEMA,
)


SOURCE_SHA256 = "b5874c606c943d7d40bc436ce90533168e0eb8f6027756e658045794675f195a"
PRODUCING_RUNNER_SHA256 = (
    "c402870c5e3467d0f319f6b50444718f9e65bee68650451340a04856d65ade27"
)
CURRENT_RUNNER_SHA256 = (
    "4e6e6f03ab6e0ccc43377449dcab83ac6daaac8c3df2462b9b425701c4d64a34"
)
DIRECT_HELICS_VERSION = "3.6.1 (2025-02-24)"
NATIG_HELICS_VERSION = "2.7.1"
CROSS_VERSION_QUALIFICATION = (
    "cross-version HELICS comparison: "
    f"direct_reference={DIRECT_HELICS_VERSION}; natig={NATIG_HELICS_VERSION}"
)
EXPECTED_IDENTITY = {
    "runner_sha256": PRODUCING_RUNNER_SHA256,
    "device_wrapper_sha256":
        "e3882462e7b3efce21c2102e10acedf472394e229d8579e58a26bb08922f9015",
    "der_devices_config_sha256":
        "c2c85271b90aae5b9f485144f37d317b2dee338d765ed880d9ce6d1ede2eea6d",
    "opender_version": "2.2.0",
    "opender_commit": "fe7877c664bc6c5eb3832499bf05e0f1dd1825c8",
    "helics_version": DIRECT_HELICS_VERSION,
    "expected_container_image_id":
        "sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7",
    "source_glm_sha256":
        "553eb2c4a3082057bba78249340adbd9f1be9d9a639206aec242e793f54ef888",
    "source_config_sha256":
        "b12a953b4182db0de97ca0d2a160919fcca642d68219d7ccd9fc5bdf718454f2",
    "effective_glm_sha256":
        "d6008f376371ff18b548f5f93971f162121ac7c91555c8b07358c27697983202",
    "effective_config_sha256":
        "2dd5a895d0eb0885835988ed845fe4d83e2417df13fd7b5b90d2a45057a5dac9",
    "legacy_block_sha256":
        "850bf20488b5d34410e12c0146acd859f143d5c999b34621c1f31189a99181ba",
}
EXPECTED_ARTIFACTS = {
    "1c_IEEE_123_feeder_0_EV4.csv": {
        "sha256": "1328b874ed2c2a15e25e0c4a195eb32d0c4e3e3ff35095a71f192b5033e26fec",
        "bytes": 5039,
    },
    "effective/1c_IEEE_123_feeder.glm": {
        "sha256": "d6008f376371ff18b548f5f93971f162121ac7c91555c8b07358c27697983202",
        "bytes": 158197,
    },
    "effective/g3_opender.json": {
        "sha256": "712d3f5f72107cef4e43d8935bec90d2c0c5c33d22bea9cfba6e39aeacebb7bd",
        "bytes": 762,
    },
    "effective/mainglm.json": {
        "sha256": "2dd5a895d0eb0885835988ed845fe4d83e2417df13fd7b5b90d2a45057a5dac9",
        "bytes": 1202,
    },
    "g3_der_ev4_coupling.csv": {
        "sha256": "b6855f193edbbef010a11bccd1146056546631f7c143dede03be04a813c0d7f7",
        "bytes": 4465,
    },
    "g3_node650_phase_c.csv": {
        "sha256": "8178db584e562e896620070d81479f6465764f6ec43587d31ee65d5fb18ee32a",
        "bytes": 3996,
    },
    "g3_swEV4_status.csv": {
        "sha256": "39c7492d5f673787cb6d9ecdcfc3ee2926300ee4a8832c3fa0ea5e79ce9649d8",
        "bytes": 2816,
    },
    "gridlabd.log": {
        "sha256": "4b610b56e36de75b44ace6660f64ea3e5b88e6f51914bbb01a6d26e07a11025a",
        "bytes": 26882,
    },
}
EXPECTED_ASSERTIONS = {
    "gridlabd_completed",
    "adapter_no_exception",
    "trace_reaches_duration",
    "trace_time_monotonic",
    "all_required_physical_recorders_present",
    "physical_csvs_parse_cleanly",
    "physical_recorders_reach_last_exchange",
    "legacy_ev4_storage_absent",
    "exactly_one_g3_coupling_object",
    "coupling_parent_is_l92",
    "coupling_not_parented_to_ev4",
    "swEV4_closed_for_entire_arm",
    "helics_has_no_swEV4_target",
    "helics_endpoints_empty",
    "finite_adapter_trace",
    "no_legacy_ev4_runtime_warning",
    "voltage_within_interface_test_range",
    "one_coupling_step_mapping_latency",
    "soc_bounded",
    "p_injection_sign_correct",
    "p_absorption_sign_correct",
    "q_injection_sign_correct",
    "q_absorption_sign_correct",
    "gridlabd_applied_p_injection",
    "gridlabd_applied_p_absorption",
    "gridlabd_applied_q_injection",
    "gridlabd_applied_q_absorption",
    "gridlabd_recovery_zero",
}
EXPECTED_TOP_KEYS = {
    "schema_version",
    "scope",
    "arm",
    "scenario",
    "coupling_step_s",
    "device_internal_step_s",
    "duration_s",
    "identity",
    "sign_convention",
    "schedule",
    "segments",
    "physical_mapping",
    "adapter_trace",
    "physical_traces",
    "process",
    "effective",
    "assertions",
    "artifacts",
    "success",
}
EXPECTED_ROW_KEYS = {
    "time_s",
    "segment",
    "desired_p_kw",
    "desired_q_kvar",
    "p_out_kw",
    "q_out_kvar",
    "feeder_load_w",
    "feeder_load_var",
    "terminal_voltage_v",
    "terminal_voltage_pu",
    "observed_gridlabd_load_w",
    "observed_gridlabd_load_var",
    "source_power_c_w",
    "source_power_c_var",
    "status",
    "soc_pu",
    "input_updates",
}
EXPECTED_SCHEDULE = (
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
NOMINAL_VOLTAGE_V = 2401.7771


class NormalizationError(RuntimeError):
    """The pinned evidence bundle cannot be normalized safely."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise NormalizationError(f"duplicate JSON field: {key}")
            value[key] = item
        return value

    try:
        parsed = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(f"cannot load source trace: {exc}") from exc
    if not isinstance(parsed, dict):
        raise NormalizationError("source trace root must be an object")
    return parsed


def _finite(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise NormalizationError(f"{label} must be finite")
    return float(value)


def _schedule_at(time_s: int) -> tuple[str, float, float]:
    for name, start, stop, p_kw, q_kvar in EXPECTED_SCHEDULE:
        if start <= time_s < stop:
            return name, p_kw, q_kvar
    if time_s == 840:
        return "terminal", 0.0, 0.0
    raise NormalizationError(f"time {time_s} is outside frozen schedule")


def _relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _artifact_metadata(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": _relative_or_absolute(path, repo_root),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def validate_document(
    document: dict[str, Any],
    *,
    bundle_dir: Path,
    repo_root: Path,
) -> list[dict[str, Any]]:
    """Validate every normalization prerequisite and return input metadata."""

    if set(document) != EXPECTED_TOP_KEYS:
        raise NormalizationError("source trace top-level fields changed")
    exact_scalars = {
        "schema_version": "1.0",
        "scope": (
            "G3 one-device physical-loop validation; no NATIG, "
            "cyber impairment, or attacker-effect claim"
        ),
        "arm": "pulse_coupling10",
        "scenario": "pulse",
        "coupling_step_s": 10,
        "device_internal_step_s": 1,
        "duration_s": 840,
        "success": True,
    }
    for field, expected in exact_scalars.items():
        if document[field] != expected or (
            isinstance(expected, int)
            and not isinstance(expected, bool)
            and isinstance(document[field], bool)
        ):
            raise NormalizationError(f"source {field} does not match pinned run")
    if document["identity"] != EXPECTED_IDENTITY:
        raise NormalizationError("source identity locks changed")

    expected_schedule = [
        {
            "name": name,
            "start_s": start,
            "stop_s": stop,
            "p_kw": p_kw,
            "q_kvar": q_kvar,
        }
        for name, start, stop, p_kw, q_kvar in EXPECTED_SCHEDULE
    ]
    if document["schedule"] != expected_schedule:
        raise NormalizationError("source schedule changed")
    assertions = document["assertions"]
    if (
        not isinstance(assertions, dict)
        or set(assertions) != EXPECTED_ASSERTIONS
        or any(value is not True for value in assertions.values())
    ):
        raise NormalizationError("not every exact source assertion is true")

    process = document["process"]
    if not isinstance(process, dict) or set(process) != {
        "gridlabd_returncode",
        "diagnostics",
        "run_error",
        "csv_parse_issues",
    }:
        raise NormalizationError("source process evidence shape changed")
    if process["gridlabd_returncode"] != 0 or process["run_error"] is not None:
        raise NormalizationError("source execution did not complete cleanly")
    issues = process["csv_parse_issues"]
    if (
        not isinstance(issues, dict)
        or set(issues) != {
            "g3_der_ev4_coupling.csv",
            "g3_node650_phase_c.csv",
            "g3_swEV4_status.csv",
            "1c_IEEE_123_feeder_0_EV4.csv",
        }
        or any(value != [] for value in issues.values())
    ):
        raise NormalizationError("source physical CSV parse issues are not empty")

    if document["artifacts"] != EXPECTED_ARTIFACTS:
        raise NormalizationError("source artifact lock table changed")
    metadata = []
    for relative, expected in EXPECTED_ARTIFACTS.items():
        path = bundle_dir / relative
        if not path.is_file():
            raise NormalizationError(f"missing source artifact: {relative}")
        actual = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        if actual != expected:
            raise NormalizationError(f"source artifact drift: {relative}")
        metadata.append(_artifact_metadata(path, repo_root))

    canonical_inputs = (
        repo_root / "examples/2bus-13bus/1c_IEEE_123_feeder.glm",
        repo_root / "examples/2bus-13bus/mainglm.json",
    )
    for path, expected in zip(
        canonical_inputs,
        (
            EXPECTED_IDENTITY["source_glm_sha256"],
            EXPECTED_IDENTITY["source_config_sha256"],
        ),
    ):
        if not path.is_file() or sha256(path) != expected:
            raise NormalizationError(f"canonical source identity drift: {path}")
        metadata.append(_artifact_metadata(path, repo_root))

    mapping = document["physical_mapping"]
    if (
        not isinstance(mapping, dict)
        or set(mapping) != {
            "expected_latency_s",
            "paired_sample_count",
            "max_applied_va_residual",
        }
        or mapping["expected_latency_s"] != 10
        or mapping["paired_sample_count"] != 82
        or _finite(
            mapping["max_applied_va_residual"],
            "physical_mapping.max_applied_va_residual",
        )
        > 0.1
    ):
        raise NormalizationError("source physical mapping evidence changed")

    rows = document["adapter_trace"]
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_SAMPLE_TIMES):
        raise NormalizationError("source must have exactly 84 adapter rows")
    for index, (row, expected_time) in enumerate(
        zip(rows, EXPECTED_SAMPLE_TIMES)
    ):
        label = f"adapter_trace[{index}]"
        if not isinstance(row, dict) or set(row) != EXPECTED_ROW_KEYS:
            raise NormalizationError(f"{label} fields changed")
        if row["time_s"] != float(expected_time):
            raise NormalizationError(f"{label} time is missing or reordered")
        segment, desired_p, desired_q = _schedule_at(expected_time)
        if (
            row["segment"] != segment
            or row["desired_p_kw"] != desired_p
            or row["desired_q_kvar"] != desired_q
        ):
            raise NormalizationError(f"{label} violates source schedule")
        values = {
            field: _finite(row[field], f"{label}.{field}")
            for field in (
                "p_out_kw",
                "q_out_kvar",
                "feeder_load_w",
                "feeder_load_var",
                "terminal_voltage_v",
                "terminal_voltage_pu",
                "observed_gridlabd_load_w",
                "observed_gridlabd_load_var",
                "source_power_c_w",
                "source_power_c_var",
                "soc_pu",
            )
        }
        if row["status"] != "Continuous Operation":
            raise NormalizationError(f"{label} device status is not continuous")
        if not (0.0 <= values["soc_pu"] <= 1.0):
            raise NormalizationError(f"{label} SOC is out of bounds")
        if not math.isclose(
            values["terminal_voltage_pu"],
            values["terminal_voltage_v"] / NOMINAL_VOLTAGE_V,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise NormalizationError(f"{label} voltage units are inconsistent")
        if not math.isclose(
            values["feeder_load_w"],
            -1000.0 * values["p_out_kw"],
            rel_tol=0.0,
            abs_tol=1e-9,
        ) or not math.isclose(
            values["feeder_load_var"],
            -1000.0 * values["q_out_kvar"],
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise NormalizationError(f"{label} P/Q sign mapping is inconsistent")
        updates = row["input_updates"]
        if (
            not isinstance(updates, list)
            or len(updates) != 3
            or not all(isinstance(value, bool) for value in updates)
        ):
            raise NormalizationError(f"{label} input update flags changed")
    return metadata


def normalize(
    *,
    source: Path,
    repo_root: Path,
) -> dict[str, Any]:
    """Normalize the exact artifact; this function does not write or execute."""

    source = source.resolve()
    repo_root = repo_root.resolve()
    if not source.is_file() or sha256(source) != SOURCE_SHA256:
        raise NormalizationError("source trace SHA-256 is not the pinned artifact")
    document = load_json(source)
    metadata = [
        _artifact_metadata(source, repo_root),
        *validate_document(
            document,
            bundle_dir=source.parent,
            repo_root=repo_root,
        ),
    ]
    normalizer_sha = sha256(Path(__file__).resolve())
    rows = document["adapter_trace"]
    commands = []
    applications = []
    for expected in EXPECTED_COMMANDS:
        key = expected["schedule_key"]
        event_time = int(expected["event_time_s"])
        observed = next(
            row for row in rows if row["time_s"] >= expected["event_time_s"]
        )
        observed_time = float(observed["time_s"])
        command_id = f"g3-direct-derived-{key}-command"
        application_id = f"g3-direct-derived-{key}-application"
        commands.append(
            {
                **expected,
                "accepted": True,
                "accepted_time_s": observed_time,
                "command_id": command_id,
                "application_id": application_id,
            }
        )
        applications.append(
            {
                "application_id": application_id,
                "command_id": command_id,
                "schedule_key": key,
                "point_index": expected["point_index"],
                "value": expected["value"],
                "unit": expected["unit"],
                "applied_time_s": observed_time,
            }
        )
        if event_time and observed_time != event_time:
            raise NormalizationError(
                f"no adapter observation at schedule boundary {event_time}"
            )
    samples = [
        {
            "time_s": int(row["time_s"]),
            "p_kw": float(row["p_out_kw"]),
            "q_kvar": float(row["q_out_kvar"]),
            "voltage_pu": float(row["terminal_voltage_pu"]),
            "soc_pu": float(row["soc_pu"]),
        }
        for row in rows
    ]
    return {
        "schema_version": TRACE_SCHEMA,
        "path": "direct_reference",
        "execution": {
            "status": "complete",
            "start_time_s": 0.0,
            "end_time_s": 840.0,
            "duration_s": 840.0,
        },
        "provenance": {
            "source_artifacts": metadata,
            "producer": {
                "runner_sha256": PRODUCING_RUNNER_SHA256,
                "helics_version": DIRECT_HELICS_VERSION,
                "opender_version": EXPECTED_IDENTITY["opender_version"],
            },
            "normalization": {
                "normalizer_sha256": normalizer_sha,
                "method": (
                    "create-once projection of exact G3 artifact; no process "
                    "was launched"
                ),
                "is_new_execution": False,
            },
            "field_provenance": {
                "observed": [
                    "execution completion, identity locks, assertions, and "
                    "84 P/Q/voltage/SOC samples are copied or checked from "
                    "the pinned G3 artifact",
                    "accepted_time_s and applied_time_s use the first observed "
                    "adapter row at or after each schedule boundary",
                ],
                "derived": [
                    "18 AO operation rows and deterministic path-local IDs "
                    "are projected from the exact nine-window P/Q schedule",
                    "accepted=true denotes successful direct schedule "
                    "assignment evidenced by source success and observations; "
                    "it is not gateway acceptance",
                ],
            },
            "comparison_qualifications": [
                CROSS_VERSION_QUALIFICATION,
                (
                    "historical producer source bytes are not the current "
                    f"workspace runner: producer={PRODUCING_RUNNER_SHA256}; "
                    f"current={CURRENT_RUNNER_SHA256}"
                ),
                (
                    "normalization is evidence transformation of an existing "
                    "completed G3 run, not a new direct-reference execution"
                ),
            ],
        },
        "commands": commands,
        "applications": applications,
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing existing output: {args.output}")
    try:
        result = normalize(source=args.source, repo_root=args.repo_root)
    except NormalizationError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except FileExistsError:
        parser.error(f"refusing existing output: {args.output}")
    print(
        json.dumps(
            {
                "status": "normalized_existing_execution",
                "source_sha256": SOURCE_SHA256,
                "output": str(args.output.resolve()),
                "equivalence_claim_permitted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

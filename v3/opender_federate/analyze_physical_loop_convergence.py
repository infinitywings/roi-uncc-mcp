#!/usr/bin/env python3
"""Analyze paired pulse/null G3 physical-loop coupling convergence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


STEPS = (1, 5, 10, 60)
SAMPLE_TIMES_S = (120, 300, 480, 660, 780)
EXPECTED_DEVICE_RESPONSE = {
    120: (10.0, 0.0),
    300: (-10.0, 0.0),
    480: (0.0, 10.0),
    660: (0.0, -10.0),
    780: (0.0, 0.0),
}
RESULT_NAME = "g3_physical_loop.json"
TIME_EPSILON_S = 1e-6


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} is missing or non-finite")
    return float(value)


def result_path(path: Path) -> Path:
    resolved = path / RESULT_NAME if path.is_dir() else path
    if not resolved.is_file():
        raise ValueError(f"Result not found: {resolved}")
    return resolved.resolve()


def load_result(path: Path, expected_step: int) -> tuple[Path, dict[str, Any]]:
    source = result_path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Result must be a JSON object: {source}")
    step = finite_number(data.get("coupling_step_s"), "coupling_step_s")
    if int(step) != expected_step or step != int(step):
        raise ValueError(
            f"Expected {expected_step}s result, found {step:g}s: {source}"
        )
    if not isinstance(data.get("adapter_trace"), list):
        raise ValueError(f"adapter_trace is missing: {source}")
    mapping = data.get("physical_mapping")
    if not isinstance(mapping, dict):
        raise ValueError(f"physical_mapping is missing: {source}")
    finite_number(
        mapping.get("max_applied_va_residual"),
        "physical_mapping.max_applied_va_residual",
    )
    return source, data


def trace_row(result: dict[str, Any], time_s: float) -> dict[str, Any]:
    matches = [
        row
        for row in result["adapter_trace"]
        if isinstance(row, dict)
        and isinstance(row.get("time_s"), (int, float))
        and abs(float(row["time_s"]) - time_s) <= TIME_EPSILON_S
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one adapter_trace row at {time_s:g}s; "
            f"found {len(matches)}"
        )
    return matches[0]


def paired_response(
    pulse: dict[str, Any], null: dict[str, Any], time_s: int
) -> dict[str, Any]:
    pulse_row = trace_row(pulse, time_s)
    null_row = trace_row(null, time_s)
    fields = (
        "p_out_kw",
        "q_out_kvar",
        "terminal_voltage_pu",
        "source_power_c_w",
        "source_power_c_var",
    )
    pulse_values = {
        field: finite_number(pulse_row.get(field), f"pulse {field}")
        for field in fields
    }
    null_values = {
        field: finite_number(null_row.get(field), f"null {field}")
        for field in fields
    }
    return {
        "time_s": time_s,
        "segment": pulse_row.get("segment"),
        "device_p_delta_kw": (
            pulse_values["p_out_kw"] - null_values["p_out_kw"]
        ),
        "device_q_delta_kvar": (
            pulse_values["q_out_kvar"] - null_values["q_out_kvar"]
        ),
        "terminal_voltage_delta_pu": (
            pulse_values["terminal_voltage_pu"]
            - null_values["terminal_voltage_pu"]
        ),
        "source_p_delta_w": (
            pulse_values["source_power_c_w"]
            - null_values["source_power_c_w"]
        ),
        "source_q_delta_var": (
            pulse_values["source_power_c_var"]
            - null_values["source_power_c_var"]
        ),
    }


def identity_subset(result: dict[str, Any]) -> dict[str, Any]:
    identity = result.get("identity")
    if not isinstance(identity, dict):
        return {}
    keys = (
        "opender_commit",
        "source_glm_sha256",
        "source_config_sha256",
        "device_wrapper_sha256",
        "der_devices_config_sha256",
        "expected_container_image_id",
    )
    return {key: identity.get(key) for key in keys if key in identity}


def null_schedule_is_zero(result: dict[str, Any]) -> bool:
    schedule = result.get("schedule")
    return bool(schedule) and all(
        isinstance(item, dict)
        and finite_number(item.get("p_kw"), "null schedule p_kw") == 0.0
        and finite_number(item.get("q_kvar"), "null schedule q_kvar") == 0.0
        for item in schedule
    )


def schedule_names(result: dict[str, Any]) -> list[Any]:
    schedule = result.get("schedule")
    if not isinstance(schedule, list):
        return []
    return [item.get("name") if isinstance(item, dict) else None for item in schedule]


def max_error(
    candidate: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    field: str,
) -> float:
    return max(
        abs(float(row[field]) - float(ref[field]))
        for row, ref in zip(candidate, reference)
    )


def analyze_arm(
    step: int,
    pulse_path: Path,
    pulse: dict[str, Any],
    null_path: Path,
    null: dict[str, Any],
    reference: list[dict[str, Any]] | None,
    tolerances: dict[str, float],
) -> dict[str, Any]:
    responses = [
        paired_response(pulse, null, time_s) for time_s in SAMPLE_TIMES_S
    ]
    expected_p_error_kw = max(
        abs(row["device_p_delta_kw"] - EXPECTED_DEVICE_RESPONSE[row["time_s"]][0])
        for row in responses
    )
    expected_q_error_kvar = max(
        abs(
            row["device_q_delta_kvar"]
            - EXPECTED_DEVICE_RESPONSE[row["time_s"]][1]
        )
        for row in responses
    )
    source_p_balance_residual_w = max(
        abs(
            row["source_p_delta_w"]
            + 1000.0 * row["device_p_delta_kw"]
        )
        for row in responses
    )
    source_q_balance_residual_var = max(
        abs(
            row["source_q_delta_var"]
            + 1000.0 * row["device_q_delta_kvar"]
        )
        for row in responses
    )
    if reference is None:
        convergence = {
            "reference_arm": True,
            "max_device_p_error_kw": 0.0,
            "max_device_q_error_kvar": 0.0,
            "max_voltage_error_pu": 0.0,
            "max_source_p_error_w": 0.0,
            "max_source_q_error_var": 0.0,
        }
    else:
        convergence = {
            "reference_arm": False,
            "max_device_p_error_kw": max_error(
                responses, reference, "device_p_delta_kw"
            ),
            "max_device_q_error_kvar": max_error(
                responses, reference, "device_q_delta_kvar"
            ),
            "max_voltage_error_pu": max_error(
                responses, reference, "terminal_voltage_delta_pu"
            ),
            "max_source_p_error_w": max_error(
                responses, reference, "source_p_delta_w"
            ),
            "max_source_q_error_var": max_error(
                responses, reference, "source_q_delta_var"
            ),
        }

    pulse_residual = finite_number(
        pulse["physical_mapping"]["max_applied_va_residual"],
        "pulse max_applied_va_residual",
    )
    null_residual = finite_number(
        null["physical_mapping"]["max_applied_va_residual"],
        "null max_applied_va_residual",
    )
    pulse_identity = identity_subset(pulse)
    null_identity = identity_subset(null)
    gates = {
        "pulse_run_success": pulse.get("success") is True,
        "null_run_success": null.get("success") is True,
        "internal_device_step_is_1s": (
            pulse.get("device_internal_step_s") == 1
            and null.get("device_internal_step_s") == 1
        ),
        "pulse_null_identity_match": (
            bool(pulse_identity) and pulse_identity == null_identity
        ),
        "pulse_null_segment_names_match": (
            bool(schedule_names(pulse))
            and schedule_names(pulse) == schedule_names(null)
        ),
        "null_schedule_is_zero": null_schedule_is_zero(null),
        "all_common_samples_present": len(responses) == len(SAMPLE_TIMES_S),
        "pulse_local_mapping_residual_within_tolerance": (
            pulse_residual <= tolerances["local_mapping_residual_va"]
        ),
        "null_local_mapping_residual_within_tolerance": (
            null_residual <= tolerances["local_mapping_residual_va"]
        ),
        "device_p_matches_declared_pulses": (
            expected_p_error_kw <= tolerances["device_p_error_kw"]
        ),
        "device_q_matches_declared_pulses": (
            expected_q_error_kvar <= tolerances["device_q_error_kvar"]
        ),
        "device_p_converges_to_1s": (
            convergence["max_device_p_error_kw"]
            <= tolerances["device_p_error_kw"]
        ),
        "device_q_converges_to_1s": (
            convergence["max_device_q_error_kvar"]
            <= tolerances["device_q_error_kvar"]
        ),
        "voltage_response_converges_to_1s": (
            convergence["max_voltage_error_pu"]
            <= tolerances["voltage_error_pu"]
        ),
        "source_p_response_converges_to_1s": (
            convergence["max_source_p_error_w"]
            <= tolerances["source_p_error_w"]
        ),
        "source_q_response_converges_to_1s": (
            convergence["max_source_q_error_var"]
            <= tolerances["source_q_error_var"]
        ),
        "paired_source_p_balance_within_tolerance": (
            source_p_balance_residual_w
            <= tolerances["source_p_balance_residual_w"]
        ),
        "paired_source_q_balance_within_tolerance": (
            source_q_balance_residual_var
            <= tolerances["source_q_balance_residual_var"]
        ),
    }
    return {
        "step_s": step,
        "inputs": {
            "pulse": {
                "path": str(pulse_path),
                "sha256": sha256(pulse_path),
                "arm": pulse.get("arm"),
            },
            "null": {
                "path": str(null_path),
                "sha256": sha256(null_path),
                "arm": null.get("arm"),
            },
        },
        "run_success": {
            "pulse": pulse.get("success") is True,
            "null": null.get("success") is True,
        },
        "local_mapping": {
            "pulse_max_applied_va_residual": pulse_residual,
            "null_max_applied_va_residual": null_residual,
        },
        "declared_pulse_error": {
            "max_p_error_kw": expected_p_error_kw,
            "max_q_error_kvar": expected_q_error_kvar,
        },
        "paired_source_balance": {
            "max_p_residual_w": source_p_balance_residual_w,
            "max_q_residual_var": source_q_balance_residual_var,
        },
        "paired_responses": responses,
        "convergence_vs_1s": convergence,
        "gates": gates,
        "passes": all(gates.values()),
    }


def resolve_inputs(args: argparse.Namespace) -> dict[int, dict[str, Path]]:
    explicit_values = {
        step: {
            "pulse": getattr(args, f"pulse_{step}"),
            "null": getattr(args, f"null_{step}"),
        }
        for step in STEPS
    }
    any_explicit = any(
        path is not None
        for pair in explicit_values.values()
        for path in pair.values()
    )
    template_mode = any(
        value is not None
        for value in (args.root, args.pulse_template, args.null_template)
    )
    if any_explicit and template_mode:
        raise ValueError(
            "Use either templates or explicit pulse/null directories, not both"
        )
    if any_explicit:
        missing = [
            f"--{kind}-{step}"
            for step, pair in explicit_values.items()
            for kind, path in pair.items()
            if path is None
        ]
        if missing:
            raise ValueError(
                "Explicit mode requires all eight paths; missing "
                + ", ".join(missing)
            )
        return explicit_values
    if (
        args.root is None
        or args.pulse_template is None
        or args.null_template is None
    ):
        raise ValueError(
            "Template mode requires --root, --pulse-template, and "
            "--null-template"
        )
    return {
        step: {
            "pulse": args.root / args.pulse_template.format(step=step),
            "null": args.root / args.null_template.format(step=step),
        }
        for step in STEPS
    }


def markdown(result: dict[str, Any]) -> str:
    selected = result["selected_coarsest_step_s"]
    lines = [
        "# G3 OpenDER Physical-Loop Convergence",
        "",
        f"Verdict: **{'PASS' if result['gate_pass'] else 'FAIL'}**",
        "",
        (
            "Selected coarsest passing step: "
            + (f"**{selected} s**" if selected is not None else "**none**")
        ),
        "",
        "All responses are paired pulse-minus-null values at common adapter "
        "sample times. The 1-second arm is the convergence reference.",
        "",
        "## Explicit tolerances",
        "",
        "| Metric | Limit |",
        "|---|---:|",
        f"| Local mapping residual | {result['tolerances']['local_mapping_residual_va']:.6g} VA |",
        f"| Device P response | {result['tolerances']['device_p_error_kw']:.6g} kW |",
        f"| Device Q response | {result['tolerances']['device_q_error_kvar']:.6g} kvar |",
        f"| Voltage response vs 1 s | {result['tolerances']['voltage_error_pu']:.6g} pu |",
        f"| Source P response vs 1 s | {result['tolerances']['source_p_error_w']:.6g} W |",
        f"| Source Q response vs 1 s | {result['tolerances']['source_q_error_var']:.6g} var |",
        f"| Paired source P balance residual | {result['tolerances']['source_p_balance_residual_w']:.6g} W |",
        f"| Paired source Q balance residual | {result['tolerances']['source_q_balance_residual_var']:.6g} var |",
        "",
        "## Arm summary",
        "",
        "| Step | Pass | Pulse/null mapping residual (VA) | "
        "Voltage error (pu) | Source P/Q error | Source P/Q balance |",
        "|---:|:---:|---:|---:|---:|---:|",
    ]
    for step in STEPS:
        arm = result["arms"][str(step)]
        mapping = arm["local_mapping"]
        convergence = arm["convergence_vs_1s"]
        balance = arm["paired_source_balance"]
        lines.append(
            "| {step} | {passed} | {pulse:.6g} / {null:.6g} | "
            "{voltage:.6g} | {p:.6g} W / {q:.6g} var | "
            "{balance_p:.6g} W / {balance_q:.6g} var |".format(
                step=step,
                passed="yes" if arm["passes"] else "no",
                pulse=mapping["pulse_max_applied_va_residual"],
                null=mapping["null_max_applied_va_residual"],
                voltage=convergence["max_voltage_error_pu"],
                p=convergence["max_source_p_error_w"],
                q=convergence["max_source_q_error_var"],
                balance_p=balance["max_p_residual_w"],
                balance_q=balance["max_q_residual_var"],
            )
        )
    lines.extend(
        [
            "",
            "Common sample times: "
            + ", ".join(f"{time_s} s" for time_s in SAMPLE_TIMES_S),
            "",
            "## Failed gates",
            "",
        ]
    )
    failures = 0
    for step in STEPS:
        failed = [
            name
            for name, passed in result["arms"][str(step)]["gates"].items()
            if not passed
        ]
        for name in failed:
            lines.append(f"- {step} s: `{name}`")
            failures += 1
    if not failures:
        lines.append("- None.")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument(
        "--pulse-template",
        help="Directory template relative to root, e.g. pulse_coupling{step}_r1",
    )
    parser.add_argument(
        "--null-template",
        help="Directory template relative to root, e.g. null_coupling{step}_r1",
    )
    for step in STEPS:
        parser.add_argument(f"--pulse-{step}", type=Path)
        parser.add_argument(f"--null-{step}", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument(
        "--max-local-mapping-residual-va", type=float, default=0.1
    )
    parser.add_argument("--max-device-p-error-kw", type=float, default=0.1)
    parser.add_argument("--max-device-q-error-kvar", type=float, default=0.1)
    parser.add_argument("--max-voltage-error-pu", type=float, default=1e-4)
    parser.add_argument("--max-source-p-error-w", type=float, default=2000.0)
    parser.add_argument(
        "--max-source-q-error-var", type=float, default=2000.0
    )
    parser.add_argument(
        "--max-source-p-balance-residual-w", type=float, default=2000.0
    )
    parser.add_argument(
        "--max-source-q-balance-residual-var", type=float, default=2000.0
    )
    args = parser.parse_args()

    for output in (args.output_json, args.output_markdown):
        if output.exists():
            parser.error(f"Refusing to overwrite existing output: {output}")
    tolerance_values = (
        args.max_local_mapping_residual_va,
        args.max_device_p_error_kw,
        args.max_device_q_error_kvar,
        args.max_voltage_error_pu,
        args.max_source_p_error_w,
        args.max_source_q_error_var,
        args.max_source_p_balance_residual_w,
        args.max_source_q_balance_residual_var,
    )
    if any(
        not math.isfinite(value) or value < 0 for value in tolerance_values
    ):
        parser.error("Tolerances must be finite and non-negative")

    try:
        inputs = resolve_inputs(args)
        loaded = {
            step: {
                kind: load_result(path, step)
                for kind, path in pair.items()
            }
            for step, pair in inputs.items()
        }
        tolerances = {
            "local_mapping_residual_va": (
                args.max_local_mapping_residual_va
            ),
            "device_p_error_kw": args.max_device_p_error_kw,
            "device_q_error_kvar": args.max_device_q_error_kvar,
            "voltage_error_pu": args.max_voltage_error_pu,
            "source_p_error_w": args.max_source_p_error_w,
            "source_q_error_var": args.max_source_q_error_var,
            "source_p_balance_residual_w": (
                args.max_source_p_balance_residual_w
            ),
            "source_q_balance_residual_var": (
                args.max_source_q_balance_residual_var
            ),
        }
        arms: dict[str, Any] = {}
        reference = None
        for step in STEPS:
            pulse_path, pulse = loaded[step]["pulse"]
            null_path, null = loaded[step]["null"]
            arm = analyze_arm(
                step,
                pulse_path,
                pulse,
                null_path,
                null,
                reference,
                tolerances,
            )
            arms[str(step)] = arm
            if step == 1:
                reference = arm["paired_responses"]
        passing = [step for step in STEPS if arms[str(step)]["passes"]]
        selected = max(passing) if passing else None
        result = {
            "schema_version": "1.0",
            "gate": "G3 coupling-step convergence",
            "scope": (
                "Paired pulse/null OpenDER physical-loop convergence; "
                "no NATIG, DNP3, cyber impairment, or attacker-effect claim"
            ),
            "required_steps_s": list(STEPS),
            "reference_step_s": 1,
            "common_sample_times_s": list(SAMPLE_TIMES_S),
            "tolerances": tolerances,
            "arms": arms,
            "passing_steps_s": passing,
            "selected_coarsest_step_s": selected,
            "gate_pass": arms["1"]["passes"] and selected is not None,
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_markdown.write_text(markdown(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate_pass": result["gate_pass"],
                "selected_coarsest_step_s": selected,
                "output_json": str(args.output_json),
                "output_markdown": str(args.output_markdown),
            },
            indent=2,
        )
    )
    return 0 if result["gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

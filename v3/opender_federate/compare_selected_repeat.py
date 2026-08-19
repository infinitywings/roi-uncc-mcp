#!/usr/bin/env python3
"""Compare selected-cadence G3 physical-loop repeat runs.

This is a create-once evidence tool: it refuses to overwrite either requested
output.  Numerical leaves are compared field-by-field with a declared
absolute/relative tolerance, while structure and discrete values are exact.
The report separately records whether all numerical values were exactly equal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "g3-selected-cadence-repeatability-v1"
RUN_FILENAME = "g3_physical_loop.json"
ABS_TOL = 1.0e-12
REL_TOL = 1.0e-12
SELECTED_COUPLING_STEP_S = 10.0
ALLOWED_CONFIG_LABEL_KEYS = frozenset({"coreName", "name", "logfile"})
MAX_MISMATCH_EXAMPLES = 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_run_path(value: Path) -> Path:
    path = value / RUN_FILENAME if value.is_dir() else value
    if not path.is_file():
        raise FileNotFoundError(f"run JSON does not exist: {path}")
    return path


def load_run(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"run JSON must contain an object: {path}")
    return value


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def new_comparison_state() -> dict[str, Any]:
    return {
        "structure_exact": True,
        "discrete_exact": True,
        "numeric_exact": True,
        "numeric_within_tolerance": True,
        "numeric_value_count": 0,
        "numeric_mismatch_count": 0,
        "numeric_nonexact_count": 0,
        "max_abs_difference": 0.0,
        "max_relative_difference": 0.0,
        "numeric_fields": defaultdict(
            lambda: {
                "count": 0,
                "nonexact_count": 0,
                "outside_tolerance_count": 0,
                "max_abs_difference": 0.0,
                "max_relative_difference": 0.0,
            }
        ),
        "mismatch_examples": [],
    }


def add_mismatch(state: dict[str, Any], kind: str, path: str, left: Any, right: Any) -> None:
    if len(state["mismatch_examples"]) < MAX_MISMATCH_EXAMPLES:
        state["mismatch_examples"].append(
            {"kind": kind, "path": path, "left": left, "right": right}
        )


def compare_tree(left: Any, right: Any, path: str, state: dict[str, Any]) -> None:
    if is_number(left) and is_number(right):
        a = float(left)
        b = float(right)
        state["numeric_value_count"] += 1
        field = state["numeric_fields"][path]
        field["count"] += 1

        finite = math.isfinite(a) and math.isfinite(b)
        exact = finite and a == b
        within = finite and math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
        abs_difference = abs(a - b) if finite else math.inf
        scale = max(abs(a), abs(b))
        relative_difference = (
            abs_difference / scale if finite and scale > 0.0 else abs_difference
        )

        state["max_abs_difference"] = max(state["max_abs_difference"], abs_difference)
        state["max_relative_difference"] = max(
            state["max_relative_difference"], relative_difference
        )
        field["max_abs_difference"] = max(field["max_abs_difference"], abs_difference)
        field["max_relative_difference"] = max(
            field["max_relative_difference"], relative_difference
        )

        if not exact:
            state["numeric_exact"] = False
            state["numeric_nonexact_count"] += 1
            field["nonexact_count"] += 1
        if not within:
            state["numeric_within_tolerance"] = False
            state["numeric_mismatch_count"] += 1
            field["outside_tolerance_count"] += 1
            add_mismatch(state, "numeric", path, left, right)
        return

    if isinstance(left, dict) and isinstance(right, dict):
        left_keys = set(left)
        right_keys = set(right)
        if left_keys != right_keys:
            state["structure_exact"] = False
            add_mismatch(
                state,
                "mapping_keys",
                path,
                sorted(left_keys - right_keys),
                sorted(right_keys - left_keys),
            )
        for key in sorted(left_keys & right_keys):
            compare_tree(left[key], right[key], f"{path}.{key}", state)
        return

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            state["structure_exact"] = False
            add_mismatch(state, "list_length", path, len(left), len(right))
        for a, b in zip(left, right):
            compare_tree(a, b, f"{path}[]", state)
        return

    if type(left) is not type(right):
        state["structure_exact"] = False
        state["discrete_exact"] = False
        add_mismatch(
            state,
            "type",
            path,
            type(left).__name__,
            type(right).__name__,
        )
    elif left != right:
        state["discrete_exact"] = False
        add_mismatch(state, "discrete", path, left, right)


def finish_comparison(state: dict[str, Any]) -> dict[str, Any]:
    fields = {
        key: value
        for key, value in sorted(state.pop("numeric_fields").items())
    }
    state["numeric_fields"] = fields
    return state


def compare_values(left: Any, right: Any, root: str) -> dict[str, Any]:
    state = new_comparison_state()
    compare_tree(left, right, root, state)
    return finish_comparison(state)


def config_difference_paths(left: Any, right: Any, path: str = "$") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(config_difference_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list) and isinstance(right, list):
        paths = []
        if len(left) != len(right):
            paths.append(f"{path}.length")
        for index, (a, b) in enumerate(zip(left, right)):
            paths.extend(config_difference_paths(a, b, f"{path}[{index}]"))
        return paths
    return [] if left == right else [path]


def normalize_config_execution_labels(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "<EXECUTION_LABEL>"
                if key in ALLOWED_CONFIG_LABEL_KEYS and isinstance(child, str)
                else normalize_config_execution_labels(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [normalize_config_execution_labels(child) for child in value]
    return value


def compare_identity(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_identity = left.get("identity", {})
    right_identity = right.get("identity", {})
    keys = sorted(set(left_identity) | set(right_identity))
    exact_by_field = {
        key: left_identity.get(key) == right_identity.get(key) for key in keys
    }

    left_config = left.get("effective", {}).get("configuration")
    right_config = right.get("effective", {}).get("configuration")
    config_paths = config_difference_paths(left_config, right_config)
    allowed_paths_only = bool(config_paths) and all(
        path.rsplit(".", 1)[-1] in ALLOWED_CONFIG_LABEL_KEYS
        for path in config_paths
    )
    normalized_config_equal = (
        normalize_config_execution_labels(left_config)
        == normalize_config_execution_labels(right_config)
    )

    config_hash_exact = exact_by_field.get("effective_config_sha256", False)
    config_hash_exception_used = (
        not config_hash_exact and allowed_paths_only and normalized_config_equal
    )
    config_hash_ok = config_hash_exact or config_hash_exception_used
    non_config_identity_exact = all(
        exact
        for key, exact in exact_by_field.items()
        if key != "effective_config_sha256"
    )

    return {
        "ok": non_config_identity_exact and config_hash_ok,
        "exact": all(exact_by_field.values()),
        "exact_by_field": exact_by_field,
        "effective_config_hash_exception": {
            "used": config_hash_exception_used,
            "allowed": True,
            "policy": (
                "A differing effective_config_sha256 is allowed only when the "
                "parsed effective configurations differ exclusively at "
                "coreName, name, and/or logfile, and become identical after "
                "those execution-label values are normalized."
            ),
            "raw_config_difference_paths": config_paths,
            "allowed_paths_only": allowed_paths_only,
            "normalized_config_equal": normalized_config_equal,
        },
    }


def process_is_successful(run: dict[str, Any]) -> bool:
    process = run.get("process", {})
    parse_issues = process.get("csv_parse_issues", {})
    no_parse_issues = not parse_issues or (
        isinstance(parse_issues, dict) and all(not value for value in parse_issues.values())
    )
    return bool(
        run.get("success") is True
        and process.get("gridlabd_returncode") == 0
        and process.get("run_error") is None
        and no_parse_issues
    )


def assertions_all_true(run: dict[str, Any]) -> bool:
    assertions = run.get("assertions")
    return bool(
        isinstance(assertions, dict)
        and assertions
        and all(value is True for value in assertions.values())
    )


def compare_pair(
    label: str,
    expected_scenario: str,
    left_path: Path,
    right_path: Path,
) -> dict[str, Any]:
    left = load_run(left_path)
    right = load_run(right_path)

    identity = compare_identity(left, right)
    adapter = compare_values(
        left.get("adapter_trace"), right.get("adapter_trace"), "$.adapter_trace"
    )
    physical = compare_values(
        left.get("physical_traces"), right.get("physical_traces"), "$.physical_traces"
    )

    left_assertions = left.get("assertions")
    right_assertions = right.get("assertions")
    checks = {
        "scenario_matches_expected": (
            left.get("scenario") == expected_scenario
            and right.get("scenario") == expected_scenario
        ),
        "selected_coupling_cadence": (
            float(left.get("coupling_step_s", math.nan)) == SELECTED_COUPLING_STEP_S
            and float(right.get("coupling_step_s", math.nan)) == SELECTED_COUPLING_STEP_S
        ),
        "timing_parameters_exact": all(
            left.get(key) == right.get(key)
            for key in ("coupling_step_s", "device_internal_step_s", "duration_s")
        ),
        "identity_ok": identity["ok"],
        "adapter_structure_exact": adapter["structure_exact"],
        "adapter_discrete_exact": adapter["discrete_exact"],
        "adapter_numeric_within_tolerance": adapter["numeric_within_tolerance"],
        "physical_structure_exact": physical["structure_exact"],
        "physical_discrete_exact": physical["discrete_exact"],
        "physical_numeric_within_tolerance": physical["numeric_within_tolerance"],
        "both_processes_successful": (
            process_is_successful(left) and process_is_successful(right)
        ),
        "assertion_sets_and_values_exact": left_assertions == right_assertions,
        "all_assertions_true": (
            assertions_all_true(left) and assertions_all_true(right)
        ),
    }

    return {
        "label": label,
        "expected_scenario": expected_scenario,
        "left": {
            "path": str(left_path),
            "sha256": sha256_file(left_path),
            "arm": left.get("arm"),
            "scenario": left.get("scenario"),
            "success": left.get("success"),
        },
        "right": {
            "path": str(right_path),
            "sha256": sha256_file(right_path),
            "arm": right.get("arm"),
            "scenario": right.get("scenario"),
            "success": right.get("success"),
        },
        "tolerance": {"absolute": ABS_TOL, "relative": REL_TOL},
        "identity": identity,
        "adapter_trace": adapter,
        "physical_traces": physical,
        "process": {
            "left_successful": process_is_successful(left),
            "right_successful": process_is_successful(right),
            "process_objects_exact": left.get("process") == right.get("process"),
        },
        "assertions": {
            "left_count": len(left_assertions) if isinstance(left_assertions, dict) else 0,
            "right_count": len(right_assertions) if isinstance(right_assertions, dict) else 0,
            "sets_and_values_exact": left_assertions == right_assertions,
            "left_all_true": assertions_all_true(left),
            "right_all_true": assertions_all_true(right),
        },
        "checks": checks,
        "success": all(checks.values()),
    }


def yes_no(value: bool) -> str:
    return "PASS" if value else "FAIL"


def render_markdown(report: dict[str, Any]) -> str:
    verdict = yes_no(report["success"])
    lines = [
        "# G3 Selected-Cadence Repeatability",
        "",
        f"**Verdict: {verdict}.** Two independent repeat pairs at the selected "
        f"{SELECTED_COUPLING_STEP_S:g}-second coupling cadence were compared.",
        "",
        "| Pair | Identity | Adapter structure/text | Adapter numeric | Physical structure/text | Physical numeric | Process/assertions |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pair in report["pairs"]:
        checks = pair["checks"]
        lines.append(
            "| {label} | {identity} | {adapter_discrete} | {adapter_numeric} | "
            "{physical_discrete} | {physical_numeric} | {process} |".format(
                label=pair["label"],
                identity=yes_no(checks["identity_ok"]),
                adapter_discrete=yes_no(
                    checks["adapter_structure_exact"]
                    and checks["adapter_discrete_exact"]
                ),
                adapter_numeric=yes_no(
                    checks["adapter_numeric_within_tolerance"]
                ),
                physical_discrete=yes_no(
                    checks["physical_structure_exact"]
                    and checks["physical_discrete_exact"]
                ),
                physical_numeric=yes_no(
                    checks["physical_numeric_within_tolerance"]
                ),
                process=yes_no(
                    checks["both_processes_successful"]
                    and checks["assertion_sets_and_values_exact"]
                    and checks["all_assertions_true"]
                ),
            )
        )

    lines.extend(
        [
            "",
            "## Numerical audit",
            "",
            f"The acceptance tolerance is `abs_tol={ABS_TOL:.0e}` and "
            f"`rel_tol={REL_TOL:.0e}`. Exact numerical equality is reported "
            "separately and is not weakened by the tolerance gate.",
            "",
            "| Pair | Adapter values | Adapter nonexact | Adapter max abs diff | "
            "Physical values | Physical nonexact | Physical max abs diff |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for pair in report["pairs"]:
        adapter = pair["adapter_trace"]
        physical = pair["physical_traces"]
        lines.append(
            f"| {pair['label']} | {adapter['numeric_value_count']} | "
            f"{adapter['numeric_nonexact_count']} | "
            f"{adapter['max_abs_difference']:.17g} | "
            f"{physical['numeric_value_count']} | "
            f"{physical['numeric_nonexact_count']} | "
            f"{physical['max_abs_difference']:.17g} |"
        )

    lines.extend(
        [
            "",
            "## Identity policy",
            "",
            "All identity fields must match exactly. The sole narrow exception is "
            "`effective_config_sha256`: a hash difference may pass only when the "
            "parsed HELICS configurations differ exclusively in `coreName`, "
            "`name`, or `logfile` and are identical after those execution labels "
            "are normalized. Publications, subscriptions, object/property "
            "bindings, units, periods, topology, and all other configuration "
            "content remain load-bearing.",
            "",
        ]
    )
    for pair in report["pairs"]:
        exception = pair["identity"]["effective_config_hash_exception"]
        lines.append(
            f"- **{pair['label']}:** identity exact = "
            f"`{str(pair['identity']['exact']).lower()}`; execution-label "
            f"exception used = `{str(exception['used']).lower()}`."
        )

    lines.extend(
        [
            "",
            "## Process and assertion audit",
            "",
        ]
    )
    for pair in report["pairs"]:
        lines.append(
            f"- **{pair['label']}:** both processes successful = "
            f"`{str(pair['checks']['both_processes_successful']).lower()}`; "
            f"assertion sets/values exact = "
            f"`{str(pair['checks']['assertion_sets_and_values_exact']).lower()}`; "
            f"all assertions true = "
            f"`{str(pair['checks']['all_assertions_true']).lower()}` "
            f"({pair['assertions']['left_count']} assertions per run)."
        )

    lines.extend(
        [
            "",
            "## Scope",
            "",
            "This gate establishes rerun repeatability for the recorded selected-"
            "cadence pulse and null arms. It does not establish correctness of the "
            "physical model, external validity, or repeatability at other coupling "
            "cadences/platforms.",
            "",
        ]
    )
    return "\n".join(lines)


def exclusive_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pulse-a", required=True, type=Path)
    parser.add_argument("--pulse-b", required=True, type=Path)
    parser.add_argument("--null-a", required=True, type=Path)
    parser.add_argument("--null-b", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-markdown", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for output in (args.output_json, args.output_markdown):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite create-once output: {output}")

    pulse_a = resolve_run_path(args.pulse_a)
    pulse_b = resolve_run_path(args.pulse_b)
    null_a = resolve_run_path(args.null_a)
    null_b = resolve_run_path(args.null_b)

    pairs = [
        compare_pair("pulse selected-cadence repeat", "pulse", pulse_a, pulse_b),
        compare_pair("null selected-cadence repeat", "null", null_a, null_b),
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "scope": (
            "Selected-cadence repeatability of pulse and null G3 physical-loop "
            "runs; no Docker execution is performed by this comparator."
        ),
        "comparator": {
            "path": str(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
        },
        "selected_coupling_step_s": SELECTED_COUPLING_STEP_S,
        "tolerance": {"absolute": ABS_TOL, "relative": REL_TOL},
        "pairs": pairs,
        "success": all(pair["success"] for pair in pairs),
    }

    json_text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    markdown_text = render_markdown(report)
    exclusive_write(args.output_json, json_text)
    try:
        exclusive_write(args.output_markdown, markdown_text)
    except Exception:
        args.output_json.unlink()
        raise

    print(
        f"{yes_no(report['success'])}: wrote {args.output_json} and "
        f"{args.output_markdown}"
    )
    return 0 if report["success"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

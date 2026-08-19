#!/usr/bin/env python3
"""Quantify numerical reproducibility across two NATIG benign-run outputs.

The byte-level comparison remains the primary exact-reproducibility check.  This
diagnostic separates structural/textual differences from floating-point
round-off in the GridLAB-D CSV recorders.
"""

from __future__ import annotations

import argparse
import csv
import cmath
import json
import math
import re
from pathlib import Path
from typing import Any


FLOAT_RE = re.compile(
    r"(?<![A-Za-z_])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?"
)
POLAR_RE = re.compile(
    r"^([-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)"
    r"([-+](?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)d$"
)
# Post-hoc diagnostic tolerances selected after the exact-hash comparison
# failed.  They are intentionally labeled and must not be represented as
# preregistered acceptance criteria.
ABSOLUTE_TOLERANCE = 1e-4
SCALED_TOLERANCE = 1e-6


def comparable_cell(a: str, b: str) -> tuple[str, list[tuple[float, float]]]:
    """Classify cells and return paired numeric tokens when shapes match."""
    if a == b:
        return "exact", []
    a_numbers = FLOAT_RE.findall(a)
    b_numbers = FLOAT_RE.findall(b)
    if (
        a_numbers
        and len(a_numbers) == len(b_numbers)
        and FLOAT_RE.sub("#", a) == FLOAT_RE.sub("#", b)
    ):
        return "numeric", list(zip(map(float, a_numbers), map(float, b_numbers)))
    return "structural", []


def within_tolerance(absolute_error: float, scaled_error: float) -> bool:
    return absolute_error <= ABSOLUTE_TOLERANCE or scaled_error <= SCALED_TOLERANCE


def polar_pair(a: str, b: str) -> tuple[complex, complex] | None:
    a_match = POLAR_RE.fullmatch(a)
    b_match = POLAR_RE.fullmatch(b)
    if not a_match or not b_match:
        return None
    a_mag, a_angle = map(float, a_match.groups())
    b_mag, b_angle = map(float, b_match.groups())
    return (
        cmath.rect(a_mag, math.radians(a_angle)),
        cmath.rect(b_mag, math.radians(b_angle)),
    )


def load_csv(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            row
            for row in csv.reader(
                line for line in handle if not line.startswith("#")
            )
        ]


def compare_csv(a_path: Path, b_path: Path) -> dict[str, Any]:
    a_rows = load_csv(a_path)
    b_rows = load_csv(b_path)
    result: dict[str, Any] = {
        "rows_a": len(a_rows),
        "rows_b": len(b_rows),
        "row_count_match": len(a_rows) == len(b_rows),
        "row_width_mismatches": 0,
        "row_key_mismatches": 0,
        "structural_cell_mismatches": 0,
        "numeric_cell_mismatches": 0,
        "numeric_scalar_mismatches": 0,
        "numeric_scalars_compared": 0,
        "polar_cells_compared": 0,
        "numeric_tolerance_violations": 0,
        "polar_tolerance_violations": 0,
        "snapshot_vector_tolerance_violations": 0,
        "max_absolute_error": 0.0,
        "max_scaled_error": 0.0,
        "max_physical_absolute_error": 0.0,
        "max_physical_scaled_error": 0.0,
        "max_error_location": None,
    }
    for row_index, (a_row, b_row) in enumerate(zip(a_rows, b_rows)):
        if len(a_row) != len(b_row):
            result["row_width_mismatches"] += 1
        if a_row and b_row and a_row[0] != b_row[0]:
            result["row_key_mismatches"] += 1
        # GridLAB-D currdump/voltdump snapshots store alternating magnitude and
        # angle-in-radians columns.  Compare those pairs as complex vectors so
        # the undefined angle of an exactly zero vector does not create a false
        # divergence.
        snapshot_vectors: set[int] = set()
        if a_rows and a_rows[0] == b_rows[0] and row_index > 0:
            header = a_rows[0]
            for column_index in range(1, min(len(header) - 1, len(a_row) - 1)):
                if header[column_index].endswith("_mag") and header[
                    column_index + 1
                ].endswith("_angle"):
                    snapshot_vectors.update((column_index, column_index + 1))
                    try:
                        a_vector = cmath.rect(
                            float(a_row[column_index]), float(a_row[column_index + 1])
                        )
                        b_vector = cmath.rect(
                            float(b_row[column_index]), float(b_row[column_index + 1])
                        )
                    except ValueError:
                        result["structural_cell_mismatches"] += 1
                        continue
                    absolute_error = abs(a_vector - b_vector)
                    scaled_error = absolute_error / max(
                        1.0, abs(a_vector), abs(b_vector)
                    )
                    result["max_physical_absolute_error"] = max(
                        result["max_physical_absolute_error"], absolute_error
                    )
                    result["max_physical_scaled_error"] = max(
                        result["max_physical_scaled_error"], scaled_error
                    )
                    if not within_tolerance(absolute_error, scaled_error):
                        result["snapshot_vector_tolerance_violations"] += 1
        for column_index, (a_cell, b_cell) in enumerate(zip(a_row, b_row)):
            if column_index in snapshot_vectors:
                continue
            polar = polar_pair(a_cell, b_cell)
            if polar is not None:
                result["polar_cells_compared"] += 1
                a_vector, b_vector = polar
                absolute_error = abs(a_vector - b_vector)
                scaled_error = absolute_error / max(
                    1.0, abs(a_vector), abs(b_vector)
                )
                result["max_physical_absolute_error"] = max(
                    result["max_physical_absolute_error"], absolute_error
                )
                result["max_physical_scaled_error"] = max(
                    result["max_physical_scaled_error"], scaled_error
                )
                if not within_tolerance(absolute_error, scaled_error):
                    result["polar_tolerance_violations"] += 1
                continue
            kind, pairs = comparable_cell(a_cell, b_cell)
            if kind == "structural":
                result["structural_cell_mismatches"] += 1
                continue
            if kind != "numeric":
                continue
            result["numeric_cell_mismatches"] += 1
            for scalar_index, (a_value, b_value) in enumerate(pairs):
                result["numeric_scalars_compared"] += 1
                if a_value == b_value:
                    continue
                result["numeric_scalar_mismatches"] += 1
                absolute_error = abs(a_value - b_value)
                scaled_error = absolute_error / max(1.0, abs(a_value), abs(b_value))
                result["max_physical_absolute_error"] = max(
                    result["max_physical_absolute_error"], absolute_error
                )
                result["max_physical_scaled_error"] = max(
                    result["max_physical_scaled_error"], scaled_error
                )
                if not within_tolerance(absolute_error, scaled_error):
                    result["numeric_tolerance_violations"] += 1
                if (
                    scaled_error > result["max_scaled_error"]
                    or (
                        math.isclose(scaled_error, result["max_scaled_error"])
                        and absolute_error > result["max_absolute_error"]
                    )
                ):
                    result["max_absolute_error"] = absolute_error
                    result["max_scaled_error"] = scaled_error
                    result["max_error_location"] = {
                        "row": row_index + 1,
                        "column": column_index + 1,
                        "scalar": scalar_index + 1,
                        "run_a": a_value,
                        "run_b": b_value,
                    }
    result["structurally_equal"] = (
        result["row_count_match"]
        and result["row_width_mismatches"] == 0
        and result["row_key_mismatches"] == 0
        and result["structural_cell_mismatches"] == 0
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    csv_a = {
        path.relative_to(args.run_a).as_posix(): path
        for path in args.run_a.rglob("*.csv")
        if "physical" in path.relative_to(args.run_a).parts
    }
    csv_b = {
        path.relative_to(args.run_b).as_posix(): path
        for path in args.run_b.rglob("*.csv")
        if "physical" in path.relative_to(args.run_b).parts
    }
    all_paths = sorted(set(csv_a) | set(csv_b))
    files: dict[str, Any] = {}
    missing: list[str] = []
    for path in all_paths:
        if path not in csv_a or path not in csv_b:
            missing.append(path)
            continue
        files[path] = compare_csv(csv_a[path], csv_b[path])

    structural_failures = [
        path for path, result in files.items() if not result["structurally_equal"]
    ]
    aggregate = {
        "file_set_match": set(csv_a) == set(csv_b),
        "file_count": len(all_paths),
        "missing_files": missing,
        "structural_failure_count": len(structural_failures),
        "structural_failures": structural_failures,
        "numeric_cell_mismatches": sum(
            result["numeric_cell_mismatches"] for result in files.values()
        ),
        "numeric_scalar_mismatches": sum(
            result["numeric_scalar_mismatches"] for result in files.values()
        ),
        "numeric_scalars_compared": sum(
            result["numeric_scalars_compared"] for result in files.values()
        ),
        "polar_cells_compared": sum(
            result["polar_cells_compared"] for result in files.values()
        ),
        "numeric_tolerance_violations": sum(
            result["numeric_tolerance_violations"] for result in files.values()
        ),
        "polar_tolerance_violations": sum(
            result["polar_tolerance_violations"] for result in files.values()
        ),
        "snapshot_vector_tolerance_violations": sum(
            result["snapshot_vector_tolerance_violations"]
            for result in files.values()
        ),
        "max_absolute_error": max(
            (result["max_absolute_error"] for result in files.values()), default=0.0
        ),
        "max_scaled_error": max(
            (result["max_scaled_error"] for result in files.values()), default=0.0
        ),
        "max_physical_absolute_error": max(
            (result["max_physical_absolute_error"] for result in files.values()),
            default=0.0,
        ),
        "max_physical_scaled_error": max(
            (result["max_physical_scaled_error"] for result in files.values()),
            default=0.0,
        ),
    }
    assertions = {
        "same_physical_csv_file_set": aggregate["file_set_match"],
        "no_missing_files": not missing,
        "all_csvs_structurally_equal": not structural_failures,
        "all_numeric_differences_within_posthoc_hybrid_tolerance": (
            aggregate["numeric_tolerance_violations"] == 0
            and aggregate["polar_tolerance_violations"] == 0
            and aggregate["snapshot_vector_tolerance_violations"] == 0
        ),
    }
    output = {
        "schema_version": "1.0",
        "scope": "Post-hoc numeric diagnosis; does not replace exact hash comparison.",
        "run_a": str(args.run_a.resolve()),
        "run_b": str(args.run_b.resolve()),
        "posthoc_absolute_tolerance": ABSOLUTE_TOLERANCE,
        "posthoc_scaled_tolerance": SCALED_TOLERANCE,
        "posthoc_acceptance_rule": (
            "absolute_error <= 1e-4 OR "
            "abs(a-b)/max(1,abs(a),abs(b)) <= 1e-6"
        ),
        "scaled_error_definition": "abs(a-b)/max(1,abs(a),abs(b))",
        "aggregate": aggregate,
        "assertions": assertions,
        "files": files,
        "success": all(assertions.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        f"success={output['success']} files={len(files)} "
        f"structural_failures={len(structural_failures)} "
        f"max_scaled_error={aggregate['max_scaled_error']:.6g}"
    )
    return 0 if output["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

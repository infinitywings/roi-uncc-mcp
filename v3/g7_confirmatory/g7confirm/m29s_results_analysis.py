"""Reproducible descriptive analysis for the frozen M29-S Attempt 4 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ARM_LABELS = {
    "IA3-SX": "Deterministic compiler",
    "IA5-OC": "Oracle ceiling",
    "IA4-C1": "Single pass, no retrieval",
    "IA4-C1R": "Single pass, retrieval",
    "IA4-FS": "Flat + self revision",
    "IA4-FSR": "Flat + self + retrieval",
    "IA4-FV": "Flat + validator",
    "IA4-FVR": "Flat + validator + retrieval",
    "IA4-SS": "Staged + self",
    "IA4-SSR": "Staged + self + retrieval",
    "IA4-SV": "Staged + validator",
    "IA4-SVR": "Staged + validator + retrieval",
}
SPLITS = ("development", "held_out")
FLAT_ARMS = {
    "IA4-C1", "IA4-C1R", "IA4-FS", "IA4-FSR", "IA4-FV", "IA4-FVR"
}
STAGED_ARMS = {"IA4-SS", "IA4-SSR", "IA4-SV", "IA4-SVR"}
INTERFACE_PAIRS = (
    ("Self revision, no retrieval", "IA4-SS", "IA4-FS"),
    ("Self revision, retrieval", "IA4-SSR", "IA4-FSR"),
    ("Validator, no retrieval", "IA4-SV", "IA4-FV"),
    ("Validator, retrieval", "IA4-SVR", "IA4-FVR"),
)


class M29SResultsError(RuntimeError):
    """Raised when the frozen result set is incomplete or inconsistent."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            M29SResultsError(f"non-finite value in {path}: {value}")
        ),
    )


def _source(root: Path, name: str) -> dict[str, Any]:
    path = root / name
    if not path.is_file():
        raise M29SResultsError(f"missing source artifact: {name}")
    return {"path": name, "sha256": sha256_file(path)}


def _arm_summary(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for arm_id, label in ARM_LABELS.items():
        for split in SPLITS:
            rows = [
                row
                for row in cells
                if row["arm_id"] == arm_id and row["split"] == split
            ]
            result.append(
                {
                    "arm_id": arm_id,
                    "arm": label,
                    "split": "Development" if split == "development" else "Held-out",
                    "exact_successes": sum(
                        row["endpoints"]["all_slot_program_exact"] for row in rows
                    ),
                    "conditions": len(rows),
                    "exact_rate": round(
                        sum(
                            row["endpoints"]["all_slot_program_exact"]
                            for row in rows
                        )
                        / len(rows),
                        6,
                    ),
                    "final_contract_violations": sum(
                        row["endpoints"]["final_contract_violation"] for row in rows
                    ),
                    "invalid_outputs": sum(
                        row["accounting"]["invalid_outputs"] for row in rows
                    ),
                    "model_calls": sum(
                        row["accounting"]["model_calls"] for row in rows
                    ),
                }
            )
    return result


def _construct_summary(
    cells: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    constructs = sorted({row["construct"] for row in cells})
    for split in SPLITS:
        for construct in constructs:
            for interface, arms in (
                ("Flat LLM", FLAT_ARMS),
                ("Staged LLM", STAGED_ARMS),
                ("Deterministic", {"IA3-SX"}),
                ("Oracle", {"IA5-OC"}),
            ):
                rows = [
                    row
                    for row in cells
                    if row["split"] == split
                    and row["construct"] == construct
                    and row["arm_id"] in arms
                ]
                successes = sum(
                    row["endpoints"]["all_slot_program_exact"] for row in rows
                )
                result.append(
                    {
                        "split": (
                            "Development" if split == "development" else "Held-out"
                        ),
                        "construct": construct.replace("_", " ").title(),
                        "interface": interface,
                        "exact_successes": successes,
                        "cells": len(rows),
                        "exact_rate": round(successes / len(rows), 6),
                    }
                )
    return result


def _slot_summary(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for split in SPLITS:
        rows = [
            row
            for row in cells
            if row["split"] == split and row["arm_id"] in FLAT_ARMS
        ]
        for slot in rows[0]["endpoints"]["per_slot_exact"]:
            exact = sum(row["endpoints"]["per_slot_exact"][slot] for row in rows)
            result.append(
                {
                    "split": "Development" if split == "development" else "Held-out",
                    "slot": slot,
                    "exact": exact,
                    "cells": len(rows),
                    "exact_rate": round(exact / len(rows), 6),
                }
            )
    return result


def _two_sided_sign_p(left_wins: int, right_wins: int) -> float:
    trials = left_wins + right_wins
    if trials == 0:
        return 1.0
    tail = sum(
        math.comb(trials, value)
        for value in range(min(left_wins, right_wins) + 1)
    )
    return min(1.0, 2 * tail * (0.5**trials))


def _pooled_interface_contrasts(
    cells: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {
        (row["arm_id"], row["condition_id"]): row
        for row in cells
    }
    condition_ids = sorted({row["condition_id"] for row in cells})
    result: list[dict[str, Any]] = []
    for label, staged_arm, flat_arm in INTERFACE_PAIRS:
        staged_wins = 0
        flat_wins = 0
        ties = 0
        for condition_id in condition_ids:
            staged = bool(
                by_key[(staged_arm, condition_id)]["endpoints"][
                    "all_slot_program_exact"
                ]
            )
            flat = bool(
                by_key[(flat_arm, condition_id)]["endpoints"][
                    "all_slot_program_exact"
                ]
            )
            if staged and not flat:
                staged_wins += 1
            elif flat and not staged:
                flat_wins += 1
            else:
                ties += 1
        result.append(
            {
                "contrast": label,
                "staged_arm": staged_arm,
                "flat_arm": flat_arm,
                "staged_wins": staged_wins,
                "flat_wins": flat_wins,
                "ties": ties,
                "discordant_pairs": staged_wins + flat_wins,
                "two_sided_exact_sign_p": round(
                    _two_sided_sign_p(staged_wins, flat_wins), 9
                ),
            }
        )
    return result


def _staged_final_failures(
    cells: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in cells:
        if row["arm_id"] not in STAGED_ARMS:
            continue
        failure = str(row.get("failure_class") or "")
        final = failure.split(";final:", 1)[-1]
        if "finish reason: length" in final:
            category = "Completion length"
        elif "authority order drift" in final:
            category = "Ledger authority order"
        elif "deterministic slot projection" in final:
            category = "Slot-program projection"
        else:
            category = "Other"
        counts[category] += 1
    return [
        {"failure_category": key, "cells": value, "share": round(value / 128, 6)}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_analysis(root: Path) -> dict[str, Any]:
    primary = strict_json(root / "primary_receipt.json")
    addendum = strict_json(root / "independent_audit_addendum.json")
    if primary.get("status") != "passed" or primary.get("issues") != []:
        raise M29SResultsError("primary receipt is not integrity-clean")
    if addendum.get("status") != "passed" or addendum.get("issues") != []:
        raise M29SResultsError("independent audit addendum is not clean")
    paths = sorted(root.glob("cells/*/*/*.json"))
    cells = [strict_json(path) for path in paths]
    if len(cells) != 384:
        raise M29SResultsError(f"expected 384 cells, observed {len(cells)}")
    model_calls = sum(row["accounting"]["model_calls"] for row in cells)
    if model_calls != 576:
        raise M29SResultsError(f"expected 576 model calls, observed {model_calls}")
    body = {
        "schema_version": "grideval-g7-m29s-results-analysis/v1",
        "classification": "PRELIMINARY_ONLY",
        "execution_contract_id": primary["execution_contract_id"],
        "source_artifacts": [
            _source(root, "contract.json"),
            _source(root, "development_receipt.json"),
            _source(root, "development_freeze.json"),
            _source(root, "held_out_receipt.json"),
            _source(root, "primary_receipt.json"),
            _source(root, "independent_audit_receipt.json"),
            _source(root, "independent_audit_addendum.json"),
        ],
        "cell_manifest_sha256": sha256_value(
            [
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in paths
            ]
        ),
        "metric_definition": {
            "exact_success": "All eleven semantic slot values, required evidence lineage, and staged artifacts when applicable match the frozen order-sensitive campaign metric.",
            "cohort": "Sixteen conditions per split and arm; thirty-two paired conditions when development and held-out are pooled descriptively.",
            "inference_boundary": "Exact sign tests are descriptive sensitivity checks. PRELIMINARY_ONLY evidence does not authorize confirmatory inference.",
        },
        "arm_summary": _arm_summary(cells),
        "construct_summary": _construct_summary(cells),
        "flat_slot_summary": _slot_summary(cells),
        "pooled_interface_contrasts": _pooled_interface_contrasts(cells),
        "staged_final_failure_summary": _staged_final_failures(cells),
        "audit_resolution": {
            "original_audit_id": addendum["prior_audit"]["audit_id"],
            "original_issue_count": addendum["prior_audit"]["issue_count"],
            "addendum_id": addendum["audit_addendum_id"],
            "addendum_status": addendum["status"],
            "frozen_evidence_modified": addendum["resolution"][
                "frozen_campaign_or_evidence_modified"
            ],
        },
        "model_calls": model_calls,
        "maximum_cumulative_model_calls": 816,
        "authorized_cumulative_ceiling": 1000,
        "m29b_authorized": False,
    }
    return {"analysis_id": f"m29sanalysis_{sha256_value(body)}", **body}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    result = build_analysis(root)
    output = args.output.resolve() if args.output else root / "analysis_snapshot.json"
    if args.verify:
        stored = strict_json(output)
        issues = [] if canonical_json(stored) == canonical_json(result) else [
            "analysis_snapshot_mismatch"
        ]
        print(canonical_json({"issues": issues}))
        raise SystemExit(0 if not issues else 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(canonical_json({"analysis_id": result["analysis_id"], "path": str(output)}))


if __name__ == "__main__":
    main()

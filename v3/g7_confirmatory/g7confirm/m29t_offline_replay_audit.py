"""Independent audit of the M29-T zero-call replay receipt."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import m29s_independent_audit_v4_addendum as source_audit


base = source_audit.base
ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "m29t_offline_replay_plan.json"
FLAT_ARMS = {
    "IA4-C1",
    "IA4-C1R",
    "IA4-FS",
    "IA4-FSR",
    "IA4-FV",
    "IA4-FVR",
}
STAGED_ARMS = {"IA4-SS", "IA4-SSR", "IA4-SV", "IA4-SVR"}
LLM_ARMS = FLAT_ARMS | STAGED_ARMS
SLOT_KEYS = tuple(base.SLOT_KEYS)
UNORDERED_SLOTS = {"allowed_targets", "forbidden_windows"}
AUTHORITY_ORDER = tuple(source_audit.parent.v3.AUTHORITY_ORDER)
STAGES = (
    "O0_recorded",
    "O1_saved_json",
    "O2_canonical_arrays",
    "O3_tool_ledger",
    "O4_tool_projection",
    "O5_tool_ledger_projection",
)


class M29TIndependentAuditError(RuntimeError):
    """Raised when an independently audited source is malformed."""


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise M29TIndependentAuditError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_response(text: str) -> dict[str, Any]:
    value = json.loads(
        text,
        object_pairs_hook=_reject_pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(
            M29TIndependentAuditError(f"non-finite JSON value: {token}")
        ),
    )
    if not isinstance(value, dict):
        raise M29TIndependentAuditError("saved response is not an object")
    return value


def _response(cell: Mapping[str, Any]) -> Mapping[str, Any] | None:
    calls = int(cell.get("accounting", {}).get("model_calls", 0))
    value = cell.get("revision_response") if calls == 2 else cell.get("initial_response")
    return value if isinstance(value, Mapping) else None


def _draft(cell: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str, str | None]:
    accepted = cell.get("final_draft")
    if isinstance(accepted, Mapping):
        return copy.deepcopy(dict(accepted)), "accepted_final_draft", None
    response = _response(cell)
    if response is None:
        return None, "no_saved_final_response", "response_absent"
    content = response.get("content")
    if not isinstance(content, str):
        return None, "saved_response_unparseable", "content_absent"
    try:
        return _parse_response(content), "recovered_saved_json", None
    except Exception as exc:
        return None, "saved_response_unparseable", type(exc).__name__


def _visible(cell: Mapping[str, Any]) -> dict[str, Any]:
    request = cell["initial_request"]
    messages = request["messages"]
    if len(messages) < 2 or messages[1].get("role") != "user":
        raise M29TIndependentAuditError("malformed visible input")
    value = json.loads(messages[1]["content"])
    if not isinstance(value, dict):
        raise M29TIndependentAuditError("visible input is not an object")
    return value


def _ledger(visible: Mapping[str, Any]) -> dict[str, Any]:
    evidence = visible["visible_evidence"]
    records = evidence["records"]
    active_authorities = {
        row["authority"] for row in records if row["status"] == "active"
    }
    return {
        "schema_version": "grideval-g7-m29s-evidence-ledger/v1",
        "condition_id": evidence["condition_id"],
        "active_evidence_ids": sorted(
            row["record_id"] for row in records if row["status"] == "active"
        ),
        "superseded_evidence_ids": sorted(
            row["record_id"] for row in records if row["status"] == "superseded"
        ),
        "expired_evidence_ids": sorted(
            row["record_id"] for row in records if row["status"] == "expired"
        ),
        "unresolved_conflict_ids": [],
        "authority_order": [
            authority for authority in AUTHORITY_ORDER if authority in active_authorities
        ],
        "visible_input_digest": base.sha256_value(visible),
    }


def _semantic(value: Any, slot: str, canonical_arrays: bool) -> Any:
    if canonical_arrays and slot in UNORDERED_SLOTS and isinstance(value, list):
        return sorted(value)
    return value


def _score(
    draft: Mapping[str, Any] | None,
    interface: str,
    oracle: Mapping[str, Any],
    visible: Mapping[str, Any],
    canonical_arrays: bool,
) -> dict[str, Any]:
    program_value = draft.get("strategy_program") if isinstance(draft, Mapping) else None
    program = program_value if isinstance(program_value, Mapping) else None
    expected_program = oracle["strategy_program"]
    per_slot = {
        slot: bool(
            program is not None
            and base.canonical_json(
                _semantic(program.get(slot), slot, canonical_arrays)
            )
            == base.canonical_json(
                _semantic(expected_program[slot], slot, canonical_arrays)
            )
        )
        for slot in SLOT_KEYS
    }
    program_lineage = bool(
        program is not None
        and sorted(program.get("required_evidence_ids", []))
        == sorted(expected_program["required_evidence_ids"])
    )
    ledger_exact: bool | None = None
    slot_lineage: bool | None = None
    if interface == "staged":
        ledger_exact = bool(
            draft
            and base.canonical_json(draft.get("evidence_ledger"))
            == base.canonical_json(_ledger(visible))
        )
        submitted = draft.get("semantic_slots", {}).get("slots", {}) if draft else {}
        expected_slots = oracle["semantic_slots"]["slots"]
        slot_lineage = bool(
            set(submitted) == set(SLOT_KEYS)
            and all(
                isinstance(submitted[slot], Mapping)
                and sorted(submitted[slot].get("supporting_evidence_ids", []))
                == sorted(expected_slots[slot]["supporting_evidence_ids"])
                for slot in SLOT_KEYS
            )
        )
    evidence_lineage = bool(
        program_lineage and (interface != "staged" or slot_lineage is True)
    )
    semantics = all(per_slot.values())
    return {
        "per_slot_exact": per_slot,
        "correct_slot_count": sum(per_slot.values()),
        "program_semantics_exact": semantics,
        "program_lineage_exact": program_lineage,
        "semantic_slot_lineage_exact": slot_lineage,
        "evidence_lineage_exact": evidence_lineage,
        "evidence_ledger_exact": ledger_exact,
        "all_slot_program_exact": bool(
            semantics
            and evidence_lineage
            and (interface != "staged" or ledger_exact is True)
        ),
    }


def _repair_ledger(
    draft: Mapping[str, Any] | None, visible: Mapping[str, Any]
) -> dict[str, Any] | None:
    if not isinstance(draft, Mapping):
        return None
    result = copy.deepcopy(dict(draft))
    result["evidence_ledger"] = _ledger(visible)
    return result


def _repair_projection(draft: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(draft, Mapping):
        return None
    result = copy.deepcopy(dict(draft))
    slots_container = result.get("semantic_slots")
    slots = slots_container.get("slots") if isinstance(slots_container, Mapping) else None
    if not isinstance(slots, Mapping) or set(slots) != set(SLOT_KEYS):
        return None
    if any(
        not isinstance(slots[slot], Mapping) or "value" not in slots[slot]
        for slot in SLOT_KEYS
    ):
        return None
    original = result.get("strategy_program")
    program = copy.deepcopy(dict(original)) if isinstance(original, Mapping) else {}
    for slot in SLOT_KEYS:
        program[slot] = copy.deepcopy(slots[slot]["value"])
    program["required_evidence_ids"] = sorted(
        {
            evidence_id
            for slot in SLOT_KEYS
            for evidence_id in slots[slot].get("supporting_evidence_ids", [])
        }
    )
    result["strategy_program"] = program
    return result


def _classify(
    observed: bool,
    source: str,
    o1: Mapping[str, Any],
    o2: Mapping[str, Any],
    o5: Mapping[str, Any],
) -> str:
    if observed:
        return "observed_exact"
    if source == "saved_response_unparseable":
        return "unparseable_or_truncated"
    if o1["all_slot_program_exact"]:
        return "saved_json_recovery"
    if o2["all_slot_program_exact"]:
        return "canonicalization_only"
    if o5["all_slot_program_exact"]:
        return "tool_owned_ledger_projection"
    if o5["program_semantics_exact"]:
        return "provenance_remaining"
    return "semantic_error_remaining"


def _expected_cell(cell: Mapping[str, Any], oracle_row: Mapping[str, Any]) -> dict[str, Any]:
    interface = "staged" if cell["arm_id"] in STAGED_ARMS else "flat"
    visible = _visible(cell)
    draft, source, parse_error = _draft(cell)
    ledger_candidate = _repair_ledger(draft, visible) if interface == "staged" else draft
    projection_candidate = _repair_projection(draft) if interface == "staged" else draft
    combined = _repair_projection(ledger_candidate) if interface == "staged" else draft
    o1 = _score(draft, interface, oracle_row["independent_oracle"], visible, False)
    o2 = _score(draft, interface, oracle_row["independent_oracle"], visible, True)
    ladder = {
        "O0_recorded": {
            "all_slot_program_exact": bool(cell["endpoints"]["all_slot_program_exact"]),
            "program_semantics_exact": bool(cell["endpoints"]["program_semantics_exact"]),
        },
        "O1_saved_json": o1,
        "O2_canonical_arrays": o2,
        "O3_tool_ledger": _score(
            ledger_candidate, interface, oracle_row["independent_oracle"], visible, True
        ),
        "O4_tool_projection": _score(
            projection_candidate, interface, oracle_row["independent_oracle"], visible, True
        ),
        "O5_tool_ledger_projection": _score(
            combined, interface, oracle_row["independent_oracle"], visible, True
        ),
    }
    o5 = ladder["O5_tool_ledger_projection"]
    return {
        "split": cell["split"],
        "arm_id": cell["arm_id"],
        "interface": interface,
        "condition_id": cell["condition_id"],
        "construct": cell["construct"],
        "saved_response_source": source,
        "saved_response_parse_error": parse_error,
        "finish_reason": (_response(cell) or {}).get("finish_reason"),
        "classification": _classify(
            bool(cell["endpoints"]["all_slot_program_exact"]), source, o1, o2, o5
        ),
        "remaining_wrong_slots": [
            slot for slot, exact in o5["per_slot_exact"].items() if not exact
        ],
        "ladder": ladder,
    }


def _group(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "cells": len(rows),
        "raw_json_available": sum(
            row["saved_response_source"] != "saved_response_unparseable"
            for row in rows
        ),
    }
    for stage in STAGES:
        result[stage] = {
            "all_slot_exact": sum(
                row["ladder"][stage]["all_slot_program_exact"] for row in rows
            ),
            "semantics_exact": sum(
                row["ladder"][stage]["program_semantics_exact"] for row in rows
            ),
        }
    return result


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_split_interface = []
    for split in ("development", "held_out"):
        for interface in ("flat", "staged"):
            selected = [
                row
                for row in rows
                if row["split"] == split and row["interface"] == interface
            ]
            by_split_interface.append(
                {"split": split, "interface": interface, **_group(selected)}
            )
    by_arm = []
    for arm in sorted(LLM_ARMS):
        for split in ("development", "held_out"):
            selected = [
                row for row in rows if row["arm_id"] == arm and row["split"] == split
            ]
            by_arm.append({"arm_id": arm, "split": split, **_group(selected)})
    wrong: Counter[str] = Counter()
    single: Counter[str] = Counter()
    for row in rows:
        slots = row["remaining_wrong_slots"]
        wrong.update(slots)
        if len(slots) == 1:
            single.update(slots)
    return {
        "by_split_interface": by_split_interface,
        "by_arm": by_arm,
        "recovery_classification": dict(
            sorted(Counter(row["classification"] for row in rows).items())
        ),
        "wrong_slot_frequency_after_o5": dict(
            sorted(wrong.items(), key=lambda item: (-item[1], item[0]))
        ),
        "single_wrong_slot_bottlenecks_after_o5": dict(
            sorted(single.items(), key=lambda item: (-item[1], item[0]))
        ),
    }


def audit(source_root: Path, replay_path: Path) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    source_root = source_root.resolve()
    replay = base.strict_json(replay_path.resolve(), "M29-T replay receipt")
    body = dict(replay)
    replay_id = body.pop("replay_id", None)
    if replay_id != base.content_id("m29treplay", body):
        issues.append("replay_content_address")
    if replay.get("plan_sha256") != base.sha256_file(PLAN_PATH):
        issues.append("plan_hash")
    if replay.get("source_contract_sha256") != base.sha256_file(source_root / "contract.json"):
        issues.append("source_contract_hash")
    if replay.get("source_primary_receipt_sha256") != base.sha256_file(
        source_root / "primary_receipt.json"
    ):
        issues.append("source_primary_hash")
    if source_audit.verify_addendum_receipt(source_root):
        issues.append("source_audit_addendum")
    for field, expected in (
        ("classification", "PRELIMINARY_ONLY"),
        ("new_model_calls", 0),
        ("new_embedding_calls", 0),
        ("maximum_cumulative_model_calls", 816),
        ("remaining_authorized_model_calls", 184),
        ("frozen_evidence_modified", False),
        ("m29b_authorized", False),
        ("final_evaluation_authorized", False),
    ):
        if replay.get(field) != expected:
            issues.append(f"boundary:{field}")

    contract = base.strict_json(source_root / "contract.json", "M29-S contract")
    commitment = base._artifact(contract, "split_commitment")
    packets = {
        split: base.strict_json(
            base._resolve_stored_path(commitment["packets"][split]["path"]), split
        )
        for split in ("development", "held_out")
    }
    oracle_rows = {
        (row["split"], row["condition_id"]): row
        for packet in packets.values()
        for row in packet["conditions"]
    }
    expected_rows = []
    for relative in sorted(contract["expected_cell_paths"]):
        cell = base.strict_json(source_root / relative, relative)
        if cell["arm_id"] not in LLM_ARMS:
            continue
        expected_rows.append(
            _expected_cell(cell, oracle_rows[(cell["split"], cell["condition_id"])])
        )
    if len(expected_rows) != 320:
        issues.append("source_llm_cell_count")
    if base.canonical_json(replay.get("cells")) != base.canonical_json(expected_rows):
        issues.append("cell_replay_mismatch")
    expected_summary = _summary(expected_rows)
    if base.canonical_json(replay.get("summary")) != base.canonical_json(expected_summary):
        issues.append("summary_mismatch")
    return list(dict.fromkeys(issues)), expected_summary


def build_audit(source_root: Path, replay_path: Path) -> dict[str, Any]:
    issues, summary = audit(source_root, replay_path)
    replay = base.strict_json(replay_path.resolve(), "M29-T replay receipt")
    body = {
        "schema_version": "grideval-g7-m29t-offline-replay-audit/v1",
        "classification": "PRELIMINARY_ONLY",
        "replay_id": replay.get("replay_id"),
        "replay_sha256": base.sha256_file(replay_path.resolve()),
        "auditor_source_sha256": base.sha256_file(Path(__file__).resolve()),
        "independent_imports_replay_implementation": False,
        "source_attempt_reverified": True,
        "saved_responses_reparsed": True,
        "ledger_repairs_recomputed": True,
        "projection_repairs_recomputed": True,
        "stage_scores_recomputed": True,
        "summary_recomputed": True,
        "cell_count": 320,
        "new_model_calls": 0,
        "scientific_summary": summary,
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "m29b_authorized": False,
        "final_evaluation_authorized": False,
    }
    return {"audit_id": base.content_id("m29taudit", body), **body}


def verify_audit(source_root: Path, replay_path: Path, audit_path: Path) -> list[str]:
    if not audit_path.is_file():
        return ["missing_independent_audit"]
    stored = base.strict_json(audit_path.resolve(), "M29-T independent audit")
    expected = build_audit(source_root, replay_path)
    return [] if base.canonical_json(stored) == base.canonical_json(expected) else [
        "independent_audit_mismatch"
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write:
        receipt = build_audit(args.source_root, args.replay)
        base.create_once_json(args.audit.resolve(), receipt)
        print(
            base.canonical_json(
                {
                    "audit_id": receipt["audit_id"],
                    "status": receipt["status"],
                    "issues": receipt["issues"],
                }
            )
        )
        raise SystemExit(0 if receipt["status"] == "passed" else 1)
    issues = verify_audit(args.source_root, args.replay, args.audit.resolve())
    print(base.canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()

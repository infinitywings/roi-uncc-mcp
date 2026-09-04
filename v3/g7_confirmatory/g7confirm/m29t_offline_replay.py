"""Zero-call representation-recovery replay over frozen M29-S Attempt 4 cells."""

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
CLASSIFICATION = "PRELIMINARY_ONLY"
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


class M29TReplayError(RuntimeError):
    """Raised when a replay source or saved response is malformed."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise M29TReplayError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_saved_json(text: str) -> dict[str, Any]:
    """Parse one complete saved JSON object without repairing its content."""

    value = json.loads(
        text,
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(
            M29TReplayError(f"non-finite JSON value: {token}")
        ),
    )
    if not isinstance(value, dict):
        raise M29TReplayError("saved response is not a JSON object")
    return value


def _response_for_final(cell: Mapping[str, Any]) -> Mapping[str, Any] | None:
    calls = int(cell.get("accounting", {}).get("model_calls", 0))
    value = cell.get("revision_response") if calls == 2 else cell.get("initial_response")
    return value if isinstance(value, Mapping) else None


def recover_final_draft(
    cell: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str, str | None]:
    """Return the accepted draft or parse the immutable saved final response."""

    accepted = cell.get("final_draft")
    if isinstance(accepted, Mapping):
        return copy.deepcopy(dict(accepted)), "accepted_final_draft", None
    response = _response_for_final(cell)
    if response is None:
        return None, "no_saved_final_response", "response_absent"
    content = response.get("content")
    if not isinstance(content, str):
        return None, "saved_response_unparseable", "content_absent"
    try:
        return parse_saved_json(content), "recovered_saved_json", None
    except Exception as exc:
        return None, "saved_response_unparseable", type(exc).__name__


def _visible_from_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    request = cell.get("initial_request")
    if not isinstance(request, Mapping):
        raise M29TReplayError("LLM cell has no initial request")
    messages = request.get("messages", [])
    if len(messages) < 2 or messages[1].get("role") != "user":
        raise M29TReplayError("LLM cell initial request is malformed")
    visible = json.loads(messages[1]["content"])
    if not isinstance(visible, dict):
        raise M29TReplayError("visible input is not an object")
    return visible


def expected_ledger(visible: Mapping[str, Any]) -> dict[str, Any]:
    """Build the Attempt 4 ledger from visible status and active authority only."""

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


def _program(draft: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(draft, Mapping):
        return None
    value = draft.get("strategy_program")
    return value if isinstance(value, Mapping) else None


def _semantic(value: Any, slot: str, canonical_arrays: bool) -> Any:
    if canonical_arrays and slot in UNORDERED_SLOTS and isinstance(value, list):
        return sorted(value)
    return value


def score_draft(
    draft: Mapping[str, Any] | None,
    *,
    interface: str,
    oracle: Mapping[str, Any],
    visible: Mapping[str, Any],
    canonical_arrays: bool,
) -> dict[str, Any]:
    """Score values without performing any semantic repair."""

    program = _program(draft)
    oracle_program = oracle["strategy_program"]
    per_slot = {
        slot: bool(
            program is not None
            and base.canonical_json(
                _semantic(program.get(slot), slot, canonical_arrays)
            )
            == base.canonical_json(
                _semantic(oracle_program[slot], slot, canonical_arrays)
            )
        )
        for slot in SLOT_KEYS
    }
    program_lineage_exact = bool(
        program is not None
        and sorted(program.get("required_evidence_ids", []))
        == sorted(oracle_program["required_evidence_ids"])
    )
    ledger_exact: bool | None = None
    slot_lineage_exact: bool | None = None
    if interface == "staged":
        ledger_exact = bool(
            draft
            and base.canonical_json(draft.get("evidence_ledger"))
            == base.canonical_json(expected_ledger(visible))
        )
        submitted = draft.get("semantic_slots", {}).get("slots", {}) if draft else {}
        oracle_slots = oracle["semantic_slots"]["slots"]
        slot_lineage_exact = bool(
            set(submitted) == set(SLOT_KEYS)
            and all(
                isinstance(submitted[slot], Mapping)
                and sorted(submitted[slot].get("supporting_evidence_ids", []))
                == sorted(oracle_slots[slot]["supporting_evidence_ids"])
                for slot in SLOT_KEYS
            )
        )
    evidence_lineage_exact = bool(
        program_lineage_exact
        and (interface != "staged" or slot_lineage_exact is True)
    )
    program_semantics_exact = all(per_slot.values())
    return {
        "per_slot_exact": per_slot,
        "correct_slot_count": sum(per_slot.values()),
        "program_semantics_exact": program_semantics_exact,
        "program_lineage_exact": program_lineage_exact,
        "semantic_slot_lineage_exact": slot_lineage_exact,
        "evidence_lineage_exact": evidence_lineage_exact,
        "evidence_ledger_exact": ledger_exact,
        "all_slot_program_exact": bool(
            program_semantics_exact
            and evidence_lineage_exact
            and (interface != "staged" or ledger_exact is True)
        ),
    }


def repair_ledger(
    draft: Mapping[str, Any] | None, visible: Mapping[str, Any]
) -> dict[str, Any] | None:
    if not isinstance(draft, Mapping):
        return None
    result = copy.deepcopy(dict(draft))
    result["evidence_ledger"] = expected_ledger(visible)
    return result


def repair_projection(draft: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Project submitted slots; never substitute an oracle semantic value."""

    if not isinstance(draft, Mapping):
        return None
    result = copy.deepcopy(dict(draft))
    semantic_slots = result.get("semantic_slots")
    if not isinstance(semantic_slots, Mapping):
        return None
    slots = semantic_slots.get("slots")
    if not isinstance(slots, Mapping) or set(slots) != set(SLOT_KEYS):
        return None
    if any(
        not isinstance(slots[slot], Mapping) or "value" not in slots[slot]
        for slot in SLOT_KEYS
    ):
        return None
    old_program = result.get("strategy_program")
    program = copy.deepcopy(dict(old_program)) if isinstance(old_program, Mapping) else {}
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


def _cell_classification(
    observed: bool,
    raw_source: str,
    raw_frozen: Mapping[str, Any],
    raw_canonical: Mapping[str, Any],
    repaired: Mapping[str, Any] | None,
) -> str:
    if observed:
        return "observed_exact"
    if raw_source == "saved_response_unparseable":
        return "unparseable_or_truncated"
    if raw_frozen["all_slot_program_exact"]:
        return "saved_json_recovery"
    if raw_canonical["all_slot_program_exact"]:
        return "canonicalization_only"
    if repaired and repaired["all_slot_program_exact"]:
        return "tool_owned_ledger_projection"
    if repaired and repaired["program_semantics_exact"]:
        return "provenance_remaining"
    return "semantic_error_remaining"


def replay_cell(
    cell: Mapping[str, Any], row: Mapping[str, Any]
) -> dict[str, Any]:
    arm = str(cell["arm_id"])
    if arm not in LLM_ARMS:
        raise M29TReplayError(f"replay_cell requires an LLM arm, got {arm}")
    interface = "staged" if arm in STAGED_ARMS else "flat"
    visible = _visible_from_cell(cell)
    draft, source, parse_error = recover_final_draft(cell)
    raw_frozen = score_draft(
        draft,
        interface=interface,
        oracle=row["independent_oracle"],
        visible=visible,
        canonical_arrays=False,
    )
    raw_canonical = score_draft(
        draft,
        interface=interface,
        oracle=row["independent_oracle"],
        visible=visible,
        canonical_arrays=True,
    )
    ledger_candidate = repair_ledger(draft, visible) if interface == "staged" else draft
    projection_candidate = repair_projection(draft) if interface == "staged" else draft
    combined_candidate = (
        repair_projection(ledger_candidate) if interface == "staged" else draft
    )
    ladder = {
        "O0_recorded": {
            "all_slot_program_exact": bool(
                cell["endpoints"]["all_slot_program_exact"]
            ),
            "program_semantics_exact": bool(
                cell["endpoints"]["program_semantics_exact"]
            ),
        },
        "O1_saved_json": raw_frozen,
        "O2_canonical_arrays": raw_canonical,
        "O3_tool_ledger": score_draft(
            ledger_candidate,
            interface=interface,
            oracle=row["independent_oracle"],
            visible=visible,
            canonical_arrays=True,
        ),
        "O4_tool_projection": score_draft(
            projection_candidate,
            interface=interface,
            oracle=row["independent_oracle"],
            visible=visible,
            canonical_arrays=True,
        ),
        "O5_tool_ledger_projection": score_draft(
            combined_candidate,
            interface=interface,
            oracle=row["independent_oracle"],
            visible=visible,
            canonical_arrays=True,
        ),
    }
    strongest = ladder["O5_tool_ledger_projection"]
    wrong_slots = [
        slot for slot, exact in strongest["per_slot_exact"].items() if not exact
    ]
    return {
        "split": cell["split"],
        "arm_id": arm,
        "interface": interface,
        "condition_id": cell["condition_id"],
        "construct": cell["construct"],
        "saved_response_source": source,
        "saved_response_parse_error": parse_error,
        "finish_reason": (
            _response_for_final(cell) or {}
        ).get("finish_reason"),
        "classification": _cell_classification(
            bool(cell["endpoints"]["all_slot_program_exact"]),
            source,
            raw_frozen,
            raw_canonical,
            strongest,
        ),
        "remaining_wrong_slots": wrong_slots,
        "ladder": ladder,
    }


def _summarize_group(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "cells": len(rows),
        "raw_json_available": sum(
            row["saved_response_source"] != "saved_response_unparseable"
            for row in rows
        ),
    }
    for stage in (
        "O0_recorded",
        "O1_saved_json",
        "O2_canonical_arrays",
        "O3_tool_ledger",
        "O4_tool_projection",
        "O5_tool_ledger_projection",
    ):
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
                {"split": split, "interface": interface, **_summarize_group(selected)}
            )
    by_arm = []
    for arm in sorted(LLM_ARMS):
        for split in ("development", "held_out"):
            selected = [
                row for row in rows if row["arm_id"] == arm and row["split"] == split
            ]
            by_arm.append({"arm_id": arm, "split": split, **_summarize_group(selected)})
    wrong_slot_frequency: Counter[str] = Counter()
    single_slot_bottlenecks: Counter[str] = Counter()
    for row in rows:
        wrong = row["remaining_wrong_slots"]
        wrong_slot_frequency.update(wrong)
        if len(wrong) == 1:
            single_slot_bottlenecks.update(wrong)
    return {
        "by_split_interface": by_split_interface,
        "by_arm": by_arm,
        "recovery_classification": dict(
            sorted(Counter(row["classification"] for row in rows).items())
        ),
        "wrong_slot_frequency_after_o5": dict(
            sorted(wrong_slot_frequency.items(), key=lambda item: (-item[1], item[0]))
        ),
        "single_wrong_slot_bottlenecks_after_o5": dict(
            sorted(single_slot_bottlenecks.items(), key=lambda item: (-item[1], item[0]))
        ),
    }


def build_replay(source_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    audit_issues = source_audit.verify_addendum_receipt(source_root)
    if audit_issues:
        raise M29TReplayError(f"source audit addendum is not clean: {audit_issues}")
    contract = base.strict_json(source_root / "contract.json", "M29-S Attempt 4 contract")
    commitment = base._artifact(contract, "split_commitment")
    packet_by_split = {
        split: base.strict_json(
            base._resolve_stored_path(commitment["packets"][split]["path"]),
            f"M29-S {split} packet",
        )
        for split in ("development", "held_out")
    }
    oracle_rows = {
        (row["split"], row["condition_id"]): row
        for packet in packet_by_split.values()
        for row in packet["conditions"]
    }
    rows: list[dict[str, Any]] = []
    for relative in sorted(contract["expected_cell_paths"]):
        cell = base.strict_json(source_root / relative, relative)
        if cell["arm_id"] not in LLM_ARMS:
            continue
        rows.append(
            replay_cell(cell, oracle_rows[(cell["split"], cell["condition_id"])])
        )
    if len(rows) != 320:
        raise M29TReplayError(f"expected 320 LLM cells, found {len(rows)}")
    body = {
        "schema_version": "grideval-g7-m29t-offline-replay/v1",
        "classification": CLASSIFICATION,
        "plan_sha256": base.sha256_file(PLAN_PATH),
        "source_execution_contract_id": contract["execution_contract_id"],
        "source_contract_sha256": base.sha256_file(source_root / "contract.json"),
        "source_primary_receipt_sha256": base.sha256_file(
            source_root / "primary_receipt.json"
        ),
        "source_audit_addendum_id": base.strict_json(
            source_root / "independent_audit_addendum.json",
            "M29-S Attempt 4 audit addendum",
        )["audit_addendum_id"],
        "replay_source_sha256": base.sha256_file(Path(__file__).resolve()),
        "source_cell_count": 384,
        "replayed_llm_cell_count": len(rows),
        "new_model_calls": 0,
        "new_embedding_calls": 0,
        "maximum_cumulative_model_calls": 816,
        "remaining_authorized_model_calls": 184,
        "frozen_evidence_modified": False,
        "m29b_authorized": False,
        "final_evaluation_authorized": False,
        "summary": _summary(rows),
        "cells": rows,
    }
    return {"replay_id": base.content_id("m29treplay", body), **body}


def verify_replay(source_root: Path, output: Path) -> list[str]:
    if not output.is_file():
        return ["missing_replay_receipt"]
    stored = base.strict_json(output, "M29-T offline replay receipt")
    rebuilt = build_replay(source_root)
    return [] if base.canonical_json(stored) == base.canonical_json(rebuilt) else [
        "replay_receipt_mismatch"
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write:
        receipt = build_replay(args.source_root)
        base.create_once_json(args.output.resolve(), receipt)
        print(
            base.canonical_json(
                {
                    "replay_id": receipt["replay_id"],
                    "new_model_calls": receipt["new_model_calls"],
                    "classification": receipt["summary"]["recovery_classification"],
                }
            )
        )
        return
    issues = verify_replay(args.source_root, args.output.resolve())
    print(base.canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()

"""Visible-ledger and staged-validator correction for M29-S Attempt 3."""

from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import m29s_campaign as base
from . import m29s_campaign_v2 as v2
from . import m29s_semantic_compiler as design


ROOT = base.ROOT
AMENDMENT_PATH = ROOT / "m29s_attempt3_interface_contract_plan.json"
PREDECESSOR_ROOT = ROOT / "artifacts/m29s_factorial_attempt2"
MAX_COMPLETION_TOKENS = 1800
PRIOR_MODEL_CALLS = 222
CONTRACTED_MODEL_CALLS = 576
MAXIMUM_CUMULATIVE_CALLS = 798
AUTHORIZED_CUMULATIVE_CALLS = 1000
TRANSPORT_WORKERS = 4
DECISION_ID = "dec_01M1PRTXJHJYCT29SFZZKXP4ZC"
PLAN_GATE_ID = "chk_01M1PS6F5VEKHWH866GXHC3BB0"
ADDITIONAL_DIAGNOSTIC_SLOTS = {"evidence_ledger", "semantic_slots"}

BOUND_SOURCE_PATHS = v2.BOUND_SOURCE_PATHS + (
    "m29s_attempt3_interface_contract_plan.json",
    "g7confirm/m29s_campaign_v3.py",
    "g7confirm/m29s_independent_audit_v3.py",
    "tests/test_m29s_campaign_v3.py",
)

_BASE_VALIDATE_CONTRACT = base.validate_execution_contract
_BASE_BUILD_LEDGER = design.build_oracle_ledger
_BASE_VALIDATE_LEDGER = design.validate_evidence_ledger
_BASE_VALIDATE_DIAGNOSTICS = design.validate_diagnostics
_BASE_VALIDATE_DRAFT = design.validate_strategy_draft


class M29SV3Error(RuntimeError):
    """Raised when the Attempt 3 interface amendment is violated."""


def active_authority_order(bundle: Mapping[str, Any]) -> list[str]:
    active = {
        row["authority"] for row in bundle["records"] if row["status"] == "active"
    }
    return [value for value in design.AUTHORITY_ORDER if value in active]


def build_oracle_ledger(
    bundle: Mapping[str, Any], passages: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    ledger = _BASE_BUILD_LEDGER(bundle, passages)
    ledger["authority_order"] = active_authority_order(bundle)
    return ledger


def validate_evidence_ledger(
    ledger: Mapping[str, Any],
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> None:
    expected = active_authority_order(bundle)
    if ledger.get("authority_order") != expected:
        raise design.M29SContractError("EvidenceLedger active authority order drift")
    shadow = copy.deepcopy(dict(ledger))
    shadow["authority_order"] = list(design.AUTHORITY_ORDER)
    _BASE_VALIDATE_LEDGER(shadow, bundle, passages)


def validate_diagnostics(payload: Mapping[str, Any]) -> None:
    shadow = copy.deepcopy(dict(payload))
    rows = shadow.get("diagnostics", [])
    for row in rows:
        if row.get("slot") in ADDITIONAL_DIAGNOSTIC_SLOTS:
            row["slot"] = "strategy_program"
    _BASE_VALIDATE_DIAGNOSTICS(shadow)


def _diagnostic_code(slot: str) -> str:
    return {
        "strategy_id": "authority_conflict",
        "effect_direction": "authority_conflict",
        "allowed_targets": "topology_inconsistent",
        "forbidden_windows": "expired_record",
        "objective_weights": "weights_inconsistent",
        "max_total_energy": "budget_inconsistent",
        "max_total_visibility": "budget_inconsistent",
        "min_actions": "budget_inconsistent",
        "max_actions": "budget_inconsistent",
        "max_level_delta": "cooldown_inconsistent",
        "cooldown_same_target": "cooldown_inconsistent",
    }[slot]


def validate_strategy_draft(
    condition: design.LatentCondition,
    draft: Mapping[str, Any],
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Add answer-free diagnostics for every staged interface artifact."""

    baseline = _BASE_VALIDATE_DRAFT(condition, draft, bundle, passages)
    findings = list(baseline["diagnostics"])
    is_staged = any(
        key in draft for key in ("evidence_ledger", "semantic_slots")
    )
    if is_staged:
        ledger = draft.get("evidence_ledger")
        if not isinstance(ledger, Mapping):
            findings.append({"code": "schema", "slot": "evidence_ledger"})
        else:
            try:
                validate_evidence_ledger(ledger, bundle, passages)
            except design.M29SContractError as exc:
                code = (
                    "authority_conflict"
                    if "authority order" in str(exc)
                    else "schema"
                )
                findings.append({"code": code, "slot": "evidence_ledger"})
        slots = draft.get("semantic_slots")
        if not isinstance(slots, Mapping):
            findings.append({"code": "schema", "slot": "semantic_slots"})
        else:
            try:
                design.validate_semantic_slots(slots, bundle, passages)
            except design.M29SContractError:
                findings.append({"code": "schema", "slot": "semantic_slots"})
            expected = design.strong_deterministic_compile(
                condition, bundle, passages
            )
            submitted = slots.get("slots", {})
            if expected is not None and isinstance(submitted, Mapping):
                expected_program = expected["strategy_program"]
                for slot in design.SLOT_KEYS:
                    value = submitted.get(slot, {}).get("value")
                    if design.canonical_json(value) != design.canonical_json(
                        expected_program[slot]
                    ):
                        findings.append(
                            {"code": _diagnostic_code(slot), "slot": slot}
                        )
        program = draft.get("strategy_program")
        if isinstance(slots, Mapping) and isinstance(program, Mapping):
            try:
                projected = design.project_slots_to_program(
                    slots, compiler_id=program.get("compiler_id", "")
                )
                if design.canonical_json(projected) != design.canonical_json(program):
                    findings.append({"code": "schema", "slot": "semantic_slots"})
            except Exception:
                findings.append({"code": "schema", "slot": "semantic_slots"})
    unique = sorted(
        {(row["code"], row["slot"]) for row in findings},
        key=lambda value: (value[1], value[0]),
    )
    result = {
        **baseline,
        "diagnostics": [
            {"code": code, "slot": slot} for code, slot in unique
        ],
    }
    validate_diagnostics(result)
    return result


@contextmanager
def _source_profile() -> Iterator[None]:
    previous = base.BOUND_SOURCE_PATHS
    base.BOUND_SOURCE_PATHS = BOUND_SOURCE_PATHS
    try:
        yield
    finally:
        base.BOUND_SOURCE_PATHS = previous


@contextmanager
def _execution_profile() -> Iterator[None]:
    previous = {
        "builder": base.build_initial_request,
        "validator": base.validate_execution_contract,
        "sources": base.BOUND_SOURCE_PATHS,
        "build_ledger": design.build_oracle_ledger,
        "validate_ledger": design.validate_evidence_ledger,
        "validate_diagnostics": design.validate_diagnostics,
        "validate_draft": design.validate_strategy_draft,
    }
    base.build_initial_request = v2.build_initial_request
    base.validate_execution_contract = validate_execution_contract
    base.BOUND_SOURCE_PATHS = BOUND_SOURCE_PATHS
    design.build_oracle_ledger = build_oracle_ledger
    design.validate_evidence_ledger = validate_evidence_ledger
    design.validate_diagnostics = validate_diagnostics
    design.validate_strategy_draft = validate_strategy_draft
    try:
        yield
    finally:
        base.build_initial_request = previous["builder"]
        base.validate_execution_contract = previous["validator"]
        base.BOUND_SOURCE_PATHS = previous["sources"]
        design.build_oracle_ledger = previous["build_ledger"]
        design.validate_evidence_ledger = previous["validate_ledger"]
        design.validate_diagnostics = previous["validate_diagnostics"]
        design.validate_strategy_draft = previous["validate_draft"]


def build_predecessor_receipt(root: Path = PREDECESSOR_ROOT) -> dict[str, Any]:
    contract_path = root / "contract.json"
    contract = base.strict_json(contract_path, "M29-S Attempt 2 contract")
    attempt2_issues = v2.validate_execution_contract(contract)
    cells = sorted(root.glob("cells/development/*/*.json"))
    rows = [base.strict_json(path, path.as_posix()) for path in cells]
    recorded_calls = sum(int(row["accounting"]["model_calls"]) for row in rows)
    staged = [
        row
        for row in rows
        if row["arm_id"] in design.FACTORIAL_ARMS
        and design.arm_spec(row["arm_id"])["interface"] == "staged"
    ]
    hidden_order = sum(
        "EvidenceLedger authority order drift" in str(row.get("failure_class") or "")
        for row in staged
    )
    length_failures = sum(
        "finish reason: length" in str(row.get("failure_class") or "")
        for row in staged
    )
    held_out_cells = list(root.glob("cells/held_out/*/*.json"))
    body = {
        "schema_version": "grideval-g7-m29s-predecessor-stop/v2",
        "classification": design.CLASSIFICATION,
        "execution_contract_id": contract["execution_contract_id"],
        "execution_contract_sha256": base.sha256_file(contract_path),
        "status": "terminated_development_interface_diagnostic",
        "reason": "hidden ledger target and missing staged-validator coverage",
        "development_cell_count": len(rows),
        "development_cell_hashes": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": base.sha256_file(path),
            }
            for path in cells
        ],
        "recorded_model_calls": recorded_calls,
        "maximum_unpersisted_concurrent_calls": 6,
        "conservative_model_calls": recorded_calls + 6,
        "completed_staged_cells": len(staged),
        "staged_cells_with_length_failure": length_failures,
        "staged_cells_with_hidden_authority_failure": hidden_order,
        "held_out_cell_count": len(held_out_cells),
        "development_receipt_created": (root / "development_receipt.json").exists(),
        "development_freeze_created": (root / "development_freeze.json").exists(),
        "source_contract_issues": attempt2_issues,
        "access_boundary": {
            "held_out_accessed_by_runner": False,
            "docker_accessed": False,
            "simulator_accessed": False,
            "detector_accessed": False,
            "defense_accessed": False,
            "physical_actuator_accessed": False,
            "final_evaluation_accessed": False,
        },
        "m29b_authorized": False,
    }
    receipt = {"predecessor_receipt_id": base.content_id("m29spred", body), **body}
    expected = {
        "development_cell_count": 20,
        "recorded_model_calls": 30,
        "conservative_model_calls": 36,
        "completed_staged_cells": 5,
        "staged_cells_with_length_failure": 0,
        "staged_cells_with_hidden_authority_failure": 5,
        "held_out_cell_count": 0,
        "source_contract_issues": [],
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise M29SV3Error(f"Attempt 2 predecessor evidence drift: {key}")
    return receipt


def _artifact_reference(path: Path, id_field: str) -> dict[str, Any]:
    payload = base.strict_json(path, path.name)
    return {
        "path": base._stored_path(path),
        "sha256": base.sha256_file(path),
        "id": payload[id_field],
    }


def build_execution_contract(
    *, predecessor_receipt_path: Path, **kwargs: Any
) -> dict[str, Any]:
    amendment = base.strict_json(AMENDMENT_PATH, "M29-S Attempt 3 amendment")
    predecessor = base.strict_json(
        predecessor_receipt_path, "M29-S Attempt 2 stop receipt"
    )
    predecessor_body = dict(predecessor)
    predecessor_id = predecessor_body.pop("predecessor_receipt_id", None)
    if predecessor_id != base.content_id("m29spred", predecessor_body):
        raise M29SV3Error("predecessor receipt content address drift")
    if predecessor.get("conservative_model_calls") != 36:
        raise M29SV3Error("Attempt 2 predecessor accounting drift")
    with _source_profile():
        contract = base.build_execution_contract(**kwargs)
    body = dict(contract)
    body.pop("execution_contract_id")
    body["schema_version"] = "grideval-g7-m29s-execution-contract/v3"
    body["decision_id"] = DECISION_ID
    body["plan_gate_id"] = PLAN_GATE_ID
    body["interface_contract_amendment"] = {
        "path": AMENDMENT_PATH.relative_to(ROOT).as_posix(),
        "sha256": base.sha256_file(AMENDMENT_PATH),
        "schema_version": amendment["schema_version"],
    }
    body["predecessor_attempt"] = _artifact_reference(
        predecessor_receipt_path, "predecessor_receipt_id"
    )
    model_contract = copy.deepcopy(body["model_contract"])
    model_contract["maximum_completion_tokens_per_call"] = MAX_COMPLETION_TOKENS
    model_contract["prior_cumulative_calls"] = PRIOR_MODEL_CALLS
    model_contract["maximum_cumulative_calls"] = MAXIMUM_CUMULATIVE_CALLS
    body["model_contract"] = model_contract
    tool_contract = copy.deepcopy(
        base.strict_json(design.PLAN_PATH, "M29-S factorial plan")["tool_contract"]
    )
    tool_contract["validator_result_slots"] = sorted(
        set(tool_contract.get("validator_result_slots", []))
        | set(design.SLOT_KEYS)
        | {"strategy_program", "required_evidence_ids"}
        | ADDITIONAL_DIAGNOSTIC_SLOTS
    )
    body["tool_contract"] = tool_contract
    body["ledger_authority_contract"] = {
        "source": "active visible records only",
        "ordering": list(design.AUTHORITY_ORDER),
        "include_absent_authorities": False,
    }
    body["authorization_budget"] = {
        "pi_authorization_note_id": kwargs["authorization_note_id"],
        "pre_m29s_model_calls": 101,
        "attempt1_conservative_calls": 85,
        "attempt2_conservative_calls": 36,
        "prior_model_calls": PRIOR_MODEL_CALLS,
        "contracted_new_model_calls": CONTRACTED_MODEL_CALLS,
        "maximum_cumulative_model_calls": MAXIMUM_CUMULATIVE_CALLS,
        "pi_authorized_cumulative_ceiling": AUTHORIZED_CUMULATIVE_CALLS,
        "remaining_after_attempt": 202,
    }
    body["transport_profile"] = {
        "workers": TRANSPORT_WORKERS,
        "bounded_concurrency": True,
        "request_payloads_changed": False,
        "retry_count": 0,
        "schedule_bound_in_contract": True,
    }
    return {"execution_contract_id": base.content_id("m29sexec", body), **body}


def validate_execution_contract(contract: Mapping[str, Any]) -> list[str]:
    with _source_profile():
        issues = _BASE_VALIDATE_CONTRACT(contract)
    v1_only = {
        "execution_contract_plan_gate",
        "execution_contract_cumulative_calls",
        "execution_contract_authorization_arithmetic",
    }
    issues = [value for value in issues if value not in v1_only]
    if contract.get("schema_version") != "grideval-g7-m29s-execution-contract/v3":
        issues.append("execution_contract_schema_version")
    if contract.get("decision_id") != DECISION_ID:
        issues.append("execution_contract_decision")
    if contract.get("plan_gate_id") != PLAN_GATE_ID:
        issues.append("execution_contract_plan_gate_v3")
    if contract.get("model_contract", {}).get(
        "maximum_completion_tokens_per_call"
    ) != MAX_COMPLETION_TOKENS:
        issues.append("execution_contract_completion_cap")
    budget = contract.get("authorization_budget", {})
    expected_budget = {
        "pre_m29s_model_calls": 101,
        "attempt1_conservative_calls": 85,
        "attempt2_conservative_calls": 36,
        "prior_model_calls": 222,
        "contracted_new_model_calls": 576,
        "maximum_cumulative_model_calls": 798,
        "pi_authorized_cumulative_ceiling": 1000,
        "remaining_after_attempt": 202,
    }
    for key, value in expected_budget.items():
        if budget.get(key) != value:
            issues.append(f"execution_contract_budget:{key}")
    if contract.get("ledger_authority_contract") != {
        "source": "active visible records only",
        "ordering": list(design.AUTHORITY_ORDER),
        "include_absent_authorities": False,
    }:
        issues.append("execution_contract_ledger_authority")
    slots = set(
        contract.get("tool_contract", {}).get("validator_result_slots", [])
    )
    if not ADDITIONAL_DIAGNOSTIC_SLOTS.issubset(slots):
        issues.append("execution_contract_staged_validator_coverage")
    if contract.get("transport_profile", {}).get("workers") != 4:
        issues.append("execution_contract_transport")
    amendment = contract.get("interface_contract_amendment", {})
    if amendment.get("sha256") != base.sha256_file(AMENDMENT_PATH):
        issues.append("execution_contract_amendment_hash")
    predecessor_ref = contract.get("predecessor_attempt", {})
    try:
        path = base._resolve_stored_path(predecessor_ref["path"])
        predecessor = base.strict_json(path, "Attempt 2 predecessor receipt")
        if predecessor_ref.get("sha256") != base.sha256_file(path):
            issues.append("execution_contract_predecessor_hash")
        if predecessor_ref.get("id") != predecessor.get("predecessor_receipt_id"):
            issues.append("execution_contract_predecessor_id")
        if predecessor.get("conservative_model_calls") != 36:
            issues.append("execution_contract_predecessor_calls")
    except Exception as exc:
        issues.append(f"execution_contract_predecessor:{type(exc).__name__}")
    return list(dict.fromkeys(issues))


def register_attempt(
    root: Path, *, predecessor_receipt_path: Path, **kwargs: Any
) -> dict[str, Any]:
    contract = build_execution_contract(
        predecessor_receipt_path=predecessor_receipt_path, **kwargs
    )
    issues = validate_execution_contract(contract)
    if issues:
        raise M29SV3Error(f"Attempt 3 contract invalid: {issues}")
    base.create_once_json(root / "contract.json", contract)
    return contract


def _run_cell(
    *, arm_id: str, row: Mapping[str, Any], packet: Mapping[str, Any],
    embedding: Mapping[str, Any], execution_contract_id: str,
) -> dict[str, Any]:
    if arm_id in design.CONTROL_ARMS:
        return base.run_control_cell(
            arm_id=arm_id, row=row, packet=packet, embedding=embedding,
            execution_contract_id=execution_contract_id,
        )
    return base.run_live_cell(
        arm_id=arm_id, row=row, packet=packet, embedding=embedding,
        execution_contract_id=execution_contract_id,
    )


def execute_split(root: Path, split: str) -> dict[str, Any]:
    if split not in design.SPLITS:
        raise M29SV3Error(f"unknown split: {split}")
    with _execution_profile():
        contract = base.strict_json(root / "contract.json", "M29-S Attempt 3 contract")
        issues = validate_execution_contract(contract)
        if issues:
            raise M29SV3Error(f"Attempt 3 contract failed verification: {issues}")
        if split == "held_out":
            freeze_path = root / "development_freeze.json"
            if not freeze_path.is_file():
                raise M29SV3Error("held-out execution requires development freeze")
            freeze = base.strict_json(freeze_path, "M29-S development freeze")
            freeze_issues = base.verify_development_freeze(root, freeze)
            if freeze_issues:
                raise M29SV3Error(
                    f"development freeze failed verification: {freeze_issues}"
                )
        commitment = base._load_contract_artifact(contract, "split_commitment")
        packet_ref = commitment["packets"][split]
        packet_path = base._resolve_stored_path(packet_ref["path"])
        if base.sha256_file(packet_path) != packet_ref["sha256"]:
            raise M29SV3Error(f"{split} packet drift")
        packet = base.strict_json(packet_path, f"M29-S {split} packet")
        embedding = base._load_contract_artifact(
            contract, "embedding_receipts", split
        )
        schedule = contract["execution_schedule"][split]
        existing = [
            root / value
            for value in base.expected_cell_paths(split)
            if (root / value).exists()
        ]
        if existing:
            raise FileExistsError(
                f"Attempt 3 split already contains {len(existing)} create-once cells"
            )
        for schedule_row in schedule:
            row = base._packet_condition(packet, schedule_row["condition_id"])
            arms = schedule_row["arm_order"]
            for offset in range(0, len(arms), TRANSPORT_WORKERS):
                wave = arms[offset:offset + TRANSPORT_WORKERS]
                with ThreadPoolExecutor(max_workers=TRANSPORT_WORKERS) as pool:
                    futures = {
                        arm: pool.submit(
                            _run_cell,
                            arm_id=arm,
                            row=row,
                            packet=packet,
                            embedding=embedding,
                            execution_contract_id=contract["execution_contract_id"],
                        )
                        for arm in wave
                    }
                    completed = {arm: futures[arm].result() for arm in wave}
                for arm in wave:
                    cell = completed[arm]
                    output = root / "cells" / split / arm / f"{row['condition_id']}.json"
                    base.create_once_json(output, cell)
                    print(base.canonical_json({
                        "split": split,
                        "arm_id": arm,
                        "condition_id": row["condition_id"],
                        "status": cell["status"],
                        "success": cell["endpoints"]["all_slot_program_exact"],
                        "model_calls": cell["accounting"]["model_calls"],
                    }), flush=True)
        receipt = base.build_split_receipt(root, split)
        base.create_once_json(root / f"{split}_receipt.json", receipt)
        return receipt


def build_development_freeze(root: Path) -> dict[str, Any]:
    with _execution_profile():
        return base.build_development_freeze(root)


def build_primary_receipt(
    root: Path, *, independent_clean: bool = False
) -> dict[str, Any]:
    with _execution_profile():
        return base.build_primary_receipt(root, independent_clean=independent_clean)


def verify_primary_receipt(root: Path) -> list[str]:
    with _execution_profile():
        return base.verify_primary_receipt(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    close = commands.add_parser("close-predecessor")
    close.add_argument("--root", type=Path, default=PREDECESSOR_ROOT)
    close.add_argument("--output", type=Path, required=True)
    register = commands.add_parser("register")
    register.add_argument("--root", type=Path, required=True)
    register.add_argument("--predecessor-receipt", type=Path, required=True)
    register.add_argument("--design-contract", type=Path, required=True)
    register.add_argument("--plan-audit", type=Path, required=True)
    register.add_argument("--split-commitment", type=Path, required=True)
    register.add_argument("--preflight", type=Path, required=True)
    register.add_argument("--development-embedding", type=Path, required=True)
    register.add_argument("--held-out-embedding", type=Path, required=True)
    register.add_argument("--authorization-note-id", required=True)
    execute = commands.add_parser("execute-split")
    execute.add_argument("--root", type=Path, required=True)
    execute.add_argument("--split", choices=design.SPLITS, required=True)
    freeze = commands.add_parser("freeze-development")
    freeze.add_argument("--root", type=Path, required=True)
    primary = commands.add_parser("primary")
    primary.add_argument("--root", type=Path, required=True)
    primary.add_argument("--independent-clean", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "close-predecessor":
        receipt = build_predecessor_receipt(args.root.resolve())
        base.create_once_json(args.output.resolve(), receipt)
        print(base.canonical_json({
            "predecessor_receipt_id": receipt["predecessor_receipt_id"],
            "conservative_model_calls": receipt["conservative_model_calls"],
        }))
    elif args.command == "register":
        contract = register_attempt(
            args.root.resolve(),
            predecessor_receipt_path=args.predecessor_receipt.resolve(),
            design_contract_path=args.design_contract.resolve(),
            plan_audit_path=args.plan_audit.resolve(),
            split_commitment_path=args.split_commitment.resolve(),
            preflight_path=args.preflight.resolve(),
            development_embedding_path=args.development_embedding.resolve(),
            held_out_embedding_path=args.held_out_embedding.resolve(),
            authorization_note_id=args.authorization_note_id,
        )
        print(base.canonical_json({"execution_contract_id": contract["execution_contract_id"]}))
    elif args.command == "execute-split":
        receipt = execute_split(args.root.resolve(), args.split)
        print(base.canonical_json({
            "split_receipt_id": receipt["split_receipt_id"],
            "model_calls": receipt["model_calls"],
        }))
    elif args.command == "freeze-development":
        receipt = build_development_freeze(args.root.resolve())
        base.create_once_json(args.root.resolve() / "development_freeze.json", receipt)
        print(base.canonical_json({"development_freeze_id": receipt["development_freeze_id"]}))
    elif args.command == "primary":
        receipt = build_primary_receipt(
            args.root.resolve(), independent_clean=args.independent_clean
        )
        base.create_once_json(args.root.resolve() / "primary_receipt.json", receipt)
        print(base.canonical_json({
            "primary_receipt_id": receipt["primary_receipt_id"],
            "status": receipt["status"],
        }))
    else:
        issues = verify_primary_receipt(args.root.resolve())
        print(base.canonical_json({"issues": issues}))
        raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()

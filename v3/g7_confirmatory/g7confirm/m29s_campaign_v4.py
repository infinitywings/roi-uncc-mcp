"""Oracle-control wiring correction for the M29-S Attempt 4 campaign."""

from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import m29s_campaign as base
from . import m29s_campaign_v3 as v3
from . import m29s_semantic_compiler as design


ROOT = base.ROOT
AMENDMENT_PATH = ROOT / "m29s_attempt4_oracle_control_plan.json"
PREDECESSOR_ROOT = ROOT / "artifacts/m29s_factorial_attempt3"
PRIOR_MODEL_CALLS = 240
MAXIMUM_CUMULATIVE_CALLS = 816
DECISION_ID = "dec_01M1PSBNQ8VKKNK4H470SKEJYX"
PLAN_GATE_ID = "chk_01M1PSVJ4H3TR34G3ZN14Z1HAC"

BOUND_SOURCE_PATHS = v3.BOUND_SOURCE_PATHS + (
    "m29s_attempt4_oracle_control_plan.json",
    "g7confirm/m29s_campaign_v4.py",
    "g7confirm/m29s_independent_audit_v4.py",
    "tests/test_m29s_campaign_v4.py",
)

_BASE_VALIDATE_CONTRACT = base.validate_execution_contract
_V3_RUN_CELL = v3._run_cell


class M29SV4Error(RuntimeError):
    """Raised when the Attempt 4 oracle-control boundary is violated."""


@contextmanager
def _source_profile() -> Iterator[None]:
    previous = base.BOUND_SOURCE_PATHS
    base.BOUND_SOURCE_PATHS = BOUND_SOURCE_PATHS
    try:
        yield
    finally:
        base.BOUND_SOURCE_PATHS = previous


@contextmanager
def _v3_override() -> Iterator[None]:
    previous = {
        "validator": v3.validate_execution_contract,
        "sources": v3.BOUND_SOURCE_PATHS,
        "cell": v3._run_cell,
    }
    v3.validate_execution_contract = validate_execution_contract
    v3.BOUND_SOURCE_PATHS = BOUND_SOURCE_PATHS
    v3._run_cell = _run_cell
    try:
        yield
    finally:
        v3.validate_execution_contract = previous["validator"]
        v3.BOUND_SOURCE_PATHS = previous["sources"]
        v3._run_cell = previous["cell"]


def build_predecessor_receipt(root: Path = PREDECESSOR_ROOT) -> dict[str, Any]:
    contract_path = root / "contract.json"
    contract = base.strict_json(contract_path, "M29-S Attempt 3 contract")
    contract_issues = v3.validate_execution_contract(contract)
    cells = sorted(root.glob("cells/development/*/*.json"))
    rows = [base.strict_json(path, path.as_posix()) for path in cells]
    recorded = sum(int(row["accounting"]["model_calls"]) for row in rows)
    oracle_failures = sum(
        row["arm_id"] == "IA5-OC"
        and not row["endpoints"]["all_slot_program_exact"]
        for row in rows
    )
    body = {
        "schema_version": "grideval-g7-m29s-predecessor-stop/v3",
        "classification": design.CLASSIFICATION,
        "execution_contract_id": contract["execution_contract_id"],
        "execution_contract_sha256": base.sha256_file(contract_path),
        "status": "terminated_development_control_diagnostic",
        "reason": "IA5-OC copied the pre-amendment ledger",
        "development_cell_count": len(rows),
        "development_cell_hashes": [
            {"path": path.relative_to(root).as_posix(), "sha256": base.sha256_file(path)}
            for path in cells
        ],
        "recorded_model_calls": recorded,
        "maximum_unpersisted_concurrent_calls": 8,
        "conservative_model_calls": recorded + 8,
        "oracle_control_failures": oracle_failures,
        "held_out_cell_count": len(list(root.glob("cells/held_out/*/*.json"))),
        "development_receipt_created": (root / "development_receipt.json").exists(),
        "development_freeze_created": (root / "development_freeze.json").exists(),
        "source_contract_issues": contract_issues,
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
        "development_cell_count": 8,
        "recorded_model_calls": 10,
        "conservative_model_calls": 18,
        "oracle_control_failures": 1,
        "held_out_cell_count": 0,
        "source_contract_issues": [],
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise M29SV4Error(f"Attempt 3 predecessor evidence drift: {key}")
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
    amendment = base.strict_json(AMENDMENT_PATH, "M29-S Attempt 4 amendment")
    predecessor = base.strict_json(
        predecessor_receipt_path, "M29-S Attempt 3 stop receipt"
    )
    predecessor_body = dict(predecessor)
    predecessor_id = predecessor_body.pop("predecessor_receipt_id", None)
    if predecessor_id != base.content_id("m29spred", predecessor_body):
        raise M29SV4Error("predecessor receipt content address drift")
    if predecessor.get("conservative_model_calls") != 18:
        raise M29SV4Error("Attempt 3 predecessor accounting drift")
    with _source_profile():
        contract = base.build_execution_contract(**kwargs)
    body = dict(contract)
    body.pop("execution_contract_id")
    body["schema_version"] = "grideval-g7-m29s-execution-contract/v4"
    body["decision_id"] = DECISION_ID
    body["plan_gate_id"] = PLAN_GATE_ID
    body["oracle_control_amendment"] = {
        "path": AMENDMENT_PATH.relative_to(ROOT).as_posix(),
        "sha256": base.sha256_file(AMENDMENT_PATH),
        "schema_version": amendment["schema_version"],
    }
    body["predecessor_attempt"] = _artifact_reference(
        predecessor_receipt_path, "predecessor_receipt_id"
    )
    model = copy.deepcopy(body["model_contract"])
    model["maximum_completion_tokens_per_call"] = 1800
    model["prior_cumulative_calls"] = PRIOR_MODEL_CALLS
    model["maximum_cumulative_calls"] = MAXIMUM_CUMULATIVE_CALLS
    body["model_contract"] = model
    plan = base.strict_json(design.PLAN_PATH, "M29-S factorial plan")
    tool = copy.deepcopy(plan["tool_contract"])
    tool["validator_result_slots"] = sorted(
        set(design.SLOT_KEYS)
        | {"strategy_program", "required_evidence_ids", "evidence_ledger", "semantic_slots"}
    )
    body["tool_contract"] = tool
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
        "attempt3_conservative_calls": 18,
        "prior_model_calls": 240,
        "contracted_new_model_calls": 576,
        "maximum_cumulative_model_calls": 816,
        "pi_authorized_cumulative_ceiling": 1000,
        "remaining_after_attempt": 184,
    }
    body["transport_profile"] = {
        "workers": 4,
        "bounded_concurrency": True,
        "request_payloads_changed": False,
        "retry_count": 0,
        "schedule_bound_in_contract": True,
    }
    return {"execution_contract_id": base.content_id("m29sexec", body), **body}


def validate_execution_contract(contract: Mapping[str, Any]) -> list[str]:
    with _source_profile():
        issues = _BASE_VALIDATE_CONTRACT(contract)
    issues = [
        value for value in issues
        if value not in {
            "execution_contract_plan_gate",
            "execution_contract_cumulative_calls",
            "execution_contract_authorization_arithmetic",
        }
    ]
    if contract.get("schema_version") != "grideval-g7-m29s-execution-contract/v4":
        issues.append("execution_contract_schema_version")
    if contract.get("decision_id") != DECISION_ID:
        issues.append("execution_contract_decision")
    if contract.get("plan_gate_id") != PLAN_GATE_ID:
        issues.append("execution_contract_plan_gate_v4")
    expected_budget = {
        "pre_m29s_model_calls": 101,
        "attempt1_conservative_calls": 85,
        "attempt2_conservative_calls": 36,
        "attempt3_conservative_calls": 18,
        "prior_model_calls": 240,
        "contracted_new_model_calls": 576,
        "maximum_cumulative_model_calls": 816,
        "pi_authorized_cumulative_ceiling": 1000,
        "remaining_after_attempt": 184,
    }
    budget = contract.get("authorization_budget", {})
    for key, value in expected_budget.items():
        if budget.get(key) != value:
            issues.append(f"execution_contract_budget:{key}")
    if contract.get("model_contract", {}).get("maximum_completion_tokens_per_call") != 1800:
        issues.append("execution_contract_completion_cap")
    if contract.get("ledger_authority_contract", {}).get("include_absent_authorities") is not False:
        issues.append("execution_contract_ledger_authority")
    if contract.get("transport_profile", {}).get("workers") != 4:
        issues.append("execution_contract_transport")
    if contract.get("oracle_control_amendment", {}).get("sha256") != base.sha256_file(AMENDMENT_PATH):
        issues.append("execution_contract_amendment_hash")
    predecessor_ref = contract.get("predecessor_attempt", {})
    try:
        path = base._resolve_stored_path(predecessor_ref["path"])
        predecessor = base.strict_json(path, "Attempt 3 predecessor receipt")
        if predecessor_ref.get("sha256") != base.sha256_file(path):
            issues.append("execution_contract_predecessor_hash")
        if predecessor_ref.get("id") != predecessor.get("predecessor_receipt_id"):
            issues.append("execution_contract_predecessor_id")
        if predecessor.get("conservative_model_calls") != 18:
            issues.append("execution_contract_predecessor_calls")
    except Exception as exc:
        issues.append(f"execution_contract_predecessor:{type(exc).__name__}")
    return list(dict.fromkeys(issues))


def _run_cell(
    *, arm_id: str, row: Mapping[str, Any], packet: Mapping[str, Any],
    embedding: Mapping[str, Any], execution_contract_id: str,
) -> dict[str, Any]:
    cell = _V3_RUN_CELL(
        arm_id=arm_id,
        row=row,
        packet=packet,
        embedding=embedding,
        execution_contract_id=execution_contract_id,
    )
    if arm_id != "IA5-OC":
        return cell
    condition = base._condition_object(row)
    bundle = row["visible_evidence"]
    by_id = {value["passage_id"]: value for value in packet["corpus"]["passages"]}
    ids = (
        row["oracle_retrieval_passage_ids"]
        if condition.retrieval_required
        else row["flat_passage_ids"]
    )
    passages = [copy.deepcopy(by_id[value]) for value in ids]
    draft = copy.deepcopy(row["independent_oracle"])
    draft.pop("tested_model_called", None)
    draft.pop("validator_called", None)
    draft["evidence_ledger"] = v3.build_oracle_ledger(bundle, passages)
    scores = base._score_draft(
        draft=draft,
        interface="staged",
        condition=condition,
        bundle=bundle,
        passages=passages,
        oracle=row["independent_oracle"],
    )
    body = dict(cell)
    body.pop("cell_id")
    body["initial_draft"] = draft
    body["final_draft"] = draft
    body["initial_scores"] = scores
    body["final_scores"] = scores
    body["failure_class"] = None
    body["endpoints"] = {
        **scores,
        "initial_all_slot_program_exact": scores["all_slot_program_exact"],
        "repair_conversion": False,
        "repair_regression": False,
        "final_contract_violation": False,
        "retrieval_required": bool(condition.retrieval_required),
    }
    return {"cell_id": base.content_id("m29scell", body), **body}


def register_attempt(
    root: Path, *, predecessor_receipt_path: Path, **kwargs: Any
) -> dict[str, Any]:
    contract = build_execution_contract(
        predecessor_receipt_path=predecessor_receipt_path, **kwargs
    )
    issues = validate_execution_contract(contract)
    if issues:
        raise M29SV4Error(f"Attempt 4 contract invalid: {issues}")
    base.create_once_json(root / "contract.json", contract)
    return contract


def execute_split(root: Path, split: str) -> dict[str, Any]:
    with _v3_override():
        return v3.execute_split(root, split)


def build_development_freeze(root: Path) -> dict[str, Any]:
    with _v3_override():
        return v3.build_development_freeze(root)


def build_primary_receipt(root: Path, *, independent_clean: bool = False) -> dict[str, Any]:
    with _v3_override():
        return v3.build_primary_receipt(root, independent_clean=independent_clean)


def verify_primary_receipt(root: Path) -> list[str]:
    with _v3_override():
        return v3.verify_primary_receipt(root)


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
        print(base.canonical_json({"predecessor_receipt_id": receipt["predecessor_receipt_id"], "conservative_model_calls": receipt["conservative_model_calls"]}))
    elif args.command == "register":
        contract = register_attempt(
            args.root.resolve(), predecessor_receipt_path=args.predecessor_receipt.resolve(),
            design_contract_path=args.design_contract.resolve(), plan_audit_path=args.plan_audit.resolve(),
            split_commitment_path=args.split_commitment.resolve(), preflight_path=args.preflight.resolve(),
            development_embedding_path=args.development_embedding.resolve(), held_out_embedding_path=args.held_out_embedding.resolve(),
            authorization_note_id=args.authorization_note_id,
        )
        print(base.canonical_json({"execution_contract_id": contract["execution_contract_id"]}))
    elif args.command == "execute-split":
        receipt = execute_split(args.root.resolve(), args.split)
        print(base.canonical_json({"split_receipt_id": receipt["split_receipt_id"], "model_calls": receipt["model_calls"]}))
    elif args.command == "freeze-development":
        receipt = build_development_freeze(args.root.resolve())
        base.create_once_json(args.root.resolve() / "development_freeze.json", receipt)
        print(base.canonical_json({"development_freeze_id": receipt["development_freeze_id"]}))
    elif args.command == "primary":
        receipt = build_primary_receipt(args.root.resolve(), independent_clean=args.independent_clean)
        base.create_once_json(args.root.resolve() / "primary_receipt.json", receipt)
        print(base.canonical_json({"primary_receipt_id": receipt["primary_receipt_id"], "status": receipt["status"]}))
    else:
        issues = verify_primary_receipt(args.root.resolve())
        print(base.canonical_json({"issues": issues}))
        raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()

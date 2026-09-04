"""Independent non-importing exact-byte audit for M29-A.

This module intentionally imports no M29 primary harness, optimizer, candidate,
validator, or project helper. It recomputes identities, parity, costs, access
seals, and endpoint rows directly from immutable JSON artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AUDIT_SCHEMA_VERSION = "grideval-g7-m29-independent-audit/v1"
PRIMARY_SCHEMA_VERSION = "grideval-g7-m29-primary-receipt/v1"
CELL_SCHEMA_VERSION = "grideval-g7-m29-cell-receipt/v1"
EXECUTION_SCHEMA_VERSION = "grideval-g7-m29-execution-contract/v1"
DESIGN_CONTRACT_ID = (
    "m29contract_97d073f1ecbc03271346a6559dfc8367275a45a18519be13d38240da7bf423b0"
)
FROZEN_CANDIDATE_SURFACE_ID = (
    "m29surface_375078014f605fae2211b301f9ee54cfab6cecadf97f179e60fbe6a5ec9a220b"
)
CLASSIFICATION = "PRELIMINARY_ONLY"
ARM_IDS = ("IA2", "IA3-O", "IA4-D", "IA4-H", "IA4-HG")
OPTIMIZER_ARMS = frozenset({"IA3-O", "IA4-H", "IA4-HG"})
LLM_ARMS = frozenset({"IA4-D", "IA4-H", "IA4-HG"})
CONDITION_IDS = (
    "m29_sensitivity_reversal_left",
    "m29_sensitivity_reversal_right",
    "m29_operating_point_change_left",
    "m29_operating_point_change_right",
    "m29_validity_hole_left",
    "m29_validity_hole_right",
    "m29_budget_change_left",
    "m29_budget_change_right",
    "m29_delayed_feedback_left",
    "m29_delayed_feedback_right",
    "m29_infeasible_optimizer_output_left",
    "m29_infeasible_optimizer_output_right",
    "m29_tool_failure_class_left",
    "m29_tool_failure_class_right",
    "m29_strategy_rule_contradiction_left",
    "m29_strategy_rule_contradiction_right",
)
ACCOUNTING_FIELDS = {
    "model_calls",
    "model_prompt_tokens",
    "model_completion_tokens",
    "optimizer_calls",
    "optimizer_evaluations",
    "optimizer_compute_units",
    "read_only_tool_calls",
    "environment_queries",
    "wall_clock_ms",
    "invalid_proposals",
    "refusals",
    "accepted_decisions",
    "effective_decisions",
}
FALSE_ACCESS_FIELDS = (
    "model_service_started_or_restarted",
    "docker_accessed",
    "simulator_accessed",
    "detector_accessed",
    "defense_accessed",
    "embedding_accessed",
    "physical_actuator_accessed",
    "evaluation_accessed",
    "rka_attacker_view_accessed",
)


class IndependentAuditError(RuntimeError):
    """Raised when immutable audit inputs cannot be parsed safely."""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise IndependentAuditError("audit value is not canonical JSON") from exc


def _copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return prefix + _sha256_value(payload)


def _strict_json(path: Path, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise IndependentAuditError(f"{label} duplicates field {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise IndependentAuditError(f"{label} contains non-finite {value}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndependentAuditError(f"{label} is not one UTF-8 JSON value") from exc


def _create_once_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise IndependentAuditError(f"refusing to overwrite {path}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _expected_paths() -> tuple[str, ...]:
    return tuple(
        f"cells/{arm_id}/{condition_id}.json"
        for arm_id in ARM_IDS
        for condition_id in CONDITION_IDS
    )


def _endpoint_table(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        accounting = cell.get("accounting")
        endpoints = cell.get("endpoints")
        if not isinstance(accounting, Mapping):
            accounting = {}
        if not isinstance(endpoints, Mapping):
            endpoints = {}
        rows.append({
            "arm_id": cell.get("arm_id"),
            "condition_id": cell.get("condition_id"),
            "status": cell.get("status"),
            "oracle_selection_match": endpoints.get("oracle_selection_match"),
            "validity_compliant": endpoints.get("validity_compliant"),
            "evidence_conditioned_correct": endpoints.get(
                "evidence_conditioned_correct"
            ),
            "fixture_regret": endpoints.get("fixture_regret"),
            "typed_request_valid": endpoints.get("typed_request_valid"),
            "optimizer_status_correct": endpoints.get("optimizer_status_correct"),
            "validator_admitted": endpoints.get("validator_admitted"),
            "effective_decision": endpoints.get("effective_decision"),
            "model_calls": accounting.get("model_calls", 0),
            "model_prompt_tokens": accounting.get("model_prompt_tokens", 0),
            "model_completion_tokens": accounting.get(
                "model_completion_tokens", 0
            ),
            "optimizer_calls": accounting.get("optimizer_calls", 0),
            "optimizer_evaluations": accounting.get(
                "optimizer_evaluations", 0
            ),
            "environment_queries": accounting.get("environment_queries", 0),
            "invalid_proposals": accounting.get("invalid_proposals", 0),
            "refusals": accounting.get("refusals", 0),
        })
    return sorted(rows, key=lambda row: (
        ARM_IDS.index(str(row["arm_id"])), str(row["condition_id"])
    ))


def _append_once(issues: list[str], issue: str) -> None:
    if issue not in issues:
        issues.append(issue)


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]]]:
    """Recompute the M29-A audit result without importing primary code."""

    issues: list[str] = []
    try:
        contract = _strict_json(root / "contract.json", "execution contract")
        primary = _strict_json(root / "primary_receipt.json", "primary receipt")
    except IndependentAuditError as exc:
        return [f"required_artifact_parse_failed:{exc}"], []
    if not isinstance(contract, dict) or not isinstance(primary, dict):
        return ["required_artifact_not_object"], []

    contract_content = _copy(contract)
    contract_id = contract_content.pop("execution_contract_id", None)
    if contract_id != _content_id("m29exec_", contract_content):
        _append_once(issues, "execution_contract_content_address_drift")
    if contract.get("schema_version") != EXECUTION_SCHEMA_VERSION:
        _append_once(issues, "execution_contract_schema_drift")
    if contract.get("design_contract_id") != DESIGN_CONTRACT_ID:
        _append_once(issues, "design_contract_id_drift")
    if contract.get("classification") != CLASSIFICATION:
        _append_once(issues, "execution_classification_drift")
    if contract.get("expected_cell_paths") != list(_expected_paths()):
        _append_once(issues, "expected_cell_paths_drift")
    if contract.get("m29b_authorized") is not False:
        _append_once(issues, "execution_m29b_authorized")
    boundary = contract.get("access_boundary")
    if not isinstance(boundary, Mapping):
        _append_once(issues, "execution_access_boundary_missing")
    else:
        for field, value in boundary.items():
            if field == "evaluation_seeds_allowed":
                if value != []:
                    _append_once(issues, "execution_evaluation_seeds_allowed")
            elif value is not False:
                _append_once(issues, f"execution_access_allowed:{field}")

    repo_root = Path(__file__).resolve().parents[3]
    source_bindings = contract.get("source_bindings")
    if not isinstance(source_bindings, list) or len(source_bindings) != 8:
        _append_once(issues, "source_binding_count_drift")
    else:
        for item in source_bindings:
            if not isinstance(item, Mapping):
                _append_once(issues, "source_binding_not_object")
                continue
            path = repo_root / str(item.get("path", ""))
            try:
                digest = _sha256_file(path)
                size = path.stat().st_size
            except OSError:
                _append_once(issues, f"source_missing:{item.get('path')}")
                continue
            if digest != item.get("sha256"):
                _append_once(issues, f"source_hash_drift:{item.get('path')}")
            if size != item.get("bytes"):
                _append_once(issues, f"source_size_drift:{item.get('path')}")
    optimizer_source = (contract.get("optimizer") or {}).get("source_sha256")
    registered_conditions = {
        item.get("condition_id"): item
        for item in contract.get("conditions", [])
        if isinstance(item, Mapping) and isinstance(item.get("condition_id"), str)
    }

    cells: list[dict[str, Any]] = []
    for relative in _expected_paths():
        try:
            cell = _strict_json(root / relative, f"cell {relative}")
        except IndependentAuditError as exc:
            _append_once(issues, f"cell_parse_failed:{relative}:{exc}")
            continue
        if not isinstance(cell, dict):
            _append_once(issues, f"cell_not_object:{relative}")
            continue
        cells.append(cell)
        parts = Path(relative).parts
        expected_arm = parts[1]
        expected_condition = Path(parts[2]).stem
        if cell.get("arm_id") != expected_arm:
            _append_once(issues, f"cell_arm_path_drift:{relative}")
        if cell.get("condition_id") != expected_condition:
            _append_once(issues, f"cell_condition_path_drift:{relative}")
        cell_content = _copy(cell)
        cell_id = cell_content.pop("cell_id", None)
        if cell_id != _content_id("m29cell_", cell_content):
            _append_once(issues, f"cell_content_address_drift:{relative}")
        if cell.get("schema_version") != CELL_SCHEMA_VERSION:
            _append_once(issues, f"cell_schema_drift:{relative}")
        if cell.get("execution_contract_id") != contract_id:
            _append_once(issues, f"cell_contract_drift:{relative}")
        if cell.get("classification") != CLASSIFICATION:
            _append_once(issues, f"cell_classification_drift:{relative}")
        registered = registered_conditions.get(expected_condition)
        if not isinstance(registered, Mapping):
            _append_once(issues, f"condition_registration_missing:{relative}")
        else:
            eligible = expected_arm in registered.get("eligible_arms", [])
            if eligible and cell.get("status") != "completed":
                _append_once(issues, f"applicable_cell_not_completed:{relative}")
            if not eligible and cell.get("status") != "not_applicable":
                _append_once(issues, f"ineligible_cell_status:{relative}")
        access = cell.get("access_boundary")
        if not isinstance(access, Mapping):
            _append_once(issues, f"cell_access_missing:{relative}")
        else:
            for field in FALSE_ACCESS_FIELDS:
                if access.get(field) is not False:
                    _append_once(issues, f"prohibited_access:{relative}:{field}")
            if access.get("final_evaluation_seeds_accessed") != []:
                _append_once(issues, f"final_seed_access:{relative}")
        accounting = cell.get("accounting")
        if not isinstance(accounting, Mapping):
            _append_once(issues, f"accounting_missing:{relative}")
        else:
            if set(accounting) != ACCOUNTING_FIELDS:
                _append_once(issues, f"accounting_fields_drift:{relative}")
            for field in ACCOUNTING_FIELDS - {"wall_clock_ms"}:
                value = accounting.get(field)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    _append_once(issues, f"accounting_value_invalid:{relative}:{field}")
            wall = accounting.get("wall_clock_ms")
            if (
                isinstance(wall, bool)
                or not isinstance(wall, (int, float))
                or not math.isfinite(float(wall))
                or float(wall) < 0
            ):
                _append_once(issues, f"wall_clock_invalid:{relative}")
            if accounting.get("environment_queries") != 0:
                _append_once(issues, f"environment_query_used:{relative}")
            if accounting.get("read_only_tool_calls") != 0:
                _append_once(issues, f"undeclared_tool_used:{relative}")
            if accounting.get("model_calls", 0) > 1:
                _append_once(issues, f"model_call_cap:{relative}")
            if accounting.get("model_completion_tokens", 0) > 512:
                _append_once(issues, f"completion_token_cap:{relative}")
            if accounting.get("optimizer_evaluations", 0) > 12:
                _append_once(issues, f"optimizer_evaluation_cap:{relative}")
        model = cell.get("model")
        if isinstance(model, Mapping) and model.get("retry_count") != 0:
            _append_once(issues, f"retry_detected:{relative}")
        request = cell.get("optimization_request")
        if isinstance(request, Mapping):
            if expected_arm not in OPTIMIZER_ARMS:
                _append_once(issues, f"optimizer_access_drift:{relative}")
            if request.get("candidate_surface_id") != FROZEN_CANDIDATE_SURFACE_ID:
                _append_once(issues, f"candidate_surface_drift:{relative}")
            if request.get("environment_query_budget") != 0:
                _append_once(issues, f"optimizer_query_budget_drift:{relative}")
            request_optimizer = request.get("optimizer")
            if not isinstance(request_optimizer, Mapping):
                _append_once(issues, f"optimizer_metadata_missing:{relative}")
            elif request_optimizer.get("source_sha256") != optimizer_source:
                _append_once(issues, f"optimizer_source_drift:{relative}")
        result = cell.get("optimizer_result")
        if isinstance(result, Mapping):
            if result.get("optimizer_source_sha256") != optimizer_source:
                _append_once(issues, f"optimizer_result_source_drift:{relative}")
            if result.get("environment_queries_used") != 0:
                _append_once(issues, f"optimizer_environment_query:{relative}")
        endpoints = cell.get("endpoints")
        validation = cell.get("validation")
        if isinstance(endpoints, Mapping) and endpoints.get("effective_decision"):
            if not isinstance(validation, Mapping):
                _append_once(issues, f"effective_without_validation:{relative}")
            elif validation.get("common_validator_id") != "common_plan_validator_v1":
                _append_once(issues, f"validator_identity_drift:{relative}")
            elif validation.get("accepted") is not True:
                _append_once(issues, f"unadmitted_effective_decision:{relative}")

    if len(cells) != 80:
        _append_once(issues, "cell_count_drift")
    by_condition: dict[str, list[Mapping[str, Any]]] = {
        condition_id: [] for condition_id in CONDITION_IDS
    }
    for cell in cells:
        condition_id = cell.get("condition_id")
        if condition_id in by_condition:
            by_condition[str(condition_id)].append(cell)
    for condition_id, items in by_condition.items():
        if len(items) != 5:
            _append_once(issues, f"condition_arm_count:{condition_id}")
            continue
        if len({item.get("semantic_digest") for item in items}) != 1:
            _append_once(issues, f"raw_information_digest_drift:{condition_id}")
        representations = {item["arm_id"]: item.get("representation") for item in items}
        if representations.get("IA4-H") != "flat_text":
            _append_once(issues, f"flat_representation_drift:{condition_id}")
        if representations.get("IA4-HG") != "structured_graph":
            _append_once(issues, f"graph_representation_drift:{condition_id}")

    total_model_calls = sum(
        int((cell.get("accounting") or {}).get("model_calls", 0))
        for cell in cells
    )
    if total_model_calls > 48:
        _append_once(issues, "campaign_model_call_cap")

    table = _endpoint_table(cells)
    primary_content = _copy(primary)
    primary_id = primary_content.pop("primary_receipt_id", None)
    if primary_id != _content_id("m29primary_", primary_content):
        _append_once(issues, "primary_content_address_drift")
    if primary.get("schema_version") != PRIMARY_SCHEMA_VERSION:
        _append_once(issues, "primary_schema_drift")
    if primary.get("classification") != CLASSIFICATION:
        _append_once(issues, "primary_classification_drift")
    if primary.get("execution_contract_id") != contract_id:
        _append_once(issues, "primary_contract_id_drift")
    if primary.get("endpoint_table") != table:
        _append_once(issues, "endpoint_table_not_reproduced")
    if primary.get("endpoint_table_sha256") != _sha256_value(table):
        _append_once(issues, "endpoint_table_digest_drift")
    if primary.get("issues") != []:
        _append_once(issues, "primary_issues_nonempty")
    if primary.get("status") != "passed":
        _append_once(issues, "primary_status_not_passed")
    if primary.get("m29b_authorized") is not False:
        _append_once(issues, "primary_m29b_authorized")
    prohibited_claims = {
        "llm_superiority",
        "physical_harm",
        "stealth",
        "detector_evasion",
        "generalization",
        "confirmatory_inference",
    }
    claim_boundary = primary.get("claim_boundary")
    if not isinstance(claim_boundary, Mapping):
        _append_once(issues, "claim_boundary_missing")
    elif not prohibited_claims.issubset(set(claim_boundary.get("prohibited", []))):
        _append_once(issues, "prohibited_claim_boundary_incomplete")
    return sorted(issues), table


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues, table = verify(root)
    contract = _strict_json(root / "contract.json", "execution contract")
    primary = _strict_json(root / "primary_receipt.json", "primary receipt")
    content = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": CLASSIFICATION,
        "execution_contract_id": contract.get("execution_contract_id"),
        "primary_receipt_id": primary.get("primary_receipt_id"),
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "independent_imports_primary": False,
        "auditor_source_sha256": _sha256_file(Path(__file__).resolve()),
        "endpoint_table": table,
        "endpoint_table_sha256": _sha256_value(table),
        "source_hashes_recomputed": True,
        "costs_recomputed": True,
        "access_seals_recomputed": True,
        "m29b_authorized": False,
    }
    receipt = _copy(content)
    receipt["audit_id"] = _content_id("m29audit_", content)
    return receipt


def verify_audit_receipt(root: Path,
                         receipt: Mapping[str, Any]) -> list[str]:
    expected = build_audit_receipt(root)
    # created_at is evidence metadata, not a deterministic verification input.
    expected_time = expected.pop("created_at_utc")
    actual = _copy(receipt)
    actual_time = actual.pop("created_at_utc", None)
    del expected_time
    issues: list[str] = []
    if not isinstance(actual_time, str) or not actual_time:
        issues.append("audit_created_at_missing")
    actual_id = actual.pop("audit_id", None)
    expected_id = expected.pop("audit_id", None)
    # Recompute the stored ID using its actual timestamp.
    id_content = _copy(receipt)
    id_content.pop("audit_id", None)
    if actual_id != _content_id("m29audit_", id_content):
        issues.append("audit_content_address_drift")
    if expected_id is None:
        issues.append("audit_rebuild_failed")
    if actual != expected:
        issues.append("audit_recomputed_payload_drift")
    return sorted(set(issues))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    receipt = build_audit_receipt(args.root)
    if args.write:
        _create_once_json(args.root / "independent_audit_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    raise SystemExit(0 if receipt["issues"] == [] else 1)


if __name__ == "__main__":
    main()

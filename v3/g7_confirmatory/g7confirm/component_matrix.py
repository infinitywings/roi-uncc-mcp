"""Validation for the development-only AI-V2 component matrix."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .orchestration_contract import ContractViolation


MATRIX_SCHEMA_VERSION = "grideval-g7-ai-v2-component-matrix/v1"
REQUIRED_COMPONENTS = {
    "timing_intelligence",
    "domain_knowledge",
    "diversification_guidance",
    "dynamic_history",
    "fixed_maximum_power",
    "safety_refusal",
}
REQUIRED_CONSTRAINTS = {
    "same_typed_plan_schema",
    "same_action_authority",
    "same_outer_rollout_budget",
    "same_dual_budget",
    "same_observation_access_except_declared_ablation",
    "same_invalid_action_policy",
    "development_only",
    "evaluation_sealed",
}
REQUIRED_METRICS = {
    "valid_proposal_rate",
    "safety_refusal_rate",
    "effective_action_rate",
    "target_diversity",
    "best_of_k_paired_harm",
}


def load_component_matrix(path: str | Path) -> dict[str, Any]:
    matrix_path = Path(path)
    data = json.loads(matrix_path.read_text(encoding="utf-8"))
    validate_component_matrix(data)
    return data


def validate_component_matrix(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ContractViolation("component matrix must be a JSON object")
    if data.get("schema_version") != MATRIX_SCHEMA_VERSION:
        raise ContractViolation("unsupported component-matrix schema_version")
    if data.get("executable") is not False:
        raise ContractViolation("component matrix must remain non-executable")
    if data.get("campaign_authorized") is not False:
        raise ContractViolation("component matrix cannot authorize a campaign")
    if data.get("evaluation_sealed") is not True:
        raise ContractViolation("component matrix must keep evaluation sealed")

    components = data.get("components")
    if not isinstance(components, list):
        raise ContractViolation("components must be a list")
    component_ids = [item.get("id") for item in components if isinstance(item, dict)]
    if len(component_ids) != len(components):
        raise ContractViolation("every component must be an object with an id")
    if len(component_ids) != len(set(component_ids)):
        raise ContractViolation("component IDs must be unique")
    missing = REQUIRED_COMPONENTS - set(component_ids)
    if missing:
        raise ContractViolation(f"component matrix is missing: {sorted(missing)}")
    for item in components:
        for field in ("role", "treatment", "control", "estimand", "evidence_status"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ContractViolation(
                    f"component {item['id']} requires a non-empty {field}"
                )

    comparators = data.get("comparators")
    if not isinstance(comparators, list) or not comparators:
        raise ContractViolation("comparators must be a non-empty list")
    comparator_ids = {item.get("id") for item in comparators if isinstance(item, dict)}
    for required in ("B2a_fixed_maximum_power", "IA3_nonllm_adaptive"):
        if required not in comparator_ids:
            raise ContractViolation(f"required comparator is missing: {required}")
    fixed = next(
        item for item in comparators if item.get("id") == "B2a_fixed_maximum_power"
    )
    if fixed.get("adaptive") is not False or fixed.get("hand_crafted") is not True:
        raise ContractViolation(
            "fixed maximum-power comparator must be hand-crafted and non-adaptive"
        )

    constraints = set(data.get("enforced_constraints", []))
    if not REQUIRED_CONSTRAINTS.issubset(constraints):
        raise ContractViolation(
            f"enforced constraints are missing: {sorted(REQUIRED_CONSTRAINTS - constraints)}"
        )
    metrics = set(data.get("required_metrics", []))
    if not REQUIRED_METRICS.issubset(metrics):
        raise ContractViolation(
            f"required metrics are missing: {sorted(REQUIRED_METRICS - metrics)}"
        )

    contrasts = data.get("estimable_contrasts")
    if not isinstance(contrasts, list) or not contrasts:
        raise ContractViolation("estimable_contrasts must be a non-empty list")
    contrast_components = {
        item.get("component_id") for item in contrasts if isinstance(item, dict)
    }
    causal_components = REQUIRED_COMPONENTS - {"safety_refusal"}
    if not causal_components.issubset(contrast_components):
        raise ContractViolation(
            "every causal component must map to an estimable contrast"
        )


def component_matrix_sha256(data: dict[str, Any]) -> str:
    validate_component_matrix(data)
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

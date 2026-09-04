"""Build the content-addressed M29-S factorial design contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from . import m29s_semantic_compiler as design


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "M29S_EXECUTOR_BACKBRIEF.md",
    "M29S_INDEPENDENT_AUDIT_PLAN.md",
    "m29s_factorial_plan.json",
    "m29s_evidence_ledger.schema.json",
    "m29s_semantic_slots.schema.json",
    "m29s_strategy_program.schema.json",
    "g7confirm/m29s_semantic_compiler.py",
    "g7confirm/m29s_design_contract.py",
    "g7confirm/m29s_plan_audit.py",
    "tests/test_m29s_semantic_compiler.py",
    "tests/test_m29s_plan_audit.py",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return design.content_id(prefix, payload)


def build_contract(fixture_path: Path) -> dict[str, Any]:
    fixture = design.strict_json_file(fixture_path, "M29-S design fixture")
    fixture_body = dict(fixture)
    fixture_identifier = fixture_body.pop("design_fixture_id", None)
    if fixture_identifier != design.content_id("m29sfixture", fixture_body):
        raise design.M29SContractError("design fixture content address drift")
    if design.verify_m29r_disjointness(fixture):
        raise design.M29SContractError("design fixture overlaps M29-R")
    sources = design.validate_design_sources()
    missing = [path for path in SOURCE_PATHS if not (ROOT / path).is_file()]
    if missing:
        raise design.M29SContractError(f"missing contract source files: {missing}")
    plan = sources["plan"]
    body = {
        "schema_version": "grideval-g7-m29s-design-contract/v1",
        "classification": design.CLASSIFICATION,
        "project_id": design.PROJECT_ID,
        "mission_id": design.MISSION_ID,
        "decision_id": design.DECISION_ID,
        "predecessor_commit": "ff91ba9",
        "design_fixture": {
            "path": fixture_path.relative_to(ROOT).as_posix(),
            "sha256": design.sha256_file(fixture_path),
            "design_fixture_id": fixture_identifier,
            "condition_count": fixture["condition_count"],
            "conditions_per_split": fixture["conditions_per_split"],
        },
        "registered_arms": [row["arm_id"] for row in plan["arms"]],
        "registered_contrasts": [
            row["contrast_id"] for row in plan["registered_contrasts"]
        ],
        "factor_contract": plan["factors"],
        "interface_contract": plan["interface_contract"],
        "tool_contract": plan["tool_contract"],
        "model_contract": plan["model_contract"],
        "retrieval_contract": plan["retrieval_contract"],
        "held_out_mechanism_gate": plan["held_out_mechanism_gate"],
        "access_authorization": {
            "offline_llm_after_plan_gate": True,
            "existing_embedding_after_plan_gate": True,
            "embedding_service_start_restart_or_reconfigure": False,
            "docker": False,
            "simulator": False,
            "detector": False,
            "defense": False,
            "network_impairment": False,
            "physical_actuator": False,
            "final_evaluation": False,
            "evaluation_seeds_9101_9112": False,
            "rka_governance_attacker_view": False,
        },
        "oracle_independence": {
            "latent_spec_created_before_rendering": True,
            "tested_llm_called": False,
            "validator_called": False,
            "simulator_data_used": False,
            "final_evaluation_data_used": False,
        },
        "source_hashes": [
            {"path": path, "sha256": design.sha256_file(ROOT / path)}
            for path in SOURCE_PATHS
        ],
        "m29b_authorized": False,
    }
    return {"design_contract_id": content_id("m29scontract", body), **body}


def create_once_json(path: Path, payload: Any) -> None:
    design.create_once_json(path, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = build_contract(args.fixture.resolve())
    create_once_json(args.output, contract)
    print(canonical_json({
        "status": "created",
        "output": str(args.output),
        "design_contract_id": contract["design_contract_id"],
    }))


if __name__ == "__main__":
    main()

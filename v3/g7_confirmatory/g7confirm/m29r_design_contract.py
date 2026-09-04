"""Create the source-frozen M29-R plan-validation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = "PRELIMINARY_ONLY"

SOURCE_PATHS = (
    "M29R_EXECUTOR_BACKBRIEF.md",
    "M29R_INDEPENDENT_AUDIT_PLAN.md",
    "m29r_complementarity_plan.json",
    "m29r_strategy_corpus.json",
    "m29r_retrieval_queries.json",
    "m29r_evidence_bundle.schema.json",
    "m29r_strategy_program.schema.json",
    "m29r_multistage_request.schema.json",
    "m29r_optimizer_result.schema.json",
    "m29r_attack_plan.schema.json",
    "g7confirm/m29r_complementarity.py",
    "g7confirm/m29r_design_contract.py",
    "g7confirm/m29r_plan_audit.py",
    "tests/test_m29r_complementarity.py",
)


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


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{sha256_value(payload)}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def build_contract(fixture_path: Path) -> dict[str, Any]:
    plan = load_json(ROOT / "m29r_complementarity_plan.json")
    fixture = load_json(fixture_path)
    if plan.get("classification") != CLASSIFICATION:
        raise ValueError("plan classification drift")
    if fixture.get("classification") != CLASSIFICATION:
        raise ValueError("fixture classification drift")
    source_hashes: list[dict[str, str]] = []
    for relative in SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        source_hashes.append({"path": relative, "sha256": sha256_file(path)})
    body = {
        "schema_version": "grideval-g7-m29r-design-contract/v1",
        "classification": CLASSIFICATION,
        "project_id": "prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
        "mission_id": "mis_01M1PC1T0M7BAVX9NWB19P0FWC",
        "decision_id": "dec_01M1PBZSNK0MP4E3NH28H26841",
        "predecessor_commit": "d83d350",
        "design_fixture": {
            "path": fixture_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(fixture_path),
            "design_fixture_id": fixture["design_fixture_id"],
            "condition_count": fixture["condition_count"],
        },
        "source_hashes": source_hashes,
        "registered_arms": [row["arm_id"] for row in plan["arms"]],
        "registered_contrasts": [row["contrast_id"] for row in plan["registered_contrasts"]],
        "scientific_unlock_rule": plan["scientific_unlock_rule"],
        "secondary_retrieval_rule": plan["secondary_retrieval_rule"],
        "model_contract": plan["model_contract"],
        "retrieval_contract": plan["retrieval_contract"],
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
            "independent_recursive_enumerator": True,
            "tested_llm_called": False,
            "embedding_called": False,
            "simulator_data_used": False,
            "final_evaluation_data_used": False,
        },
        "m29b_authorized": False,
    }
    return {"design_contract_id": content_id("m29rcontract", body), **body}


def create_once_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = args.fixture.resolve()
    contract = build_contract(fixture)
    create_once_json(args.output, contract)
    print(canonical_json({"design_contract_id": contract["design_contract_id"], "output": args.output.as_posix()}))


if __name__ == "__main__":
    main()

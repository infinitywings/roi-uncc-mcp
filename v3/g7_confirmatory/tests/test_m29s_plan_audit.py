from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from g7confirm import m29s_design_contract as contract_builder
from g7confirm import m29s_plan_audit as audit
from g7confirm import m29s_semantic_compiler as design


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_design_contract_and_independent_audit_pass(tmp_path: Path) -> None:
    fixture_path = design.ROOT / "artifacts/m29s_design_attempt1/design_fixture.json"
    contract = contract_builder.build_contract(fixture_path)
    contract_path = tmp_path / "contract.json"
    _write_json(contract_path, contract)
    issues, loaded, fixture = audit.verify(contract_path)
    assert issues == []
    assert loaded["design_contract_id"] == contract["design_contract_id"]
    assert fixture["condition_count"] == 32


def test_checked_in_contract_build_path_is_relative() -> None:
    fixture = design.build_design_fixture()
    path = design.ROOT / "artifacts/m29s_design_attempt1/design_fixture.json"
    if path.exists():
        contract = contract_builder.build_contract(path)
        assert contract["design_fixture"]["path"] == "artifacts/m29s_design_attempt1/design_fixture.json"


def test_independent_audit_detects_call_parity_mutation(tmp_path: Path) -> None:
    plan = json.loads(design.PLAN_PATH.read_text(encoding="utf-8"))
    next(row for row in plan["arms"] if row["arm_id"] == "IA4-SVR")["model_calls_per_cell"] = 3
    original_plan = audit.PLAN_PATH
    mutated_path = tmp_path / "plan.json"
    _write_json(mutated_path, plan)
    issues: list[str] = []
    audit._verify_plan(plan, issues)
    assert "factorial_call_parity" in issues
    assert "per_split_call_budget" in issues
    assert original_plan == audit.PLAN_PATH


def test_independent_audit_detects_fixture_mutation() -> None:
    fixture = design.build_design_fixture()
    mutated = copy.deepcopy(fixture)
    mutated["conditions"][0]["latent_condition"]["semantic_program"]["effect_direction"] = "decrease"
    issues: list[str] = []
    audit._verify_fixture(mutated, issues)
    assert "design_fixture_content_address" in issues
    assert any(item.startswith("oracle_semantics:") for item in issues)


def test_independent_auditor_does_not_import_primary_modules() -> None:
    tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any("m29s_semantic_compiler" in name for name in imports)
    assert not any("m29s_design_contract" in name for name in imports)


def test_audit_receipt_is_content_addressed(tmp_path: Path) -> None:
    fixture_path = design.ROOT / "artifacts/m29s_design_attempt1/design_fixture.json"
    contract = contract_builder.build_contract(fixture_path)
    contract_path = tmp_path / "contract.json"
    _write_json(contract_path, contract)
    receipt = audit.build_audit_receipt(contract_path)
    body = dict(receipt)
    identifier = body.pop("audit_id")
    assert identifier == audit.content_id("m29splanaudit", body)

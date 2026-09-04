"""Build and verify the M28 matched IA3/IA4 decision-to-action package."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from .m25_adapter_transaction import verify_qualification as verify_m25
from .m25_independent_audit import verify_audit_receipt as verify_m25_audit
from .m26_independent_audit import audit_qualification as audit_m26
from .m26_live_empirical_decision import (
    action_request_paths as m26_action_request_paths,
    build_contract as build_m26_contract,
    verify_receipt as verify_m26_receipt,
)
from .m27_independent_audit import verify_receipt as verify_m27_audit
from .m27_repeatability_coverage import verify_evidence as verify_m27
from .m28_runtime import (
    ACTORS,
    COMMAND_KW,
    M28_RUNTIME_PROFILES,
    OPERATING_POINT,
    SEED,
    TARGET_ID,
    WINDOWS,
    WINDOW_SECONDS,
    pair_id,
)
from .manifest import create_once_json
from .preliminary_only_gate import validate_preliminary_action_request
from .runtime import DEFAULT_CONFIG, M18_GATE_ARTIFACT


CONTRACT_SCHEMA_VERSION = "grideval-g7-m28-decision-to-action-contract/v1"
EVIDENCE_SCHEMA_VERSION = "grideval-g7-m28-decision-to-action-evidence/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1N1G1JVYHSXVZFHREF01QKA"
DECISION_ID = "dec_01M1N1F7JDKCVK43WGCC6NGYW1"
CLASSIFICATION = "PRELIMINARY_ONLY"
EXPECTED_CANDIDATE_ID = "cand_bc73d19dea133043082f"
ABSTRACT_TARGET_ID = "DER_B"
IMAGE_TAG = "docker-cosim:latest"
IMAGE_ID = "sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7"
EXPECTED_M18_SHA256 = "e31a49d758700a3d30e4d7e3d5469b831b3f52370954fa92238eac6aa4dc3e9d"

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_CORE_PATH = Path(__file__).with_name("runtime.py")
RUNTIME_WRAPPER_PATH = Path(__file__).with_name("m28_runtime.py")
EXECUTOR_PATH = Path(__file__).with_name("m28_execute.py")
AUDITOR_PATH = Path(__file__).with_name("m28_independent_audit.py")
SPEC_PATH = PACKAGE_ROOT / "experiment_spec.yaml"
M25_ROOT = PACKAGE_ROOT / "artifacts" / "m25_adapter_transaction_attempt1"
M26_ROOT = PACKAGE_ROOT / "artifacts" / "m26_live_empirical_attempt1"
M27_ROOT = PACKAGE_ROOT / "artifacts" / "m27_repeatability_coverage_attempt1"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_json_file(path: Path, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate field: {key}")
            result[key] = item
        return result

    def reject_constant(item: str) -> None:
        raise ValueError(f"{label} contains non-finite constant: {item}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _load_upstream() -> dict[str, Any]:
    m25_contract = _strict_json_file(M25_ROOT / "contract.json", "M25 contract")
    m25_receipt = _strict_json_file(
        M25_ROOT / "qualification_receipt.json", "M25 receipt"
    )
    m25_audit = _strict_json_file(
        M25_ROOT / "independent_audit_receipt.json", "M25 audit"
    )
    if verify_m25(M25_ROOT):
        raise ValueError("M25 qualification no longer verifies")
    if verify_m25_audit(M25_ROOT, m25_audit):
        raise ValueError("M25 independent audit no longer verifies")

    m26_contract = _strict_json_file(M26_ROOT / "contract.json", "M26 contract")
    if m26_contract != build_m26_contract(m26_action_request_paths(M26_ROOT)):
        raise ValueError("M26 contract drifts from current executable bytes")
    m26_receipt = _strict_json_file(M26_ROOT / "receipt.json", "M26 receipt")
    m26_audit = _strict_json_file(
        M26_ROOT / "independent_audit_receipt.json", "M26 audit"
    )
    if verify_m26_receipt(m26_receipt, m26_contract):
        raise ValueError("M26 receipt no longer verifies")
    if audit_m26(M26_ROOT):
        raise ValueError("M26 independent audit no longer verifies")
    if m26_audit.get("status") != "passed" or m26_audit.get("issues") != []:
        raise ValueError("M26 stored audit is not passing")

    if verify_m27(M27_ROOT):
        raise ValueError("M27 evidence no longer verifies")
    m27_evidence = _strict_json_file(
        M27_ROOT / "m27_repeatability_coverage.json", "M27 evidence"
    )
    m27_audit = _strict_json_file(
        M27_ROOT / "independent_audit_receipt.json", "M27 audit"
    )
    if verify_m27_audit(M27_ROOT, m27_audit):
        raise ValueError("M27 independent audit no longer verifies")

    ia3 = m25_receipt.get("transactions", {}).get("IA3", {})
    ia4 = m26_receipt.get("result", {})
    for actor, record in (("IA3", ia3), ("IA4", ia4)):
        if record.get("selected_candidate_id") != EXPECTED_CANDIDATE_ID:
            raise ValueError(f"{actor} selected candidate drift")
        if record.get("selected_target") != ABSTRACT_TARGET_ID:
            raise ValueError(f"{actor} selected target drift")
        validation = record.get("validation", {})
        if validation.get("accepted") is not True:
            raise ValueError(f"{actor} validated-plan state drift")
        if validation.get("commands") != {ABSTRACT_TARGET_ID: [30, 0]}:
            raise ValueError(f"{actor} validated command drift")

    return {
        "M25_contract": m25_contract,
        "M25_receipt": m25_receipt,
        "M25_audit": m25_audit,
        "M26_contract": m26_contract,
        "M26_receipt": m26_receipt,
        "M26_audit": m26_audit,
        "M27_evidence": m27_evidence,
        "M27_audit": m27_audit,
    }


def _source_bindings() -> dict[str, dict[str, Any]]:
    paths = {
        "M18_gate": M18_GATE_ARTIFACT,
        "M25_contract": M25_ROOT / "contract.json",
        "M25_receipt": M25_ROOT / "qualification_receipt.json",
        "M25_independent_audit": M25_ROOT / "independent_audit_receipt.json",
        "M26_contract": M26_ROOT / "contract.json",
        "M26_receipt": M26_ROOT / "receipt.json",
        "M26_independent_audit": M26_ROOT / "independent_audit_receipt.json",
        "M27_evidence": M27_ROOT / "m27_repeatability_coverage.json",
        "M27_independent_audit": M27_ROOT / "independent_audit_receipt.json",
        "runtime_core": RUNTIME_CORE_PATH,
        "M28_runtime_wrapper": RUNTIME_WRAPPER_PATH,
        "M28_evidence_builder": Path(__file__).resolve(),
        "M28_executor": EXECUTOR_PATH,
        "M28_independent_auditor": AUDITOR_PATH,
        "DER_configuration": DEFAULT_CONFIG,
        "experiment_specification": SPEC_PATH,
    }
    bindings = {name: _binding(path) for name, path in paths.items()}
    if bindings["M18_gate"]["sha256"] != EXPECTED_M18_SHA256:
        raise ValueError("M18 gate hash drift")
    return bindings


def build_action_requests() -> dict[str, dict[str, dict[str, Any]]]:
    """Return the four exact M18 simulator requests for M28."""

    runtime_hash = _sha256_file(RUNTIME_CORE_PATH)
    config_hash = _sha256_file(DEFAULT_CONFIG)
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for actor in ACTORS:
        profile = M28_RUNTIME_PROFILES[pair_id(actor)]
        common = {
            "action_type": "simulator_execution",
            "partition_role": "attack_development",
            "seed": SEED,
            "output_classification": CLASSIFICATION,
            "create_once": True,
            "manifest_sha256": EXPECTED_M18_SHA256,
            "code_sha256": runtime_hash,
            "config_sha256": config_hash,
            "budget_id": profile["budget_id"],
            "paired_benign_id": profile["benign_action_id"],
            "final_evaluation_data_accessed": False,
            "physical_field_actuator": False,
            "starts_or_restarts_service": False,
            "retain_failures": True,
            "local_service_identity": None,
        }
        result[actor] = {
            "benign_action_request.json": {
                "action_id": profile["benign_action_id"],
                **common,
            },
            "attack_action_request.json": {
                "action_id": profile["probe_action_ids"][f"{TARGET_ID}:+30"],
                **common,
            },
        }
        for name, request in result[actor].items():
            issues = validate_preliminary_action_request(request)
            if issues:
                raise ValueError(f"M28 request rejected ({actor}/{name}): {issues}")
    return _canonical_copy(result)


def _load_action_requests(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    expected = build_action_requests()
    actual: dict[str, dict[str, dict[str, Any]]] = {}
    for actor, requests in expected.items():
        actual[actor] = {}
        for name in requests:
            actual[actor][name] = _strict_json_file(
                root / "requests" / actor / name,
                f"M28 {actor} {name}",
            )
    if actual != expected:
        raise ValueError("stored M28 action requests drift")
    return actual


def build_contract(root: Path) -> dict[str, Any]:
    """Build the final-code M28 contract before simulator execution."""

    upstream = _load_upstream()
    requests = _load_action_requests(root)
    m25_ia3 = upstream["M25_receipt"]["transactions"]["IA3"]
    m26_ia4 = upstream["M26_receipt"]["result"]
    content = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M28",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_NO_SIMULATOR_RUN",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_admitted": False,
        "source_bindings": _source_bindings(),
        "decision_lineage": {
            "IA3": {
                "source": "M25 deterministic real-adapter transaction",
                "qualification_id": upstream["M25_receipt"]["qualification_id"],
                "candidate_id": m25_ia3["selected_candidate_id"],
                "abstract_target_id": m25_ia3["selected_target"],
                "plan_id": m25_ia3["validation"]["plan_id"],
                "commands": m25_ia3["validation"]["commands"],
            },
            "IA4": {
                "source": "M26 live-model real-adapter decision",
                "receipt_id": upstream["M26_receipt"]["receipt_id"],
                "candidate_id": m26_ia4["selected_candidate_id"],
                "abstract_target_id": m26_ia4["selected_target"],
                "plan_id": m26_ia4["validation"]["plan_id"],
                "commands": m26_ia4["validation"]["commands"],
                "model_id": m26_ia4["model_record"]["id"],
            },
            "candidate_agreement_required": True,
            "agreed_candidate_id": EXPECTED_CANDIDATE_ID,
        },
        "translation": {
            "actor_visible_target": ABSTRACT_TARGET_ID,
            "runtime_target": TARGET_ID,
            "active_power_kw": COMMAND_KW,
            "reactive_power_kvar": 0.0,
            "strategy_id": "matched_step",
            "translation_is_fixed": True,
            "executor_may_modify_plan": False,
        },
        "runtime_design": {
            "actors": list(ACTORS),
            "treatments_per_actor": ["benign", "attack"],
            "runs": 4,
            "retry_cap": 0,
            "seed": SEED,
            "measurement_noise_seed": SEED + 90000,
            "partition_role": "attack_development",
            "operating_point": OPERATING_POINT,
            "windows": WINDOWS,
            "window_seconds": WINDOW_SECONDS,
            "perturbed_window_cap": 1,
            "apparent_energy_cap_kvah": 2.0,
            "expected_command_energy_kvah": COMMAND_KW * WINDOW_SECONDS / 3600.0,
            "container_image_tag": IMAGE_TAG,
            "container_image_id": IMAGE_ID,
            "network_mode": "none",
            "containers_ephemeral": True,
            "action_requests": requests,
        },
        "endpoints": {
            "decision_candidate_agreement": True,
            "candidate_to_runtime_translation_exact": True,
            "accepted_equals_delivered": True,
            "paired_causal_response_at_t30": True,
            "actor_blind_physical_trace_equality": True,
            "attacker_advantage_endpoint": False,
        },
        "access_boundary": {
            "simulator": True,
            "simulated_actuator": True,
            "new_LLM_inference": False,
            "embedding": False,
            "detector": False,
            "defense": False,
            "real_network": False,
            "physical_field_actuator": False,
            "final_evaluation": False,
            "evaluation_seeds": False,
            "resource_admission": False,
        },
        "claim_boundary": (
            "M28 qualifies point-specific decision-to-action wiring and exact "
            "actor-blind execution equivalence only. It does not establish an "
            "LLM advantage, adaptive strategy use, operating-point generality, "
            "population performance, safety, or confirmatory impact."
        ),
    }
    contract = _canonical_copy(content)
    contract["contract_id"] = "m28contract_" + _sha256_value(content)
    return contract


def register_artifacts(root: Path) -> dict[str, Any]:
    """Create the action requests and contract without simulator access."""

    root.mkdir(parents=True, exist_ok=True)
    for actor, requests in build_action_requests().items():
        for name, request in requests.items():
            create_once_json(root / "requests" / actor / name, request)
    contract = build_contract(root)
    create_once_json(root / "contract.json", contract)
    return contract


def _normalise_command(value: Any) -> dict[str, list[float]]:
    if not isinstance(value, Mapping):
        raise ValueError("command record is not an object")
    result: dict[str, list[float]] = {}
    for key, item in value.items():
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("command record is malformed")
        result[str(key)] = [float(item[0]), float(item[1])]
    return result


def _run_dir(root: Path, actor: str, treatment: str) -> Path:
    return root / "runs" / actor / treatment


def _physical_payload(run_dir: Path) -> dict[str, Any]:
    return {
        name: _strict_json_file(run_dir / name, f"M28 physical {name}")
        for name in (
            "attack_trace.json",
            "dual_budget_trace.json",
            "g7_summary.json",
            "multi_der_source.json",
            "multi_der_traces.json",
        )
    }


def _validate_run(root: Path, actor: str, treatment: str) -> dict[str, Any]:
    run_dir = _run_dir(root, actor, treatment)
    integration = _strict_json_file(
        run_dir / "runtime_integration.json", "M28 runtime integration"
    )
    attack_trace = _strict_json_file(run_dir / "attack_trace.json", "attack trace")
    dual = _strict_json_file(run_dir / "dual_budget_trace.json", "dual budget")
    if integration.get("status") != "passed":
        raise ValueError(f"M28 {actor}/{treatment} runtime did not pass")
    lineage = integration.get("seed_lineage", {})
    expected_lineage = {
        "partition": "attack_development",
        "replicate_seed": SEED,
        "attacker_policy_seed": SEED,
        "measurement_noise_seed": SEED + 90000,
        "gridlabd_random_seed": 10,
    }
    if lineage != expected_lineage:
        raise ValueError(f"M28 {actor}/{treatment} seed lineage drift")
    operating = integration.get("operating_point", {})
    if operating.get("id") != OPERATING_POINT or operating.get("duration_s") != 30:
        raise ValueError(f"M28 {actor}/{treatment} operating-point drift")
    pairing = integration.get("pairing", {})
    if (
        pairing.get("pair_id") != pair_id(actor)
        or pairing.get("treatment") != treatment
        or pairing.get("matched_seed") != SEED
    ):
        raise ValueError(f"M28 {actor}/{treatment} pairing drift")
    expected_request = build_action_requests()[actor][f"{treatment}_action_request.json"]
    if integration.get("M18_action_request") != expected_request:
        raise ValueError(f"M28 {actor}/{treatment} action request drift")
    if not isinstance(attack_trace, list) or len(attack_trace) != WINDOWS:
        raise ValueError(f"M28 {actor}/{treatment} attack trace length drift")
    commands = [_normalise_command(item.get("attack")) for item in attack_trace]
    if treatment == "benign":
        if commands != [{}, {}, {}]:
            raise ValueError(f"M28 {actor} benign command contamination")
        if dual.get("windows_spent") != 0 or dual.get("admitted_energy_kvah") != 0.0:
            raise ValueError(f"M28 {actor} benign budget drift")
    else:
        expected = [{TARGET_ID: [COMMAND_KW, 0.0]}, {}, {}]
        if commands != expected:
            raise ValueError(f"M28 {actor} attack command drift")
        if (
            dual.get("windows_spent") != 1
            or not math.isclose(
                float(dual.get("admitted_energy_kvah", -1)),
                COMMAND_KW * WINDOW_SECONDS / 3600.0,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            or dual.get("delivery_reconciled") is not True
        ):
            raise ValueError(f"M28 {actor} attack delivery drift")
    telemetry = [
        {key: float(value) for key, value in item["telemetry"].items()}
        for item in attack_trace
    ]
    return {
        "actor": actor,
        "treatment": treatment,
        "output_dir": _relative(run_dir),
        "action_id": expected_request["action_id"],
        "commands": commands,
        "telemetry": telemetry,
        "physical_payload_sha256": _sha256_value(_physical_payload(run_dir)),
        "delivery": integration.get("delivery"),
    }


def _manifest(root: Path, files: Iterable[Path]) -> dict[str, Any]:
    entries = []
    for path in sorted(set(files)):
        if path.is_symlink() or not path.is_file():
            continue
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return {
        "algorithm": "sha256",
        "file_count": len(entries),
        "total_bytes": sum(item["bytes"] for item in entries),
        "files": entries,
    }


def _verify_manifest(root: Path, manifest: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    entries = manifest.get("files")
    if manifest.get("algorithm") != "sha256" or not isinstance(entries, list):
        return ["manifest_shape_invalid"]
    total = 0
    seen: set[str] = set()
    for entry in entries:
        relative = str(entry.get("path", ""))
        if (
            not relative
            or relative in seen
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            issues.append("manifest_path_invalid_or_duplicate")
            continue
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.is_symlink():
            issues.append(f"manifest_file_missing:{relative}")
            continue
        size = path.stat().st_size
        total += size
        if entry.get("bytes") != size:
            issues.append(f"manifest_size_drift:{relative}")
        if entry.get("sha256") != _sha256_file(path):
            issues.append(f"manifest_sha256_drift:{relative}")
    if manifest.get("file_count") != len(entries):
        issues.append("manifest_file_count_drift")
    if manifest.get("total_bytes") != total:
        issues.append("manifest_total_bytes_drift")
    return sorted(set(issues))


def build_evidence(root: Path) -> dict[str, Any]:
    """Build the content-addressed M28 evidence after the four runs."""

    contract = _strict_json_file(root / "contract.json", "M28 contract")
    if contract != build_contract(root):
        raise ValueError("M28 stored contract drifts")
    execution = _strict_json_file(
        root / "runtime_execution.json", "M28 runtime execution"
    )
    if (
        execution.get("status") != "complete"
        or execution.get("issues") != []
        or execution.get("runs_completed") != 4
        or execution.get("retry_count") != 0
    ):
        raise ValueError("M28 runtime execution did not satisfy its cap")

    records = {
        actor: {
            treatment: _validate_run(root, actor, treatment)
            for treatment in ("benign", "attack")
        }
        for actor in ACTORS
    }
    deltas: dict[str, dict[str, float]] = {}
    for actor in ACTORS:
        benign = records[actor]["benign"]["telemetry"]
        attack = records[actor]["attack"]["telemetry"]
        for index in (0, 1):
            for device in benign[index]:
                if not math.isclose(
                    attack[index][device], benign[index][device],
                    rel_tol=0.0, abs_tol=1e-12,
                ):
                    raise ValueError(f"M28 {actor} has pre-t30 physical response")
        deltas[actor] = {
            device: attack[2][device] - benign[2][device]
            for device in benign[2]
        }
        if not any(abs(value) > 1e-12 for value in deltas[actor].values()):
            raise ValueError(f"M28 {actor} lacks a finite t30 response")

    physical_equality = {
        treatment: (
            _physical_payload(_run_dir(root, "IA3", treatment))
            == _physical_payload(_run_dir(root, "IA4", treatment))
        )
        for treatment in ("benign", "attack")
    }
    if physical_equality != {"benign": True, "attack": True}:
        raise ValueError("M28 actor-blind physical evidence differs")
    if deltas["IA3"] != deltas["IA4"]:
        raise ValueError("M28 actor paired causal deltas differ")

    evidence_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.name not in {
            "m28_decision_to_action.json",
            "independent_audit_receipt.json",
        }
    ]
    content = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M28",
        "classification": CLASSIFICATION,
        "status": "DECISION_TO_ACTION_WIRING_QUALIFIED",
        "contract_id": contract["contract_id"],
        "decision_lineage": contract["decision_lineage"],
        "translation": contract["translation"],
        "runtime_execution_sha256": _sha256_file(
            root / "runtime_execution.json"
        ),
        "run_records": records,
        "paired_t30_true_voltage_delta_pu": deltas,
        "max_abs_t30_true_voltage_delta_pu": max(
            abs(value) for value in deltas["IA3"].values()
        ),
        "actor_blind_physical_equality": physical_equality,
        "actor_paired_delta_equality": True,
        "primary_endpoints": {
            "decision_candidate_agreement": True,
            "candidate_to_runtime_translation_exact": True,
            "accepted_equals_delivered": True,
            "paired_causal_response_at_t30": True,
            "actor_blind_physical_trace_equality": True,
        },
        "manifest": _manifest(root, evidence_files),
        "access_boundary": {
            "simulator_accessed": True,
            "simulated_actuator_used": True,
            "new_LLM_inference_used": False,
            "embedding_accessed": False,
            "detector_accessed": False,
            "defense_accessed": False,
            "real_network_used": False,
            "physical_field_actuator_accessed": False,
            "final_evaluation_accessed": False,
            "final_evaluation_seeds_accessed": [],
            "resource_admitted": False,
        },
        "claim_boundary": contract["claim_boundary"],
    }
    evidence = _canonical_copy(content)
    evidence["evidence_id"] = "m28evidence_" + _sha256_value(content)
    return evidence


def verify_evidence(root: Path) -> list[str]:
    """Verify M28 contract, evidence, manifest, and primary endpoints."""

    issues: list[str] = []
    try:
        contract = _strict_json_file(root / "contract.json", "M28 contract")
        evidence = _strict_json_file(
            root / "m28_decision_to_action.json", "M28 evidence"
        )
        if contract != build_contract(root):
            issues.append("contract_drift")
        content = _canonical_copy(evidence)
        evidence_id = content.pop("evidence_id", None)
        if evidence_id != "m28evidence_" + _sha256_value(content):
            issues.append("evidence_content_address_drift")
        if evidence.get("contract_id") != contract.get("contract_id"):
            issues.append("evidence_contract_id_drift")
        issues.extend(_verify_manifest(root, evidence.get("manifest", {})))
        if evidence.get("status") != "DECISION_TO_ACTION_WIRING_QUALIFIED":
            issues.append("evidence_status_drift")
        expected_endpoints = {
            "decision_candidate_agreement": True,
            "candidate_to_runtime_translation_exact": True,
            "accepted_equals_delivered": True,
            "paired_causal_response_at_t30": True,
            "actor_blind_physical_trace_equality": True,
        }
        if evidence.get("primary_endpoints") != expected_endpoints:
            issues.append("primary_endpoint_drift")
        if evidence.get("actor_blind_physical_equality") != {
            "benign": True,
            "attack": True,
        }:
            issues.append("actor_blind_physical_equality_failed")
        if evidence.get("actor_paired_delta_equality") is not True:
            issues.append("actor_paired_delta_equality_failed")
        boundary = evidence.get("access_boundary", {})
        if boundary.get("simulator_accessed") is not True:
            issues.append("simulator_access_state_drift")
        for field in (
            "new_LLM_inference_used",
            "embedding_accessed",
            "detector_accessed",
            "defense_accessed",
            "real_network_used",
            "physical_field_actuator_accessed",
            "final_evaluation_accessed",
            "resource_admitted",
        ):
            if boundary.get(field) is not False:
                issues.append(f"access_boundary_drift:{field}")
        if boundary.get("final_evaluation_seeds_accessed") != []:
            issues.append("final_evaluation_seed_access")
        rebuilt = build_evidence(root)
        for field in (
            "decision_lineage",
            "translation",
            "runtime_execution_sha256",
            "run_records",
            "paired_t30_true_voltage_delta_pu",
            "max_abs_t30_true_voltage_delta_pu",
            "actor_blind_physical_equality",
            "actor_paired_delta_equality",
            "primary_endpoints",
            "manifest",
        ):
            if evidence.get(field) != rebuilt.get(field):
                issues.append(f"rebuilt_evidence_drift:{field}")
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        issues.append(f"M28_evidence_unreadable_or_invalid:{exc}")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["register", "build", "verify"])
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_relative_to(PACKAGE_ROOT):
        raise ValueError("M28 artifacts must remain under g7_confirmatory")
    if args.mode == "register":
        result = register_artifacts(root)
        output = {"status": "registered", "contract_id": result["contract_id"]}
    elif args.mode == "build":
        result = build_evidence(root)
        create_once_json(root / "m28_decision_to_action.json", result)
        output = {"status": result["status"], "evidence_id": result["evidence_id"]}
    else:
        issues = verify_evidence(root)
        output = {"status": "passed" if not issues else "failed", "issues": issues}
    print(json.dumps(output, indent=2, sort_keys=True))
    return int(output["status"] in {"failed"})


if __name__ == "__main__":
    raise SystemExit(main())

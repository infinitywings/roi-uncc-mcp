"""Command-line entry points for the non-destructive Phase 0–1 harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .campaign import expand_profile
from .career_review_receipts import (
    READY_FOR_GOVERNANCE,
    SYNTHETIC_PASS,
    evaluate_review_receipts,
    load_review_receipt,
)
from .career_reviewer_handoff import (
    M14_CHECKPOINT_ID,
    build_reviewer_handoff_contract,
    verify_checked_in_handoff,
)
from .career_two_tier_gate import (
    DEFERRED_EXTERNAL_CHECKPOINT_ID,
    SEALED_ACTIONS,
    build_career_two_tier_gate,
    verify_checked_in_two_tier_gate,
)
from .career_internal_advisory import (
    load_career_internal_advisory,
    verify_checked_in_internal_advisory,
)
from .career_trial_matrix import (
    build_career_trial_matrix,
    verify_checked_in_trial_matrix,
)
from .preliminary_only_gate import (
    build_preliminary_only_gate,
    verify_checked_in_preliminary_gate,
)
from .detector_freeze import (
    build_benign_calibration_plan,
    build_detector_provenance_audit,
)
from .manifest import build_manifest, create_once_json
from .ia4_model import IA4ModelReplay, perform_bounded_model_smoke
from .ia4_interactive_model import (
    M6_SMOKE_SCHEMA_VERSION,
    build_default_m6_overlay,
    perform_bounded_interactive_model_smoke,
)
from .ia4_counterfactual import (
    M7_SMOKE_SCHEMA_VERSION,
    M7ModelOverlay,
    build_default_m7_overlay,
    build_m7_contract_artifact,
    perform_m7_counterfactual_model_smoke,
    validate_m7_contract_artifact,
)
from .ia4_smoke_fixture import build_m4_smoke_adapter
from .ia4_tool_loop import build_m5_contract_artifact
from .model_client import ModelClientError, request_proposal
from .orchestration_contract import ContractViolation, TypedObservation
from .prompt_audit import load_prompt, prompt_sha256, render_messages
from .pairing import build_paired_development_plan
from .partitions import gridlabd_random_seed
from .spec import load_spec, spec_sha256


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def cmd_validate(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    _print({
        "status": "valid",
        "protocol_id": spec["protocol_id"],
        "campaign_authorized": spec["campaign_authorized"],
        "spec_sha256": spec_sha256(spec),
        "outer_budget_k": spec["search"]["outer_budget_k"],
        "search_arms": spec["search"]["arms"],
    })
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    plan = expand_profile(spec, args.profile)
    create_once_json(args.output, plan)
    _print({"status": "created", "output": str(args.output), "runs": len(plan["runs"]),
            "executable": plan["executable"]})
    return 0


def cmd_model_smoke(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    prompt = load_prompt(args.prompt)
    space = spec["candidate_space"]
    primary = spec["budgets"]["primary"]
    messages = render_messages(
        prompt,
        amplitudes=list(map(float, space["amplitude_fractions"])),
        periods=list(map(int, space["period_windows"])),
        window_cap=int(primary["perturbed_windows"]),
        energy_cap=float(primary["apparent_energy_kvah"]),
    )
    artifact = {
        "schema_version": "grideval-g7-model-smoke/v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": spec["protocol_id"],
        "spec_sha256": spec_sha256(spec),
        "prompt_id": prompt["prompt_id"],
        "prompt_sha256": prompt_sha256(prompt),
        "endpoint": spec["model"]["base_url"],
        "expected_model_id": spec["model"]["id"],
        "scope": "one_proposal_no_cosimulation",
    }
    exit_code = 0
    try:
        result = request_proposal(
            base_url=spec["model"]["base_url"],
            model_id=spec["model"]["id"],
            messages=messages,
            amplitudes=list(map(float, space["amplitude_fractions"])),
            periods=list(map(int, space["period_windows"])),
            temperature=float(spec["model"]["temperature"]),
            max_tokens=int(spec["model"]["max_tokens"]),
            timeout_s=float(spec["model"]["timeout_s"]),
            seed=int(spec["partitions"]["development"][0]),
        )
        artifact.update({"status": "passed", **result})
    except ModelClientError as exc:
        artifact.update({"status": "failed_closed", "error": str(exc)})
        exit_code = 2
    create_once_json(args.output, artifact)
    _print({"status": artifact["status"], "output": str(args.output)})
    return exit_code


def cmd_ia4_model_smoke(args: argparse.Namespace) -> int:
    """Run one model-only IA4 parsing smoke with no tool or simulator access."""

    spec = load_spec(args.spec)
    adapter = build_m4_smoke_adapter()
    development_seeds = tuple(map(int, spec["partitions"]["development"]))
    replay = IA4ModelReplay(
        adapter=adapter,
        allowed_development_seeds=development_seeds,
    )
    artifact = {
        "schema_version": "grideval-g7-ia4-model-smoke/v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": spec["protocol_id"],
        "project_id": "prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
        "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        "spec_file_sha256": hashlib.sha256(args.spec.read_bytes()).hexdigest(),
        "endpoint": spec["model"]["base_url"],
        "expected_model_id": spec["model"]["id"],
        "search_surface_id": adapter.search_surface.search_surface_id,
        "scope": "synthetic_interface_model_output_parsing_only",
        "development_only": True,
        "campaign_authorized": False,
        "evaluation_sealed": True,
        "tool_execution_authorized": False,
        "simulator_accessed": False,
        "detector_accessed": False,
        "embedding_accessed": False,
    }
    exit_code = 0
    try:
        result = perform_bounded_model_smoke(
            replay,
            base_url=spec["model"]["base_url"],
            model_id=spec["model"]["id"],
            observation=TypedObservation(
                window=0,
                time_s=0,
                values={
                    "context": "synthetic_interface_fixture",
                    "prior_alarm": False,
                    "voltage_pu": 1.0,
                },
            ),
            history=(),
            temperature=0.0,
            max_tokens=min(512, int(spec["model"]["max_tokens"])),
            timeout_s=float(spec["model"]["timeout_s"]),
            seed=development_seeds[0],
        )
        artifact.update({"status": "passed", **result})
    except (ModelClientError, ContractViolation) as exc:
        artifact.update({"status": "failed_closed", "error": str(exc)})
        exit_code = 2
    create_once_json(args.output, artifact)
    _print({"status": artifact["status"], "output": str(args.output)})
    return exit_code


def cmd_ia4_interactive_fixture(args: argparse.Namespace) -> int:
    """Create the offline M5 state-machine and matched-control receipt."""

    load_spec(args.spec)
    artifact = build_m5_contract_artifact(
        adapter=build_m4_smoke_adapter(),
        spec_file_sha256=hashlib.sha256(args.spec.read_bytes()).hexdigest(),
    )
    create_once_json(args.output, artifact)
    _print({
        "status": artifact["status"],
        "output": str(args.output),
        "protocol_id": artifact["protocol"]["protocol_id"],
    })
    return 0


def cmd_ia4_interactive_model_smoke(args: argparse.Namespace) -> int:
    """Run the bounded M6 two-turn model/read-only-fixture qualification."""

    spec = load_spec(args.spec)
    overlay = build_default_m6_overlay(
        model_id=spec["model"]["id"],
        development_seeds=spec["partitions"]["development"],
        timeout_s=float(spec["model"]["timeout_s"]),
    )
    artifact = {
        "schema_version": M6_SMOKE_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": spec["protocol_id"],
        "project_id": "prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
        "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        "spec_file_sha256": hashlib.sha256(args.spec.read_bytes()).hexdigest(),
        "endpoint": spec["model"]["base_url"],
        "expected_model_id": spec["model"]["id"],
        "scope": "synthetic_read_only_fixture_interactive_model_qualification",
        "development_only": True,
        "campaign_authorized": False,
        "evaluation_sealed": True,
        "model_transport_authorized": True,
        "tool_execution_authorized": False,
        "simulator_access_authorized": False,
        "detector_access_authorized": False,
        "embedding_access_authorized": False,
        "overlay": overlay.to_dict(),
    }
    result = perform_bounded_interactive_model_smoke(
        base_url=spec["model"]["base_url"],
        overlay=overlay,
    )
    artifact.update(result)
    create_once_json(args.output, artifact)
    _print({
        "status": artifact["status"],
        "output": str(args.output),
        "completion_requests": artifact["completion_requests"],
        "terminal_state": (
            artifact["session_receipt"]["state"]
            if artifact["session_receipt"] else None
        ),
    })
    return 0 if artifact["status"] == "passed" else 2


def _m7_overlay(spec: dict) -> M7ModelOverlay:
    development = tuple(map(int, spec["partitions"]["development"]))
    if len(development) < 4:
        raise ValueError("M7 requires development seeds 8103 and 8104")
    return build_default_m7_overlay(
        model_id=spec["model"]["id"],
        development_seeds=development[2:4],
        timeout_s=float(spec["model"]["timeout_s"]),
    )


def cmd_ia4_counterfactual_contract(args: argparse.Namespace) -> int:
    """Create the offline M7 preregistration before any model transport."""

    spec = load_spec(args.spec)
    overlay = _m7_overlay(spec)
    artifact = build_m7_contract_artifact(
        overlay=overlay,
        spec_file_sha256=hashlib.sha256(args.spec.read_bytes()).hexdigest(),
    )
    create_once_json(args.output, artifact)
    _print({
        "status": "created",
        "output": str(args.output),
        "contract_id": artifact["contract_id"],
        "model_requests": 0,
        "real_tool_executions": 0,
    })
    return 0


def cmd_ia4_counterfactual_model_smoke(args: argparse.Namespace) -> int:
    """Run the bounded M7 paired counterfactual model qualification."""

    spec = load_spec(args.spec)
    overlay = _m7_overlay(spec)
    spec_file_sha256 = hashlib.sha256(args.spec.read_bytes()).hexdigest()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    validate_m7_contract_artifact(
        artifact=contract,
        overlay=overlay,
        spec_file_sha256=spec_file_sha256,
    )
    artifact = {
        "schema_version": M7_SMOKE_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": spec["protocol_id"],
        "project_id": "prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
        "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        "spec_file_sha256": spec_file_sha256,
        "contract_id": contract["contract_id"],
        "endpoint": spec["model"]["base_url"],
        "expected_model_id": spec["model"]["id"],
        "scope": "synthetic_paired_counterfactual_causal_tool_use_qualification",
        "development_only": True,
        "campaign_authorized": False,
        "evaluation_sealed": True,
        "model_transport_authorized": True,
        "tool_execution_authorized": False,
        "simulator_access_authorized": False,
        "detector_access_authorized": False,
        "embedding_access_authorized": False,
        "overlay": overlay.to_dict(),
    }
    artifact.update(perform_m7_counterfactual_model_smoke(
        base_url=spec["model"]["base_url"],
        overlay=overlay,
    ))
    create_once_json(args.output, artifact)
    _print({
        "status": artifact["status"],
        "output": str(args.output),
        "completion_requests": artifact["completion_requests"],
        "qualification": artifact["qualification"],
    })
    return 0 if artifact["status"] == "passed" else 2


def cmd_manifest(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    files = [root / path for path in args.files]
    manifest = build_manifest(root=root, files=files, metadata={
        "protocol_id": args.protocol_id,
        "phase": args.phase,
        "campaign_authorized": False,
        **({"mission_id": args.mission_id} if args.mission_id else {}),
        **({"decision_id": args.decision_id} if args.decision_id else {}),
    })
    create_once_json(args.output, manifest)
    _print({"status": "created", "output": str(args.output), "files": len(files)})
    return 0


def cmd_detector_audit(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    artifact = build_detector_provenance_audit(
        spec,
        repo_root=args.repo_root,
        mission_id=args.mission_id,
        decision_id=args.decision_id,
    )
    create_once_json(args.output, artifact)
    _print({
        "status": "created",
        "output": str(args.output),
        "detector_package_id": artifact["detector_package_id"],
        "readiness": artifact["readiness"],
    })
    return 0


def _load_detector_audit(path: Path, spec: dict) -> dict:
    audit = json.loads(path.read_text(encoding="utf-8"))
    if audit.get("schema_version") != "grideval-g7-detector-provenance-audit/v1":
        raise ValueError("unsupported detector audit schema")
    if audit.get("protocol_id") != spec["protocol_id"]:
        raise ValueError("detector audit protocol drift")
    if audit.get("spec_sha256") != spec_sha256(spec):
        raise ValueError("detector audit spec hash drift")
    if audit.get("evaluation_opened") is not False:
        raise ValueError("detector audit has opened evaluation")
    return audit


def _audit_dependencies(audit: dict) -> dict[str, str]:
    selected_suffixes = (
        "detector_g7.py",
        "sensitivity_g7.json",
        "run_multi_der_loop.py",
        "examples/2bus-13bus/1c_IEEE_123_feeder.glm",
        "v3/configs/der_devices.yaml",
    )
    result = {
        item["path"]: item["sha256"]
        for item in audit["inventory"]
        if item["path"].endswith(selected_suffixes)
    }
    if len(result) != len(selected_suffixes):
        raise ValueError("detector audit is missing a controlled dependency")
    return result


def cmd_calibration_plan(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    audit = _load_detector_audit(args.detector_audit, spec)
    source_glm = args.repo_root / "examples/2bus-13bus/1c_IEEE_123_feeder.glm"
    plan = build_benign_calibration_plan(
        spec,
        dependency_hashes=_audit_dependencies(audit),
        gridlabd_seed=gridlabd_random_seed(source_glm),
    )
    create_once_json(args.output, plan)
    _print({"status": "created", "output": str(args.output),
            "runs": plan["run_count"], "executable": plan["executable"]})
    return 0


def cmd_paired_plan(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    audit = _load_detector_audit(args.detector_audit, spec)
    source_glm = args.repo_root / "examples/2bus-13bus/1c_IEEE_123_feeder.glm"
    plan = build_paired_development_plan(
        spec,
        args.profile,
        dependency_hashes=_audit_dependencies(audit),
        detector_package_id=audit["detector_package_id"],
        gridlabd_seed=gridlabd_random_seed(source_glm),
    )
    create_once_json(args.output, plan)
    _print({"status": "created", "output": str(args.output),
            "pairs": plan["pair_count"], "executable": plan["executable"]})
    return 0


def _closed_review_authorization() -> dict[str, bool]:
    return {
        "source_generation": False,
        "partition_assignment": False,
        "threshold_selection": False,
        "resource_admission": False,
        "model_or_embedding_access": False,
        "tool_simulator_detector_or_actuator_access": False,
        "evaluation_access": False,
        "campaign": False,
    }


def cmd_career_review_preflight(args: argparse.Namespace) -> int:
    """Read and verify the exact M14B handoff without modifying anything."""

    issues = verify_checked_in_handoff(args.repo_root)
    handoff = build_reviewer_handoff_contract()
    status = (
        handoff["status"] if not issues else "FAILED_CLOSED_NOT_APPROVED"
    )
    _print({
        "status": status,
        "handoff_id": handoff["handoff_id"],
        "support_files": len(handoff["support_snapshot"]),
        "worksheets": len(handoff["worksheets"]),
        "issues": issues,
        "checkpoint_id": M14_CHECKPOINT_ID,
        "checkpoint_status": "OPEN_REQUIRES_EXTERNAL_RESOLUTION",
        "authorization": _closed_review_authorization(),
        "files_created_or_modified": 0,
        "RKA_writes": 0,
    })
    return 0 if not issues else 2


def cmd_career_review_receipt(args: argparse.Namespace) -> int:
    """Read and validate one externally supplied receipt declaration."""

    receipt = load_review_receipt(args.receipt).to_dict()
    _print({
        "status": "VALID_RECEIPT_DECLARATION_NOT_APPROVED",
        "receipt_id": receipt["receipt_id"],
        "artifact_class": receipt["artifact_class"],
        "reviewer_role": receipt["reviewer"]["reviewer_role"],
        "disposition": receipt["review"]["disposition"],
        "checkpoint_id": M14_CHECKPOINT_ID,
        "checkpoint_status": "OPEN_REQUIRES_EXTERNAL_RESOLUTION",
        "authorization": _closed_review_authorization(),
        "files_created_or_modified": 0,
        "RKA_writes": 0,
    })
    return 0


def cmd_career_review_bundle(args: argparse.Namespace) -> int:
    """Read and evaluate receipt declarations without resolving the gate."""

    payloads = [
        json.loads(path.read_text(encoding="utf-8")) for path in args.receipt
    ]
    result = evaluate_review_receipts(payloads).to_dict()
    result["files_created_or_modified"] = 0
    result["RKA_writes"] = 0
    _print(result)
    return 0 if result["status"] in {
        SYNTHETIC_PASS,
        READY_FOR_GOVERNANCE,
    } else 2


def cmd_career_development_gate(args: argparse.Namespace) -> int:
    """Verify the M15 offline-development boundary without writing anything."""

    issues = verify_checked_in_two_tier_gate(args.repo_root)
    gate = build_career_two_tier_gate().to_dict()
    _print({
        "status": gate["status"] if not issues else "FAILED_CLOSED",
        "gate_id": gate["gate_id"],
        "deferred_external_checkpoint_id": DEFERRED_EXTERNAL_CHECKPOINT_ID,
        "external_review_complete": False,
        "offline_permissions": gate["offline_permissions"],
        "sealed_actions": gate["sealed_actions"],
        "issues": issues,
        "files_created_or_modified": 0,
        "RKA_writes": 0,
    })
    return 0 if not issues else 2


def cmd_career_advisory_preflight(args: argparse.Namespace) -> int:
    """Verify M16 model evidence and Brain adjudication without writes."""

    issues = verify_checked_in_internal_advisory(args.repo_root)
    path = (
        args.repo_root
        / "v3/g7_confirmatory/artifacts/career_internal_advisory_m16.json"
    )
    advisory = load_career_internal_advisory(path).to_dict()
    _print({
        "status": advisory["status"] if not issues else "FAILED_CLOSED",
        "advisory_id": advisory["advisory_id"],
        "model_id": advisory["transport"]["model_record"]["id"],
        "model_completions_attempted": advisory["transport"]
        ["model_completions_attempted"],
        "accepted_completions": advisory["transport"]["accepted_completions"],
        "adjudication": {
            finding_id: item["disposition"]
            for finding_id, item in advisory["brain_adjudication"].items()
        },
        "external_review_complete": False,
        "sealed_actions": {
            key: advisory["governance"][key]
            for key in SEALED_ACTIONS
        },
        "issues": issues,
        "files_created_or_modified": 0,
        "RKA_writes": 0,
    })
    return 0 if not issues else 2


def cmd_career_trial_matrix_preflight(args: argparse.Namespace) -> int:
    """Verify the M17 non-executable trial matrix without writes."""

    issues = verify_checked_in_trial_matrix(args.repo_root)
    matrix = build_career_trial_matrix().to_dict()
    _print({
        "status": matrix["status"] if not issues else "FAILED_CLOSED",
        "matrix_id": matrix["matrix_id"],
        "executable": matrix["executable"],
        "scope_tracks": [item["id"] for item in matrix["scope_tracks"]],
        "capability_ladder": [
            item["id"] for item in matrix["capability_ladder"]
        ],
        "strategy_families": [
            item["id"] for item in matrix["strategy_families"]
        ],
        "knowledge_profiles": [
            item["id"] for item in matrix["knowledge_contract"]["profiles"]
        ],
        "next_gate": matrix["next_gate"],
        "final_evaluation_sealed": matrix["governance"]
        ["final_evaluation_and_confirmatory_campaign_sealed"],
        "issues": issues,
        "files_created_or_modified": 0,
        "RKA_writes": 0,
    })
    return 0 if not issues else 2


def cmd_preliminary_only_preflight(args: argparse.Namespace) -> int:
    """Verify the M18 preliminary-only boundary without executing it."""

    issues = verify_checked_in_preliminary_gate(args.repo_root)
    gate = build_preliminary_only_gate().to_dict()
    _print({
        "status": gate["status"] if not issues else "FAILED_CLOSED",
        "gate_id": gate["gate_id"],
        "executes_actions": gate["executes_actions"],
        "preliminary_partitions": [
            item["role"]
            for item in gate["partition_registry"]
            if item["classification"] == "PRELIMINARY_ONLY"
        ],
        "sealed_partition": next(
            item["role"]
            for item in gate["partition_registry"]
            if item["classification"] == "FINAL_SEALED"
        ),
        "preliminary_permissions": gate["preliminary_permissions"],
        "final_seals": gate["final_seals"],
        "next_action": gate["next_action"],
        "issues": issues,
        "files_created_or_modified": 0,
        "RKA_writes": 0,
    })
    return 0 if not issues else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-spec")
    validate.add_argument("--spec", required=True, type=Path)
    validate.set_defaults(func=cmd_validate)

    plan = sub.add_parser("plan")
    plan.add_argument("--spec", required=True, type=Path)
    plan.add_argument("--profile", required=True)
    plan.add_argument("--output", required=True, type=Path)
    plan.set_defaults(func=cmd_plan)

    smoke = sub.add_parser("model-smoke")
    smoke.add_argument("--spec", required=True, type=Path)
    smoke.add_argument("--prompt", required=True, type=Path)
    smoke.add_argument("--output", required=True, type=Path)
    smoke.set_defaults(func=cmd_model_smoke)

    ia4_smoke = sub.add_parser("ia4-model-smoke")
    ia4_smoke.add_argument("--spec", required=True, type=Path)
    ia4_smoke.add_argument("--output", required=True, type=Path)
    ia4_smoke.set_defaults(func=cmd_ia4_model_smoke)

    ia4_fixture = sub.add_parser("ia4-interactive-fixture")
    ia4_fixture.add_argument("--spec", required=True, type=Path)
    ia4_fixture.add_argument("--output", required=True, type=Path)
    ia4_fixture.set_defaults(func=cmd_ia4_interactive_fixture)

    ia4_interactive_model = sub.add_parser("ia4-interactive-model-smoke")
    ia4_interactive_model.add_argument("--spec", required=True, type=Path)
    ia4_interactive_model.add_argument("--output", required=True, type=Path)
    ia4_interactive_model.set_defaults(func=cmd_ia4_interactive_model_smoke)

    ia4_counterfactual_contract = sub.add_parser(
        "ia4-counterfactual-contract"
    )
    ia4_counterfactual_contract.add_argument("--spec", required=True, type=Path)
    ia4_counterfactual_contract.add_argument("--output", required=True, type=Path)
    ia4_counterfactual_contract.set_defaults(
        func=cmd_ia4_counterfactual_contract
    )

    ia4_counterfactual_model = sub.add_parser(
        "ia4-counterfactual-model-smoke"
    )
    ia4_counterfactual_model.add_argument("--spec", required=True, type=Path)
    ia4_counterfactual_model.add_argument(
        "--contract", required=True, type=Path
    )
    ia4_counterfactual_model.add_argument("--output", required=True, type=Path)
    ia4_counterfactual_model.set_defaults(
        func=cmd_ia4_counterfactual_model_smoke
    )

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--root", required=True, type=Path)
    manifest.add_argument("--output", required=True, type=Path)
    manifest.add_argument("--protocol-id", required=True)
    manifest.add_argument("--phase", default="phase0_phase1_harness")
    manifest.add_argument("--mission-id")
    manifest.add_argument("--decision-id")
    manifest.add_argument("files", nargs="+")
    manifest.set_defaults(func=cmd_manifest)

    detector_audit = sub.add_parser("detector-audit")
    detector_audit.add_argument("--spec", required=True, type=Path)
    detector_audit.add_argument("--repo-root", required=True, type=Path)
    detector_audit.add_argument("--mission-id", required=True)
    detector_audit.add_argument("--decision-id", required=True)
    detector_audit.add_argument("--output", required=True, type=Path)
    detector_audit.set_defaults(func=cmd_detector_audit)

    calibration_plan = sub.add_parser("calibration-plan")
    calibration_plan.add_argument("--spec", required=True, type=Path)
    calibration_plan.add_argument("--repo-root", required=True, type=Path)
    calibration_plan.add_argument("--detector-audit", required=True, type=Path)
    calibration_plan.add_argument("--output", required=True, type=Path)
    calibration_plan.set_defaults(func=cmd_calibration_plan)

    paired_plan = sub.add_parser("paired-plan")
    paired_plan.add_argument("--spec", required=True, type=Path)
    paired_plan.add_argument("--repo-root", required=True, type=Path)
    paired_plan.add_argument("--detector-audit", required=True, type=Path)
    paired_plan.add_argument("--profile", required=True)
    paired_plan.add_argument("--output", required=True, type=Path)
    paired_plan.set_defaults(func=cmd_paired_plan)

    review_preflight = sub.add_parser("career-review-preflight")
    review_preflight.add_argument("--repo-root", required=True, type=Path)
    review_preflight.set_defaults(func=cmd_career_review_preflight)

    review_receipt = sub.add_parser("career-review-receipt")
    review_receipt.add_argument("--receipt", required=True, type=Path)
    review_receipt.set_defaults(func=cmd_career_review_receipt)

    review_bundle = sub.add_parser("career-review-bundle")
    review_bundle.add_argument(
        "--receipt", required=True, action="append", type=Path
    )
    review_bundle.set_defaults(func=cmd_career_review_bundle)

    development_gate = sub.add_parser("career-development-gate")
    development_gate.add_argument("--repo-root", required=True, type=Path)
    development_gate.set_defaults(func=cmd_career_development_gate)

    advisory_preflight = sub.add_parser("career-advisory-preflight")
    advisory_preflight.add_argument("--repo-root", required=True, type=Path)
    advisory_preflight.set_defaults(func=cmd_career_advisory_preflight)

    trial_matrix_preflight = sub.add_parser("career-trial-matrix-preflight")
    trial_matrix_preflight.add_argument(
        "--repo-root", required=True, type=Path
    )
    trial_matrix_preflight.set_defaults(func=cmd_career_trial_matrix_preflight)

    preliminary_only_preflight = sub.add_parser(
        "preliminary-only-preflight"
    )
    preliminary_only_preflight.add_argument(
        "--repo-root", required=True, type=Path
    )
    preliminary_only_preflight.set_defaults(func=cmd_preliminary_only_preflight)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Command-line entry points for the non-destructive Phase 0–1 harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .campaign import expand_profile
from .detector_freeze import (
    build_benign_calibration_plan,
    build_detector_provenance_audit,
)
from .manifest import build_manifest, create_once_json
from .ia4_model import IA4ModelReplay, perform_bounded_model_smoke
from .ia4_smoke_fixture import build_m4_smoke_adapter
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

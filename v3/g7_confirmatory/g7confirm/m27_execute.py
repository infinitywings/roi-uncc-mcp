"""Execute the preregistered M27 cells in ephemeral network-isolated containers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Any

from .m19_qualification import _load_json
from .m27_profiles import M27_CELLS, cell_id, pair_id, treatment_definitions
from .m27_repeatability_coverage import (
    CLASSIFICATION,
    IMAGE_ID,
    IMAGE_TAG,
    PACKAGE_ROOT,
    REPO_ROOT,
    build_contract,
)
from .manifest import create_once_json


EXECUTION_SCHEMA_VERSION = "grideval-g7-m27-runtime-execution/v1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _container_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ValueError(f"M27 path escapes repository: {resolved}")
    return "/work/" + resolved.relative_to(REPO_ROOT).as_posix()


def _run_container(
    *, root: Path, seed: int, operating_point: str, treatment: dict[str, Any],
) -> dict[str, Any]:
    identifier = cell_id(seed, operating_point)
    name = f"g7-m27-{seed}-{operating_point.replace('_', '-')}-{treatment['id'].replace('_', '-')}-a1"
    output_dir = root / "cells" / identifier / treatment["id"]
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite M27 run: {output_dir}")
    request_path = root / "requests" / identifier / treatment["action_request"]
    common = [
        "python3", "-m", "g7confirm.m27_runtime",
        "--operating-point", operating_point,
        "--windows", "3",
        "--coupling-step", "10",
        "--attacker-seed", str(seed),
        "--noise-seed", str(seed + 90000),
        "--preliminary-role", "system_identification",
        "--pair-id", pair_id(seed, operating_point),
        "--action-request", _container_path(request_path),
        "--output-dir", _container_path(output_dir),
    ]
    if treatment["id"] == "benign":
        common.extend(["--arm", "benign", "--budget-windows", "0", "--energy-cap-kvah", "0"])
    else:
        common.extend([
            "--arm", "probe",
            "--probe-id", str(treatment["target_id"]),
            "--probe-kw", str(treatment["command_kw"]),
            "--budget-windows", "1",
            "--energy-cap-kvah", "2",
        ])
    inner = "PYTHONPATH=/work/v3/g7_confirmatory " + " ".join(shlex.quote(item) for item in common)
    command = [
        "docker", "run",
        "--name", name,
        "--network", "none",
        "--rm",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--entrypoint", "/bin/bash",
        "-v", f"{REPO_ROOT}:/work",
        "-w", "/work",
        IMAGE_TAG,
        "-lc", inner,
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = output_dir / "console.stdout.txt"
    stderr_path = output_dir / "console.stderr.txt"
    if stdout_path.exists() or stderr_path.exists():
        raise FileExistsError(f"M27 console evidence already exists: {output_dir}")
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    teardown = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    teardown_names = teardown.stdout.decode("utf-8", errors="replace").splitlines()
    return {
        "cell_id": identifier,
        "seed": seed,
        "operating_point": operating_point,
        "treatment": treatment["id"],
        "action_id": treatment["action_id"],
        "container_name": name,
        "container_exit_code": completed.returncode,
        "stdout_sha256": _sha256_bytes(completed.stdout),
        "stderr_sha256": _sha256_bytes(completed.stderr),
        "teardown_query_exit_code": teardown.returncode,
        "teardown_remaining_names": teardown_names,
        "teardown_verified": teardown.returncode == 0 and teardown_names == [],
        "retry_count": 0,
    }


def execute(root: Path) -> dict[str, Any]:
    """Execute all 30 preregistered runs once and retain every result."""

    root = root.resolve()
    if not root.is_relative_to(PACKAGE_ROOT):
        raise ValueError("M27 output must remain under g7_confirmatory")
    contract_path = root / "contract.json"
    if not contract_path.is_file() or _load_json(contract_path) != build_contract(root):
        raise ValueError("M27 execution requires the exact final-code contract")
    if (root / "runtime_execution.json").exists() or (root / "cells").exists():
        raise FileExistsError("refusing to overwrite an M27 runtime attempt")
    image = subprocess.run(
        ["docker", "image", "inspect", IMAGE_TAG, "--format", "{{.Id}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    image_id = image.stdout.decode("utf-8", errors="replace").strip()
    if image.returncode != 0 or image_id != IMAGE_ID:
        raise ValueError(f"M27 image identity drift: {image_id or image.stderr.decode(errors='replace')}")
    runs: list[dict[str, Any]] = []
    issues: list[str] = []
    for cell in M27_CELLS:
        seed = int(cell["seed"])
        operating_point = str(cell["operating_point"])
        for treatment in treatment_definitions(seed, operating_point):
            record = _run_container(
                root=root,
                seed=seed,
                operating_point=operating_point,
                treatment=treatment,
            )
            runs.append(record)
            if record["container_exit_code"] != 0:
                issues.append(f"container_failed:{record['container_name']}")
            if not record["teardown_verified"]:
                issues.append(f"container_teardown_failed:{record['container_name']}")
            if issues:
                break
        if issues:
            break
    execution = {
        "schema_version": EXECUTION_SCHEMA_VERSION,
        "classification": CLASSIFICATION,
        "status": "complete" if not issues and len(runs) == 30 else "failed_closed",
        "issues": issues,
        "contract_id": _load_json(contract_path)["contract_id"],
        "container_image_tag": IMAGE_TAG,
        "container_image_id": IMAGE_ID,
        "network_mode": "none",
        "physical_field_connection": False,
        "container_user": f"{os.getuid()}:{os.getgid()}",
        "entrypoint_override": "/bin/bash",
        "new_cell_cap": 6,
        "new_runtime_run_cap": 30,
        "runs_completed": len(runs),
        "runs": runs,
        "retry_count": 0,
        "containers_ephemeral": True,
        "teardown_verified": bool(runs) and all(item["teardown_verified"] for item in runs),
        "regular_evidence_files_retained": True,
        "final_evaluation_data_accessed": False,
        "model_or_embedding_inference_used": False,
        "model_or_embedding_service_started_or_restarted": False,
        "detector_or_defense_used": False,
        "real_network_used": False,
    }
    create_once_json(root / "runtime_execution.json", execution)
    return execution


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = execute(args.root)
    print(json.dumps({
        "status": result["status"],
        "runs_completed": result["runs_completed"],
        "issues": result["issues"],
    }, indent=2))
    return int(result["status"] != "complete")


if __name__ == "__main__":
    raise SystemExit(main())

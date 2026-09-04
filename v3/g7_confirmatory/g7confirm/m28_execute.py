"""Execute the four preregistered M28 traces in isolated containers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Any

from .m28_decision_to_action import (
    CLASSIFICATION,
    COMMAND_KW,
    IMAGE_ID,
    IMAGE_TAG,
    OPERATING_POINT,
    PACKAGE_ROOT,
    REPO_ROOT,
    SEED,
    TARGET_ID,
    build_contract,
)
from .m28_runtime import ACTORS, pair_id
from .manifest import create_once_json


EXECUTION_SCHEMA_VERSION = "grideval-g7-m28-runtime-execution/v1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _container_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ValueError(f"M28 path escapes repository: {resolved}")
    return "/work/" + resolved.relative_to(REPO_ROOT).as_posix()


def _remove_container_only_links(output_dir: Path) -> list[dict[str, str]]:
    """Remove only broken /work/examples compatibility links after capture."""

    removed: list[dict[str, str]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_symlink():
            continue
        target = os.readlink(path)
        if not target.startswith("/work/examples/") or path.exists():
            raise ValueError(f"unexpected M28 runtime symlink: {path} -> {target}")
        removed.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "target": target,
            }
        )
        path.unlink()
    return removed


def _run_container(
    *, root: Path, actor: str, treatment: str,
) -> dict[str, Any]:
    name = f"g7-m28-{actor.lower()}-{treatment}-seed{SEED}-a1"
    output_dir = root / "runs" / actor / treatment
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite M28 run: {output_dir}")
    request_path = root / "requests" / actor / f"{treatment}_action_request.json"
    common = [
        "python3", "-m", "g7confirm.m28_runtime",
        "--operating-point", OPERATING_POINT,
        "--windows", "3",
        "--coupling-step", "10",
        "--attacker-seed", str(SEED),
        "--noise-seed", str(SEED + 90000),
        "--preliminary-role", "attack_development",
        "--pair-id", pair_id(actor),
        "--action-request", _container_path(request_path),
        "--output-dir", _container_path(output_dir),
    ]
    if treatment == "benign":
        common.extend(
            ["--arm", "benign", "--budget-windows", "0", "--energy-cap-kvah", "0"]
        )
    elif treatment == "attack":
        common.extend(
            [
                "--arm", "probe",
                "--probe-id", TARGET_ID,
                "--probe-kw", str(COMMAND_KW),
                "--budget-windows", "1",
                "--energy-cap-kvah", "2",
            ]
        )
    else:
        raise ValueError(f"unregistered M28 treatment: {treatment}")
    inner = "PYTHONPATH=/work/v3/g7_confirmatory " + " ".join(
        shlex.quote(item) for item in common
    )
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
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=False)
    removed_links = _remove_container_only_links(output_dir)
    stdout_path = output_dir / "console.stdout.txt"
    stderr_path = output_dir / "console.stderr.txt"
    if stdout_path.exists() or stderr_path.exists():
        raise FileExistsError(f"M28 console evidence already exists: {output_dir}")
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    teardown = subprocess.run(
        [
            "docker", "ps", "-a", "--filter", f"name=^/{name}$",
            "--format", "{{.Names}}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    remaining = teardown.stdout.decode("utf-8", errors="replace").splitlines()
    return {
        "actor": actor,
        "treatment": treatment,
        "action_id": json.loads(request_path.read_text(encoding="utf-8"))["action_id"],
        "container_name": name,
        "container_exit_code": completed.returncode,
        "stdout_sha256": _sha256_bytes(completed.stdout),
        "stderr_sha256": _sha256_bytes(completed.stderr),
        "container_only_links_removed": removed_links,
        "container_only_link_count": len(removed_links),
        "teardown_query_exit_code": teardown.returncode,
        "teardown_remaining_names": remaining,
        "teardown_verified": teardown.returncode == 0 and remaining == [],
        "retry_count": 0,
    }


def execute(root: Path) -> dict[str, Any]:
    """Execute exactly four M28 traces once and retain every result."""

    root = root.resolve()
    if not root.is_relative_to(PACKAGE_ROOT):
        raise ValueError("M28 output must remain under g7_confirmatory")
    contract_path = root / "contract.json"
    if (
        not contract_path.is_file()
        or json.loads(contract_path.read_text(encoding="utf-8"))
        != build_contract(root)
    ):
        raise ValueError("M28 execution requires the exact final-code contract")
    if (root / "runtime_execution.json").exists() or (root / "runs").exists():
        raise FileExistsError("refusing to overwrite an M28 runtime attempt")
    image = subprocess.run(
        ["docker", "image", "inspect", IMAGE_TAG, "--format", "{{.Id}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    image_id = image.stdout.decode("utf-8", errors="replace").strip()
    if image.returncode != 0 or image_id != IMAGE_ID:
        message = image_id or image.stderr.decode("utf-8", errors="replace")
        raise ValueError(f"M28 image identity drift: {message}")

    runs: list[dict[str, Any]] = []
    issues: list[str] = []
    for actor in ACTORS:
        for treatment in ("benign", "attack"):
            record = _run_container(root=root, actor=actor, treatment=treatment)
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
        "status": "complete" if not issues and len(runs) == 4 else "failed_closed",
        "issues": issues,
        "contract_id": json.loads(contract_path.read_text(encoding="utf-8"))[
            "contract_id"
        ],
        "container_image_tag": IMAGE_TAG,
        "container_image_id": IMAGE_ID,
        "network_mode": "none",
        "container_user": f"{os.getuid()}:{os.getgid()}",
        "entrypoint_override": "/bin/bash",
        "run_cap": 4,
        "runs_completed": len(runs),
        "runs": runs,
        "retry_count": 0,
        "containers_ephemeral": True,
        "teardown_verified": bool(runs)
        and all(item["teardown_verified"] for item in runs),
        "upstream_IA4_model_decision_reused": True,
        "new_model_or_embedding_inference_used": False,
        "model_or_embedding_service_started_or_restarted": False,
        "detector_or_defense_used": False,
        "real_network_used": False,
        "physical_field_connection": False,
        "final_evaluation_data_accessed": False,
    }
    create_once_json(root / "runtime_execution.json", execution)
    return execution


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = execute(args.root)
    print(
        json.dumps(
            {
                "status": result["status"],
                "runs_completed": result["runs_completed"],
                "issues": result["issues"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return int(result["status"] != "complete")


if __name__ == "__main__":
    raise SystemExit(main())

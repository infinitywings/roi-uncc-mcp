#!/usr/bin/env python3
"""Run one create-once locked NATIG toolchain-base build with evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from .validate_locked_build import validate
except ImportError:
    from validate_locked_build import validate


HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command(argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "output": completed.stdout,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    context = args.context.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)

    manifest_path = context / "context_manifest.json"
    lock_path = context / "locked_dependencies.json"
    context_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("live_ready") is not False:
        parser.error("this runner only admits a non-live-ready toolchain base")
    validation = validate(
        lock_path,
        context / "Dockerfile",
        HERE / "prepare_context.py",
        context,
    )
    (output / "prebuild_validation.json").write_text(
        json.dumps(validation, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if not validation["valid"]:
        print(
            "success=False returncode=2 "
            "reason=locked-context-validation-failed"
        )
        return 2

    docker_version = command(
        ["docker", "version", "--format", "{{json .}}"]
    )
    argv = [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "--no-cache",
        "--progress=plain",
        "--tag",
        args.image_tag,
        str(context),
    ]
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    started = time.monotonic()
    build = command(argv)
    elapsed_s = time.monotonic() - started
    completed_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log_path = output / "docker_build.log"
    log_path.write_text(build["output"], encoding="utf-8")

    inspect = (
        command(
            [
                "docker",
                "image",
                "inspect",
                args.image_tag,
                "--format",
                "{{json .}}",
            ]
        )
        if build["returncode"] == 0
        else None
    )
    result = {
        "schema_version": "1.0",
        "scope": "G4 locked NATIG toolchain base; not live-ready",
        "context": {
            "path": str(context),
            "manifest_sha256": sha256(manifest_path),
            "lock_sha256": sha256(lock_path),
            "dockerfile_sha256": sha256(context / "Dockerfile"),
            "natig_sha256_manifest_sha256": sha256(
                context / "natig.sha256"
            ),
            "manifest": context_manifest,
        },
        "docker_version": docker_version["output"].strip(),
        "prebuild_validation": validation,
        "build": {
            "argv": argv,
            "started_utc": started_utc,
            "completed_utc": completed_utc,
            "elapsed_s": elapsed_s,
            "returncode": build["returncode"],
            "log": log_path.name,
            "log_sha256": sha256(log_path),
        },
        "image": (
            {
                "tag": args.image_tag,
                "inspect_returncode": inspect["returncode"],
                "inspect": json.loads(inspect["output"]),
            }
            if inspect is not None and inspect["returncode"] == 0
            else None
        ),
        "live_ready": False,
        "live_readiness_blockers": lock["live_readiness_blockers"],
        "success": build["returncode"] == 0,
    }
    (output / "locked_build_attempt.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"success={result['success']} returncode={build['returncode']} "
        f"elapsed_s={elapsed_s:.1f} log={log_path}"
    )
    return build["returncode"]


if __name__ == "__main__":
    raise SystemExit(main())

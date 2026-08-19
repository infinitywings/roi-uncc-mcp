#!/usr/bin/env python3
"""Run and preserve one create-once NATIG Docker build attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def command(argv: list[str], cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "output": completed.stdout,
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dockerfile", type=Path, required=True)
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    dockerfile = args.dockerfile.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    commit = command(["git", "rev-parse", "HEAD"], cwd=source)
    tree = command(["git", "rev-parse", "HEAD^{tree}"], cwd=source)
    docker_version = command(["docker", "version", "--format", "{{json .}}"])
    argv = [
        "docker",
        "build",
        "--no-cache",
        "--progress=plain",
        "--tag",
        args.image_tag,
        "--file",
        str(dockerfile),
        str(source),
    ]
    started = time.monotonic()
    build = command(argv)
    elapsed_s = time.monotonic() - started
    log_path = output_dir / "docker_build.log"
    log_path.write_text(build["output"], encoding="utf-8")

    image = (
        command(
            [
                "docker",
                "image",
                "inspect",
                args.image_tag,
                "--format",
                "{{.Id}} {{.Created}} {{.Size}}",
            ]
        )
        if build["returncode"] == 0
        else None
    )
    result = {
        "schema_version": "1.0",
        "source": {
            "path": str(source),
            "commit": commit["output"].strip(),
            "tree": tree["output"].strip(),
        },
        "dockerfile": {
            "path": str(dockerfile),
            "sha256": sha256(dockerfile),
        },
        "docker_version": docker_version["output"].strip(),
        "build": {
            "argv": argv,
            "returncode": build["returncode"],
            "elapsed_s": elapsed_s,
            "log": log_path.name,
            "log_sha256": sha256(log_path),
        },
        "image": (
            {
                "tag": args.image_tag,
                "inspect": image["output"].strip(),
                "inspect_returncode": image["returncode"],
            }
            if image is not None
            else None
        ),
        "success": build["returncode"] == 0,
    }
    (output_dir / "natig_build_attempt.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"success={result['success']} "
        f"returncode={build['returncode']} elapsed_s={elapsed_s:.1f} "
        f"log={log_path}"
    )
    return build["returncode"]


if __name__ == "__main__":
    raise SystemExit(main())

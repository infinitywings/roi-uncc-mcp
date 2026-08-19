#!/usr/bin/env python3
"""Create a non-overwriting identity manifest for the current v2 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANONICAL_FILES = [
    "paper_writing/v2/main.tex",
    "paper_writing/v2/main.pdf",
    "paper_writing/v2/ref.bib",
    "paper_writing/v2/sections/evaluation.tex",
    "paper_writing/v2/sections/framework.tex",
    "paper_writing/v2/sections/discussion.tex",
    "v2/results/CAMPAIGN_REPORT.md",
    "v2/results/campaign/analysis.json",
    "v2/analysis/analyze_v2.py",
    "v2/configs/experiment.yaml",
    "v2/configs/constraints.yaml",
    "v2/helics/federation.json",
    "v2/helics/v2_cosim.json",
    "v2/controller/ev_controller_v2.py",
    "v2/controller/v2_control.json",
    "v2/run_experiments.py",
    "v2/docker/docker-compose.yml",
    "examples/2bus-13bus/1c_IEEE_123_feeder.glm",
    "examples/2bus-13bus/1c_IEEE_123_feeder_2.glm",
    "examples/2bus-13bus/mainglm.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(repo: Path, relative: str) -> dict[str, Any]:
    path = repo / relative
    if not path.is_file():
        return {"path": relative, "status": "missing"}
    return {
        "path": relative,
        "status": "present",
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def tree_record(repo: Path, relative: str) -> dict[str, Any]:
    root = repo / relative
    records = [
        file_record(repo, str(path.relative_to(repo)))
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    identity = hashlib.sha256()
    for record in records:
        identity.update(record["path"].encode("utf-8"))
        identity.update(b"\0")
        identity.update(record["sha256"].encode("ascii"))
        identity.update(b"\n")
    return {
        "path": relative,
        "file_count": len(records),
        "tree_sha256": identity.hexdigest(),
        "files": records,
    }


def command(repo: Path, args: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}
    return {
        "available": True,
        "returncode": completed.returncode,
        "output": completed.stdout.strip(),
    }


def tool_version(repo: Path, name: str, args: list[str]) -> dict[str, Any]:
    location = shutil.which(name)
    if location is None:
        return {"available": False}
    result = command(repo, [location, *args])
    result["path"] = location
    return result


def summarize_campaign(repo: Path) -> dict[str, Any]:
    root = repo / "v2/results/campaign"
    result_files = [
        path
        for path in root.glob("hr*/*.json")
        if path.name != "analysis.json"
    ]
    by_condition: dict[str, dict[str, int]] = {}
    for path in result_files:
        parts = path.stem.split("_")
        attacker = "_".join(parts[:-2])
        condition = parts[-2]
        by_condition.setdefault(condition, {})
        by_condition[condition][attacker] = (
            by_condition[condition].get(attacker, 0) + 1
        )
    return {
        "planned_runs_from_report": 45,
        "observed_result_files": len(result_files),
        "reported_completed_runs": 37,
        "reported_timeout_failures": 8,
        "observed_by_condition_and_attacker": by_condition,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "baseline/v2_freeze_manifest.json",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()

    if output.exists():
        print(f"Refusing to overwrite existing manifest: {output}", file=sys.stderr)
        return 2

    head = command(repo, ["git", "rev-parse", "HEAD"])
    status = command(repo, ["git", "status", "--short"])
    manifest = {
        "schema_version": "0.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Identity freeze for the v2 comparison evidence; not approval of its claims.",
        "repository": {
            "root": str(repo),
            "head": head.get("output") if head.get("returncode") == 0 else None,
            "worktree_dirty": bool(status.get("output")),
            "status_short": status.get("output", "").splitlines(),
        },
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "tools": {
                "gridlabd": tool_version(repo, "gridlabd", ["--version"]),
                "helics_broker": tool_version(repo, "helics_broker", ["--version"]),
                "docker": tool_version(repo, "docker", ["--version"]),
            },
        },
        "canonical_files": [file_record(repo, path) for path in CANONICAL_FILES],
        "campaign_tree": tree_record(repo, "v2/results/campaign"),
        "campaign_counts": summarize_campaign(repo),
        "audit_flags": [
            {
                "id": "STAT_TEST_MISMATCH",
                "status": "open",
                "detail": "Manuscript/report describe Welch testing while analyze_v2.py does not pass equal_var=False.",
            },
            {
                "id": "INFORMATIVE_TIMEOUTS",
                "status": "open",
                "detail": "Eight of 45 planned runs timed out, with systematic seed/attacker patterns.",
            },
            {
                "id": "CONTROLLER_CADENCE",
                "status": "open",
                "detail": "Controller logic/config documentation mixes a 10 s decision cadence with a 60 s HELICS period.",
            },
            {
                "id": "LLM_MAX_TOKENS",
                "status": "open",
                "detail": "v2/configs/experiment.yaml declares 300 while the campaign report states 4000.",
            },
            {
                "id": "HOUR14_CEILING",
                "status": "classified",
                "detail": "Hour 14 is retained as a negative-control ceiling condition, not a responsive primary block.",
            },
        ],
    }

    missing = [
        item["path"]
        for item in manifest["canonical_files"]
        if item["status"] == "missing"
    ]
    if missing:
        print(f"Cannot freeze baseline; missing canonical files: {missing}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote immutable baseline manifest candidate: {output}")
    print(
        "Campaign result files: "
        f"{manifest['campaign_counts']['observed_result_files']}; "
        f"tree sha256={manifest['campaign_tree']['tree_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


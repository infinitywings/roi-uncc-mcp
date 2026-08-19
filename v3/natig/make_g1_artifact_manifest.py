#!/usr/bin/env python3
"""Create the top-level G1 evidence manifest without rewriting run evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIG = ROOT / "natig"
PINNED_COMMIT = "e163b350e243c6386477e35dead979a4cb2b7c60"
PINNED_TREE = "9f10cb55d5eaa4c20a95f292b84a266e9992bc1a"
IMAGE_ID = (
    "sha256:662e1ae46656de8a97195d7a6a6f7cfef84bd0baa997fedbea859e9d76978f7c"
)

EVIDENCE = [
    "natig/G1_VALIDATION_REPORT.md",
    "natig/README.md",
    "SELF_AUDIT.md",
    "IMPLEMENTATION_PLAN.md",
    "natig/DEPENDENCY_LOCK.md",
    "natig/locked_dependencies.json",
    "natig/audit_upstream.py",
    "natig/upstream_audit_r5/audit.json",
    "natig/upstream_audit_r6/audit.json",
    "natig/run_docker_build.py",
    "natig/upstream_build_r1/natig_build_attempt.json",
    "natig/upstream_build_r1/docker_build.log",
    "natig/make_benign_overlay.py",
    "natig/benign_overlay_r5/grid.json",
    "natig/benign_overlay_r5/overlay_manifest.json",
    "natig/benign_overlay_r6/grid.json",
    "natig/benign_overlay_r6/overlay_manifest.json",
    "natig/run_benign_ieee123.py",
    "natig/run_benign_federation.sh",
    "natig/benign_ieee123_r1/natig_benign_result.json",
    "natig/benign_ieee123_r2/natig_benign_result.json",
    "natig/benign_ieee123_r2/dnp3_perf.txt",
    "natig/benign_ieee123_r3/natig_benign_result.json",
    "natig/benign_ieee123_r3/dnp3_perf.txt",
    "natig/compare_benign_runs.py",
    "natig/benign_reproducibility_r2_r3.json",
    "natig/analyze_numeric_reproducibility.py",
    "natig/benign_numeric_reproducibility_r2_r3_v3.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> int:
    output = NATIG / "g1_artifact_manifest.json"
    if output.exists():
        raise FileExistsError(output)
    build = read_json("natig/upstream_build_r1/natig_build_attempt.json")
    failed = read_json("natig/benign_ieee123_r1/natig_benign_result.json")
    run_a = read_json("natig/benign_ieee123_r2/natig_benign_result.json")
    run_b = read_json("natig/benign_ieee123_r3/natig_benign_result.json")
    exact = read_json("natig/benign_reproducibility_r2_r3.json")
    numeric = read_json("natig/benign_numeric_reproducibility_r2_r3_v3.json")
    source = ROOT / "deps" / "natig-src"
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "-C", str(source), "status", "--porcelain"], text=True
        ).strip()
    )
    assertions = {
        "source_commit_matches": commit == PINNED_COMMIT,
        "source_tree_matches": tree == PINNED_TREE,
        "source_clean": not dirty,
        "upstream_build_completed": build["success"] is True,
        "built_image_matches": build["image"]["inspect"].split()[0] == IMAGE_ID,
        "upstream_launch_failure_retained": failed["success"] is False,
        "run_r2_completed": run_a["success"] is True,
        "run_r3_completed": run_b["success"] is True,
        "same_image_and_effective_config": (
            run_a["image"]["resolved_id"] == run_b["image"]["resolved_id"] == IMAGE_ID
            and run_a["configuration"]["effective_hashes"]
            == run_b["configuration"]["effective_hashes"]
        ),
        "same_dnp3_trace": (
            run_a["normalized_science_signature"]["files"]["dnp3_perf.txt"]
            == run_b["normalized_science_signature"]["files"]["dnp3_perf.txt"]
        ),
        "exact_reproducibility_failure_retained": exact["success"] is False,
        "posthoc_numeric_diagnostic_passed": numeric["success"] is True,
        "evidence_files_present": all((ROOT / path).is_file() for path in EVIDENCE),
    }
    manifest = {
        "schema_version": "1.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "G1 bounded NATIG IEEE-123/DNP3 no-attack component proof; "
            "not locked-build, G4-equivalence, or attack evidence"
        ),
        "source": {"commit": commit, "tree": tree, "dirty": dirty},
        "image_id": IMAGE_ID,
        "verdict": "partial_pass_with_blockers",
        "assertions": assertions,
        "evidence": {
            path: {"sha256": sha256(ROOT / path), "bytes": (ROOT / path).stat().st_size}
            for path in EVIDENCE
        },
        "success": all(assertions.values()),
    }
    output.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"success={manifest['success']} evidence={len(EVIDENCE)}")
    return 0 if manifest["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

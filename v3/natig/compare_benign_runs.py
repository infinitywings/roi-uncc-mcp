#!/usr/bin/env python3
"""Compare two create-once NATIG benign-run manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    a = json.loads(args.run_a.read_text(encoding="utf-8"))
    b = json.loads(args.run_b.read_text(encoding="utf-8"))

    a_signature = a["normalized_science_signature"]
    b_signature = b["normalized_science_signature"]
    a_files = a_signature["files"]
    b_files = b_signature["files"]
    all_paths = sorted(set(a_files) | set(b_files))
    mismatches = [
        {
            "path": path,
            "run_a": a_files.get(path),
            "run_b": b_files.get(path),
        }
        for path in all_paths
        if a_files.get(path) != b_files.get(path)
    ]
    assertions = {
        "run_a_success": a["success"] is True,
        "run_b_success": b["success"] is True,
        "same_resolved_image": a["image"]["resolved_id"]
        == b["image"]["resolved_id"],
        "same_embedded_commit": a["embedded_source"]["commit"]
        == b["embedded_source"]["commit"],
        "same_effective_config": a["configuration"]["effective_hashes"]
        == b["configuration"]["effective_hashes"],
        "same_signature_file_set": set(a_files) == set(b_files),
        "zero_normalized_mismatches": not mismatches,
        "same_aggregate_signature": a_signature["sha256"]
        == b_signature["sha256"],
    }
    result = {
        "schema_version": "1.0",
        "run_a": str(args.run_a.resolve()),
        "run_b": str(args.run_b.resolve()),
        "assertions": assertions,
        "normalized_file_count": len(all_paths),
        "mismatches": mismatches,
        "success": all(assertions.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"success={result['success']} files={len(all_paths)} "
        f"mismatches={len(mismatches)}"
    )
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

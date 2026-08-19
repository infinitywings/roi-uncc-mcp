#!/usr/bin/env python3
"""Create a create-once manifest for the bounded G4 preparation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test-count", type=int, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite create-once output: {output}")
    if args.test_count <= 0:
        parser.error("--test-count must be positive")

    relative_files = [
        Path("v3/README.md"),
        Path("v3/IMPLEMENTATION_PLAN.md"),
        Path("v3/SELF_AUDIT.md"),
        Path("v3/interfaces/cyber_message.schema.json"),
        Path("v3/interfaces/README.md"),
        Path("v3/opender/device.py"),
        Path("v3/cyber_gateway/README.md"),
        Path("v3/cyber_gateway/dnp3_point_map.yaml"),
        Path("v3/cyber_gateway/gateway.py"),
        Path("v3/cyber_gateway/tests/test_gateway.py"),
        Path("v3/cyber_gateway/tests/test_real_opender_sink.py"),
        Path("v3/natig_adapter/README.md"),
        Path("v3/natig_adapter/POINT_MAP_AUDIT.md"),
        Path("v3/natig_adapter/endpoint_graph.json"),
        Path("v3/natig_adapter/validate_endpoint_graph.py"),
        Path("v3/natig_adapter/dnp3_codec.py"),
        Path("v3/natig_adapter/gateway_bridge.py"),
        Path("v3/natig_adapter/run_offline_conformance.py"),
        Path("v3/natig_adapter/tests/test_endpoint_graph.py"),
        Path("v3/natig_adapter/tests/test_dnp3_codec.py"),
        Path("v3/natig_adapter/tests/test_gateway_bridge.py"),
        Path("v3/natig_adapter/tests/test_offline_conformance.py"),
        Path(
            "v3/natig_adapter/offline_conformance_r2/"
            "offline_conformance.json"
        ),
        Path(
            "v3/natig_adapter/offline_conformance_r2/"
            "OFFLINE_CONFORMANCE_REPORT.md"
        ),
    ]
    missing = [
        str(path) for path in relative_files if not (repo / path).is_file()
    ]
    if missing:
        parser.error("Missing required artifact(s): " + ", ".join(missing))

    evidence_path = (
        repo
        / "v3/natig_adapter/offline_conformance_r2/"
        "offline_conformance.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("verdict") != "PASS":
        parser.error("offline conformance evidence does not pass")
    metrics = evidence["result"]["metrics"]
    embedded_mismatches = []
    for relative, expected in evidence["source_sha256"].items():
        actual = sha256(repo / "v3" / relative)
        if actual != expected:
            embedded_mismatches.append(
                {"path": relative, "expected": expected, "actual": actual}
            )
    if embedded_mismatches:
        parser.error(
            "offline evidence source hashes are stale: "
            + json.dumps(embedded_mismatches, sort_keys=True)
        )

    manifest = {
        "schema_version": "1.0",
        "gate": "G4 benign cyber-path equivalence preparation",
        "verdict": "PASS_OFFLINE_PREPARATION_ONLY",
        "scope": evidence["scope"],
        "not_proven": [
            "live NATIG DNP3 transport",
            "ns-3 network behavior",
            "HELICS endpoint timing",
            "GridLAB-D physical equivalence through NATIG",
            "network impairment or attacker effect",
        ],
        "open_blockers": [
            "locked-source NATIG image is not built",
            "stock NATIG direct GridLAB-D callback must be replaced",
            "undeclared CC/Monitor and auxiliary endpoint debt must be removed",
            "live benign direct-reference versus NATIG equivalence is unrun",
        ],
        "verification": {
            "gateway_and_adapter_tests_passed": args.test_count,
            "endpoint_graph_passed": True,
            "design_validation_passed": True,
            "offline_run_verdict": evidence["verdict"],
            "two_run_exact_match": evidence["repeatability"][
                "exact_canonical_match"
            ],
            "run_signature_sha256": evidence["repeatability"][
                "run_signature_sha256"
            ],
            "steps_per_path": metrics["steps_per_path"],
            "commands_per_path": metrics["commands_per_path"],
            "lifecycle_records": metrics["lifecycle_records"],
            "telemetry_objects_encoded_decoded": metrics[
                "telemetry_objects_encoded_decoded"
            ],
            "trace_max_abs_difference": metrics[
                "trace_max_abs_difference"
            ],
            "embedded_source_hashes_match": True,
        },
        "artifacts": {
            str(path): {
                "sha256": sha256(repo / path),
                "bytes": (repo / path).stat().st_size,
            }
            for path in relative_files
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {output}: artifacts={len(relative_files)} "
        f"verdict={manifest['verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

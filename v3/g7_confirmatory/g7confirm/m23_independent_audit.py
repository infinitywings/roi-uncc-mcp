"""Independently audit the exact create-once M23 source and raw evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .manifest import create_once_json
from .preliminary_only_gate import validate_preliminary_action_request


AUDIT_SCHEMA_VERSION = "grideval-g7-m23-independent-audit/v1"
SOURCE_SCHEMA_VERSION = "grideval-g7-m23-system-identification/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m23-system-identification-contract/v1"
EXPECTED_SOURCE_SHA256 = (
    "30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1"
)
EXPECTED_CONTRACT_SHA256 = (
    "b870c6af3279f709bd096a3ed6c39f3b15f3c6428c5fd65cb0eb61e3e4b75e74"
)
EXPECTED_GENERATOR_SHA256 = (
    "72dca567388aca9203129c39a3b97c801fa1322c0c643a2e9e1617147480598f"
)
EXPECTED_RUNTIME_SHA256 = (
    "8ebfbcbd28c4952c2d6a90517e6b0a4bc84525de7fc5889b26afda5b887d939e"
)
EXPECTED_SOURCE_ID = (
    "m23source_300ed1e8d0d878cd5ce932e59fa8920d8a22edba3793a9cfc5d9044ca0dd9f50"
)
EXPECTED_CONTRACT_ID = (
    "m23contract_1fe0006a3ed480a1ef6b7a084a7031aa8855c319f02c46bfbaea42a0c45ad859"
)
EXPECTED_TARGETS = ("DER_EV1_BESS", "DER_EV4_BESS")
EXPECTED_DEVICES = (
    "DER_EV1_BESS",
    "DER_EV3_PV",
    "DER_EV4_BESS",
    "DER_EV5_PV",
)
FINAL_EVALUATION_SEEDS = list(range(9101, 9113))
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = PACKAGE_ROOT / "g7confirm" / "m23_system_identification.py"
RUNTIME_PATH = PACKAGE_ROOT / "g7confirm" / "runtime.py"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _close(left: Any, right: Any) -> bool:
    try:
        return math.isclose(
            float(left), float(right), rel_tol=1e-12, abs_tol=1e-15,
        )
    except (TypeError, ValueError):
        return False


def _verify_self_address(
    value: Mapping[str, Any], *, id_field: str, prefix: str,
) -> bool:
    content = json.loads(_canonical_json(value))
    actual = content.pop(id_field, None)
    return actual == prefix + _sha256_value(content)


def _verify_manifest(root: Path, source: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    manifest = source.get("manifest", {})
    if not isinstance(manifest.get("created_at_utc"), str):
        issues.append("manifest_timestamp_missing")
    entries = manifest.get("files", [])
    if not isinstance(entries, list) or not entries:
        return ["manifest_empty"]
    seen: set[str] = set()
    for entry in entries:
        relative = Path(str(entry.get("path", "")))
        label = relative.as_posix()
        if relative.is_absolute() or ".." in relative.parts:
            issues.append(f"manifest_path_unscoped:{label}")
            continue
        if label in seen:
            issues.append(f"manifest_duplicate:{label}")
        seen.add(label)
        path = root / relative
        if not path.is_file():
            issues.append(f"manifest_missing:{label}")
            continue
        if path.stat().st_size != entry.get("bytes"):
            issues.append(f"manifest_size_drift:{label}")
        if _sha256_file(path) != entry.get("sha256"):
            issues.append(f"manifest_sha256_drift:{label}")
    if "m23_system_identification.json" in seen:
        issues.append("source_recursively_in_manifest")
    return issues


def _verify_arithmetic(source: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    runs = source.get("runs", [])
    if not isinstance(runs, list) or len(runs) != 5:
        return ["five_run_structure_drift"]
    by_id = {run.get("treatment"): run for run in runs}
    if len(by_id) != 5 or "benign" not in by_id:
        return ["treatment_identity_drift"]
    expected_pairs = {
        "DER_EV1_BESS": ("probe_ev1_plus30", "probe_ev1_minus30"),
        "DER_EV4_BESS": ("probe_ev4_plus30", "probe_ev4_minus30"),
    }
    columns = {
        item.get("target_id"): item
        for item in source.get("estimator", {}).get("columns", [])
    }
    tool_values = source.get("read_only_tool_payload_candidate", {}).get(
        "values", {}
    )
    benign = by_id["benign"]["windows"][2]
    for target, (plus_id, minus_id) in expected_pairs.items():
        if plus_id not in by_id or minus_id not in by_id or target not in columns:
            issues.append(f"missing_symmetric_pair:{target}")
            continue
        plus = by_id[plus_id]["windows"][2]
        minus = by_id[minus_id]["windows"][2]
        column = columns[target]
        recomputed: dict[str, float] = {}
        for device in EXPECTED_DEVICES:
            central = (
                float(plus["true_voltage_pu"][device])
                - float(minus["true_voltage_pu"][device])
            ) / 60.0
            plus_one_sided = (
                float(plus["true_voltage_pu"][device])
                - float(benign["true_voltage_pu"][device])
            ) / 30.0
            minus_one_sided = (
                float(benign["true_voltage_pu"][device])
                - float(minus["true_voltage_pu"][device])
            ) / 30.0
            center_residual = (
                (
                    float(plus["true_voltage_pu"][device])
                    + float(minus["true_voltage_pu"][device])
                ) / 2.0
                - float(benign["true_voltage_pu"][device])
            )
            checks = {
                "central": (
                    column["central_true_voltage_gain_pu_per_kw"][device],
                    central,
                ),
                "plus": (
                    column["plus_one_sided_true_voltage_gain_pu_per_kw"][device],
                    plus_one_sided,
                ),
                "minus": (
                    column["minus_one_sided_true_voltage_gain_pu_per_kw"][device],
                    minus_one_sided,
                ),
                "center": (
                    column["centered_true_voltage_residual_pu"][device],
                    center_residual,
                ),
            }
            for name, (actual, expected) in checks.items():
                if not _close(actual, expected):
                    issues.append(f"voltage_{name}_arithmetic_drift:{target}:{device}")
            recomputed[device] = central
        max_gain = max(abs(value) for value in recomputed.values())
        if not _close(column.get("max_abs_true_voltage_gain_pu_per_kw"), max_gain):
            issues.append(f"max_gain_arithmetic_drift:{target}")
        if not _close(tool_values.get(target), max_gain):
            issues.append(f"tool_payload_arithmetic_drift:{target}")
        for field in ("source_p_w", "source_q_var"):
            central = (
                float(plus["source_power_w_var"][field])
                - float(minus["source_power_w_var"][field])
            ) / 60.0
            residual = (
                (
                    float(plus["source_power_w_var"][field])
                    + float(minus["source_power_w_var"][field])
                ) / 2.0
                - float(benign["source_power_w_var"][field])
            )
            if not _close(
                column["central_source_power_gain_w_var_per_kw"][field], central,
            ):
                issues.append(f"source_central_arithmetic_drift:{target}:{field}")
            if not _close(
                column["centered_source_power_residual_w_var"][field], residual,
            ):
                issues.append(f"source_residual_arithmetic_drift:{target}:{field}")
    return issues


def audit_source(root: Path) -> list[str]:
    """Audit exact M23 bytes without rebuilding the timestamped source."""

    issues: list[str] = []
    source_path = root / "m23_system_identification.json"
    contract_path = root / "contract.json"
    try:
        source = _load_json(source_path)
        contract = _load_json(contract_path)
    except (OSError, ValueError, TypeError) as exc:
        return [f"evidence_unreadable:{exc}"]
    if _sha256_file(source_path) != EXPECTED_SOURCE_SHA256:
        issues.append("source_file_sha256_drift")
    if _sha256_file(contract_path) != EXPECTED_CONTRACT_SHA256:
        issues.append("contract_file_sha256_drift")
    if source.get("source_id") != EXPECTED_SOURCE_ID or not _verify_self_address(
        source, id_field="source_id", prefix="m23source_",
    ):
        issues.append("source_self_address_drift")
    if contract.get("contract_id") != EXPECTED_CONTRACT_ID or not _verify_self_address(
        contract, id_field="contract_id", prefix="m23contract_",
    ):
        issues.append("contract_self_address_drift")
    if source.get("schema_version") != SOURCE_SCHEMA_VERSION:
        issues.append("source_schema_drift")
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        issues.append("contract_schema_drift")
    if source.get("contract_id") != EXPECTED_CONTRACT_ID:
        issues.append("source_contract_binding_drift")
    if _sha256_file(GENERATOR_PATH) != EXPECTED_GENERATOR_SHA256:
        issues.append("generator_bytes_drift")
    if _sha256_file(RUNTIME_PATH) != EXPECTED_RUNTIME_SHA256:
        issues.append("runtime_bytes_drift")
    bindings = contract.get("source_bindings", {})
    if bindings.get("source_builder_code", {}).get("sha256") != EXPECTED_GENERATOR_SHA256:
        issues.append("contract_generator_binding_drift")
    if bindings.get("runtime_code", {}).get("sha256") != EXPECTED_RUNTIME_SHA256:
        issues.append("contract_runtime_binding_drift")

    requests = contract.get("action_requests", {})
    if not isinstance(requests, dict) or len(requests) != 6:
        issues.append("action_request_count_drift")
    else:
        for name, request in requests.items():
            request_issues = validate_preliminary_action_request(request)
            issues.extend(f"{name}:{issue}" for issue in request_issues)
            if request.get("partition_role") != "system_identification":
                issues.append(f"{name}:partition_drift")
            if request.get("final_evaluation_data_accessed") is not False:
                issues.append(f"{name}:final_evaluation_opened")
            if request.get("physical_field_actuator") is not False:
                issues.append(f"{name}:physical_actuator_opened")
    source_request = source.get("source_generation_action_request", {})
    if source_request != requests.get("source_generation_action_request.json"):
        issues.append("source_action_request_binding_drift")

    expected_false = (
        "campaign_authorized",
        "confirmatory_claim_authorized",
        "evaluation_opened",
    )
    for field in expected_false:
        if source.get(field) is not False:
            issues.append(f"source_boundary_opened:{field}")
    if source.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_accessed")
    if source.get("final_evaluation_seeds_remain_sealed") != FINAL_EVALUATION_SEEDS:
        issues.append("final_evaluation_seal_drift")
    tool_payload = source.get("read_only_tool_payload_candidate", {})
    if tool_payload.get("empirical_source_admitted") is not False:
        issues.append("source_admission_boundary_opened")
    if set(tool_payload.get("values", {})) != set(EXPECTED_TARGETS):
        issues.append("tool_payload_target_drift")
    runtime = source.get("runtime_environment", {})
    runtime_false = (
        "physical_field_connection",
        "final_evaluation_data_accessed",
        "model_or_embedding_inference_used",
        "model_or_embedding_service_started_or_restarted",
    )
    for field in runtime_false:
        if runtime.get(field) is not False:
            issues.append(f"runtime_boundary_opened:{field}")
    if runtime.get("network_mode") != "none":
        issues.append("container_network_boundary_opened")
    if runtime.get("teardown_verified") is not True:
        issues.append("container_teardown_unverified")
    issues.extend(_verify_manifest(root, source))
    issues.extend(_verify_arithmetic(source))
    return sorted(set(issues))


def build_audit_receipt(root: Path) -> dict[str, Any]:
    """Create one self-addressed receipt for the independent audit result."""

    issues = audit_source(root)
    content = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": _sha256_file(root / "m23_system_identification.json"),
        "source_id": EXPECTED_SOURCE_ID,
        "contract_sha256": _sha256_file(root / "contract.json"),
        "contract_id": EXPECTED_CONTRACT_ID,
        "generator_sha256": _sha256_file(GENERATOR_PATH),
        "runtime_sha256": _sha256_file(RUNTIME_PATH),
        "auditor_sha256": _sha256_file(Path(__file__)),
        "status": "passed" if not issues else "failed_closed",
        "issues": issues,
        "checks": [
            "source_and_contract_self_address",
            "exact_generator_and_runtime_bindings",
            "six_M18_action_requests_and_access_seals",
            "manifest_file_size_and_sha256",
            "five_run_and_symmetric_pair_structure",
            "central_and_one_sided_voltage_arithmetic",
            "centered_voltage_residual_arithmetic",
            "central_and_centered_source_power_arithmetic",
            "tool_payload_scalar_derivation",
            "container_network_and_teardown_boundary",
            "final_evaluation_and_resource_admission_seals",
        ],
        "known_generator_verifier_failure_retained": {
            "issues": ["M23_source_content_drift", "M23_source_id_drift"],
            "cause": "build_manifest_created_at_utc_changes_on_rebuild",
            "source_overwritten": False,
            "runtime_rerun": False,
            "checkpoint_id": "chk_01M1MR10KGAJT84EJC0WT2YB4T",
        },
        "claim_boundary": (
            "A passing audit validates the exact stored M23 preliminary source "
            "and its arithmetic. It does not admit the source or establish "
            "repeatability, generalization, real-adapter safety, or final evidence."
        ),
    }
    receipt = json.loads(_canonical_json(content))
    receipt["audit_id"] = "m23audit_" + _sha256_value(content)
    return receipt


def verify_audit_receipt(root: Path, receipt: Mapping[str, Any]) -> list[str]:
    """Verify the independent receipt against current exact bytes."""

    issues = audit_source(root)
    content = json.loads(_canonical_json(receipt))
    audit_id = content.pop("audit_id", None)
    if audit_id != "m23audit_" + _sha256_value(content):
        issues.append("audit_receipt_self_address_drift")
    if receipt.get("auditor_sha256") != _sha256_file(Path(__file__)):
        issues.append("auditor_bytes_drift")
    if receipt.get("status") != "passed" or receipt.get("issues") != []:
        issues.append("stored_audit_not_passed")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output.resolve()
    if args.verify:
        receipt = _load_json(output)
        issues = verify_audit_receipt(root, receipt)
        print(json.dumps({"issues": issues}, indent=2))
        return int(bool(issues))
    receipt = build_audit_receipt(root)
    create_once_json(output, receipt)
    print(json.dumps({
        "status": receipt["status"],
        "audit_id": receipt["audit_id"],
        "issues": receipt["issues"],
    }, indent=2))
    return int(bool(receipt["issues"]))


if __name__ == "__main__":
    raise SystemExit(main())

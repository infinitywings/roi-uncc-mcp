from __future__ import annotations

import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path

from g7confirm.m24_read_only_adapter import (
    ADAPTER_CODE_PATH,
    CONSUMER_TARGETS,
    EmpiricalSensitivityAdapter,
    FORBIDDEN_PAYLOAD_FIELDS,
    M23_AUDIT_PATH,
    M23_SOURCE_PATH,
    METRIC,
    PAYLOAD_FIELDS,
    SOURCE_TARGETS,
    TARGET_ALIAS_MAP,
    _audit_issues,
    _canonical_json,
    _expected_tool_definition,
    _self_addressed,
    _source_issues,
    build_contract,
    build_qualification_receipt,
    verify_qualification,
)
from g7confirm.orchestration_contract import ContractViolation
from g7confirm.m24_independent_audit import (
    audit_qualification,
    build_audit_receipt,
    verify_audit_receipt,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
M24_ATTEMPT_ROOT = PACKAGE_ROOT / "artifacts" / "m24_read_only_adapter_attempt1"


class M24ReadOnlyAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = build_contract()
        cls.source = json.loads(M23_SOURCE_PATH.read_text(encoding="utf-8"))
        cls.audit = json.loads(M23_AUDIT_PATH.read_text(encoding="utf-8"))

    def _write_evidence(self, root: Path, source: object, audit: object) -> tuple[Path, Path]:
        source_path = root / "source.json"
        audit_path = root / "audit.json"
        source_path.write_text(
            json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        audit_path.write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return source_path, audit_path

    def test_contract_preserves_exact_m7_surface_and_boundaries(self):
        self.assertEqual(build_contract(), build_contract())
        consumer = self.contract["consumer_contract"]
        self.assertEqual(consumer["tool"], _expected_tool_definition())
        self.assertEqual(consumer["participant_rungs"], ["IA3", "IA4"])
        self.assertEqual(consumer["target_alias_map"], TARGET_ALIAS_MAP)
        self.assertEqual(
            consumer["exact_request"],
            {"metric": METRIC, "target_ids": list(CONSUMER_TARGETS)},
        )
        boundary = self.contract["access_boundary"]
        self.assertTrue(boundary["real_local_read_only_adapter_authorized"])
        for key, value in boundary.items():
            if key.endswith("_access_authorized") or key == "file_write_authorized":
                self.assertFalse(value)
        self.assertFalse(self.contract["source_admitted"])

    def test_adapter_maps_only_two_scalars_and_keeps_provenance_separate(self):
        adapter = EmpiricalSensitivityAdapter(contract=self.contract)
        result = adapter.invoke(
            arguments=self.contract["consumer_contract"]["exact_request"],
            caller_rung="IA3",
        )
        self.assertEqual(set(result.payload), set(PAYLOAD_FIELDS))
        self.assertEqual(set(result.payload["values"]), set(CONSUMER_TARGETS))
        source_values = self.source["read_only_tool_payload_candidate"]["values"]
        self.assertEqual(
            result.payload["values"],
            {
                alias: source_values[source_target]
                for alias, source_target in TARGET_ALIAS_MAP.items()
            },
        )
        encoded = result.payload_canonical_json
        for field in FORBIDDEN_PAYLOAD_FIELDS:
            self.assertNotIn(field, encoded)
        self.assertNotIn("source_binding", result.payload)
        self.assertEqual(result.receipt["source_binding"]["admitted"], False)
        self.assertTrue(
            result.receipt["source_binding"][
                "full_internal_response_vectors_preserved_by_exact_byte_reference"
            ]
        )

    def test_real_adapter_reads_exactly_source_and_audit_once(self):
        reads: list[Path] = []

        def tracked(path: Path) -> bytes:
            reads.append(path)
            return path.read_bytes()

        adapter = EmpiricalSensitivityAdapter(
            contract=self.contract, read_bytes=tracked
        )
        self.assertEqual(reads, [M23_SOURCE_PATH, M23_AUDIT_PATH])
        adapter.invoke(
            arguments=self.contract["consumer_contract"]["exact_request"],
            caller_rung="IA4",
        )
        self.assertEqual(reads, [M23_SOURCE_PATH, M23_AUDIT_PATH])

    def test_ia3_and_ia4_receive_identical_request_and_payload_bytes(self):
        receipt = build_qualification_receipt(self.contract)
        self.assertEqual(receipt["status"], "passed")
        self.assertTrue(all(receipt["parity"].values()))
        self.assertTrue(all(receipt["field_minimization"].values()))
        ia3 = receipt["invocations"]["IA3"]["receipt"]
        ia4 = receipt["invocations"]["IA4"]["receipt"]
        self.assertEqual(ia3["request_canonical_json"], ia4["request_canonical_json"])
        self.assertEqual(ia3["payload_canonical_json"], ia4["payload_canonical_json"])
        self.assertNotEqual(ia3["invocation_id"], ia4["invocation_id"])
        self.assertTrue(receipt["access_seals"]["real_local_read_only_adapter_executed"])
        for key, value in receipt["access_seals"].items():
            if key.endswith("_accessed"):
                self.assertFalse(value)

    def test_request_schema_alias_order_and_rung_fail_closed(self):
        valid = self.contract["consumer_contract"]["exact_request"]
        cases = (
            ({"metric": METRIC, "target_ids": ["DER_B", "DER_A"]}, "IA3"),
            ({"metric": METRIC, "target_ids": ["DER_A"]}, "IA3"),
            ({"metric": METRIC, "target_ids": list(CONSUMER_TARGETS), "extra": 1}, "IA3"),
            ({"metric": "source_power_gain", "target_ids": list(CONSUMER_TARGETS)}, "IA3"),
            (valid, "IA2"),
        )
        for arguments, rung in cases:
            with self.subTest(arguments=arguments, rung=rung):
                adapter = EmpiricalSensitivityAdapter(contract=self.contract)
                with self.assertRaises(ContractViolation):
                    adapter.invoke(arguments=arguments, caller_rung=rung)

    def test_contract_schema_alias_and_boundary_drift_fail_closed(self):
        mutations = []
        changed = copy.deepcopy(self.contract)
        changed["consumer_contract"]["target_alias_map"]["DER_A"] = "DER_EV4_BESS"
        mutations.append((changed, "consumer_alias_drift"))
        changed = copy.deepcopy(self.contract)
        changed["consumer_contract"]["tool"]["output_schema"]["additionalProperties"] = True
        mutations.append((changed, "consumer_tool_schema_drift"))
        changed = copy.deepcopy(self.contract)
        changed["access_boundary"]["network_access_authorized"] = True
        mutations.append((changed, "contract_access_boundary_opened"))
        changed = copy.deepcopy(self.contract)
        changed["source_admitted"] = True
        mutations.append((changed, "contract_boundary_opened"))
        for changed, expected in mutations:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ContractViolation, expected):
                    EmpiricalSensitivityAdapter(contract=changed)

    def test_source_semantic_mutations_are_independently_detected(self):
        mutations = []
        for path, value, issue in (
            (("schema_version",), "wrong", "source_schema_drift"),
            (("source_id",), "m23source_wrong", "source_id_drift"),
            (("status",), "ADMITTED", "source_status_drift"),
            (("classification",), "FINAL", "source_classification_drift"),
            (("evaluation_opened",), True, "source_boundary_opened:evaluation_opened"),
            (("final_evaluation_seeds_accessed",), [9101], "final_evaluation_accessed"),
            (("read_only_tool_payload_candidate", "empirical_source_admitted"), True, "source_admission_boundary_opened"),
            (("read_only_tool_payload_candidate", "metric"), "wrong", "source_payload_metric_drift"),
            (("read_only_tool_payload_candidate", "time_s"), 20, "source_payload_time_drift"),
        ):
            changed = copy.deepcopy(self.source)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append((changed, issue))
        changed = copy.deepcopy(self.source)
        changed["read_only_tool_payload_candidate"]["extra"] = "leak"
        mutations.append((changed, "source_payload_field_drift"))
        changed = copy.deepcopy(self.source)
        changed["read_only_tool_payload_candidate"]["values"]["DER_X"] = 0.1
        mutations.append((changed, "source_payload_target_drift"))
        for changed, issue in mutations:
            with self.subTest(issue=issue):
                self.assertIn(issue, _source_issues(changed))
                self.assertFalse(
                    _self_addressed(changed, id_field="source_id", prefix="m23source_")
                )

    def test_audit_semantic_mutations_are_independently_detected(self):
        mutations = []
        for field, value, issue in (
            ("schema_version", "wrong", "audit_schema_drift"),
            ("audit_id", "m23audit_wrong", "audit_id_drift"),
            ("status", "failed_closed", "audit_status_not_passed"),
            ("issues", ["problem"], "audit_issues_not_empty"),
            ("source_sha256", "0" * 64, "audit_source_hash_binding_drift"),
            ("source_id", "m23source_wrong", "audit_source_id_binding_drift"),
        ):
            changed = copy.deepcopy(self.audit)
            changed[field] = value
            mutations.append((changed, issue))
        for changed, issue in mutations:
            with self.subTest(issue=issue):
                self.assertIn(issue, _audit_issues(changed))

    def test_mutated_evidence_files_fail_before_payload_release(self):
        changed = copy.deepcopy(self.source)
        changed["read_only_tool_payload_candidate"]["values"][SOURCE_TARGETS[0]] = 0.01
        with tempfile.TemporaryDirectory() as directory:
            source_path, audit_path = self._write_evidence(
                Path(directory), changed, self.audit
            )
            with self.assertRaisesRegex(
                ContractViolation, "source_file_sha256_drift"
            ):
                EmpiricalSensitivityAdapter(
                    contract=self.contract,
                    source_path=source_path,
                    audit_path=audit_path,
                )

    def test_symlink_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_link = root / "source-link.json"
            source_link.symlink_to(M23_SOURCE_PATH)
            with self.assertRaisesRegex(ContractViolation, "must not be a symlink"):
                EmpiricalSensitivityAdapter(
                    contract=self.contract,
                    source_path=source_link,
                    audit_path=M23_AUDIT_PATH,
                )

    def test_adapter_module_has_no_external_service_imports(self):
        tree = ast.parse(ADAPTER_CODE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue({"requests", "httpx", "openai", "docker"}.isdisjoint(imported))
        source = ADAPTER_CODE_PATH.read_text(encoding="utf-8")
        for token in ("subprocess", "socket", "urlopen", "Popen", "os.system"):
            self.assertNotIn(token, source)

    def test_temporary_create_once_artifact_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contract.json").write_text(
                json.dumps(self.contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            receipt = build_qualification_receipt(self.contract)
            (root / "qualification_receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_qualification(root), [])
            mutated = copy.deepcopy(receipt)
            mutated["status"] = "failed_closed"
            (root / "qualification_receipt.json").write_text(
                json.dumps(mutated, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertIn("M24_receipt_content_drift", verify_qualification(root))

    def test_independent_auditor_accepts_exact_temporary_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contract.json").write_text(
                json.dumps(self.contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            receipt = build_qualification_receipt(self.contract)
            (root / "qualification_receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(audit_qualification(root), [])
            audit = build_audit_receipt(root)
            self.assertEqual(audit["status"], "passed")
            self.assertEqual(audit["issues"], [])
            self.assertEqual(verify_audit_receipt(root, audit), [])

    def test_independent_auditor_rejects_payload_or_access_provenance_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contract.json").write_text(
                json.dumps(self.contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            receipt = build_qualification_receipt(self.contract)
            receipt["invocations"]["IA4"]["payload"]["values"]["DER_B"] = 0.02
            receipt["invocations"]["IA3"]["receipt"]["access_boundary"][
                "network_accessed"
            ] = True
            (root / "qualification_receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            issues = audit_qualification(root)
            self.assertIn("payload_drift:IA4", issues)
            self.assertIn("IA3_IA4_payload_mismatch", issues)
            self.assertIn(
                "invocation_access_boundary_drift:IA3", issues
            )

    def test_duplicate_and_nonfinite_source_json_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.json"
            audit_path = root / "audit.json"
            audit_path.write_bytes(M23_AUDIT_PATH.read_bytes())
            source_path.write_text('{"source_id":"one","source_id":"two"}\n')
            with self.assertRaisesRegex(ContractViolation, "duplicate field"):
                EmpiricalSensitivityAdapter(
                    contract=self.contract,
                    source_path=source_path,
                    audit_path=audit_path,
                )
            source_path.write_text('{"value":NaN}\n')
            with self.assertRaisesRegex(ContractViolation, "non-finite constant"):
                EmpiricalSensitivityAdapter(
                    contract=self.contract,
                    source_path=source_path,
                    audit_path=audit_path,
                )

    def test_payload_is_a_defensive_copy(self):
        adapter = EmpiricalSensitivityAdapter(contract=self.contract)
        first = adapter.invoke(
            arguments=self.contract["consumer_contract"]["exact_request"],
            caller_rung="IA3",
        )
        first.payload["values"]["DER_A"] = 0.1
        second = adapter.invoke(
            arguments=self.contract["consumer_contract"]["exact_request"],
            caller_rung="IA3",
        )
        self.assertNotEqual(first.payload, second.payload)
        self.assertEqual(second.payload_canonical_json, second.receipt["payload_canonical_json"])

    def test_checked_in_artifact_passes_both_verifiers(self):
        self.assertEqual(verify_qualification(M24_ATTEMPT_ROOT), [])
        self.assertEqual(audit_qualification(M24_ATTEMPT_ROOT), [])
        audit = json.loads(
            (M24_ATTEMPT_ROOT / "independent_audit_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(verify_audit_receipt(M24_ATTEMPT_ROOT, audit), [])
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["issues"], [])

    def test_receipt_schema_is_closed_and_names_exact_version(self):
        schema = json.loads(
            (PACKAGE_ROOT / "m24_read_only_adapter.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            "grideval-g7-m24-read-only-adapter-qualification/v1",
        )


if __name__ == "__main__":
    unittest.main()

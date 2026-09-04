from __future__ import annotations

import ast
import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from g7confirm.ia4_counterfactual import (
    M7_METRIC,
    M7_TARGETS,
    build_m7_adapter,
    build_m7_capability_profile,
    build_m7_protocol,
)
from g7confirm.ia4_tool_loop import (
    IAInteractiveSession,
    M5_REAL_ADAPTER_TOOL_RESULT_SCHEMA_VERSION,
    RealAdapterToolResult,
)
from g7confirm.m24_read_only_adapter import (
    EmpiricalSensitivityAdapter,
    build_contract as build_m24_contract,
)
from g7confirm.m25_adapter_transaction import (
    EXPECTED_LEGACY_FIXTURE_RECEIPT_SHA256,
    EXPECTED_LEGACY_FIXTURE_RESULT_SHA256,
    EXPECTED_M7_PROTOCOL_ID,
    EXPECTED_M7_SEARCH_SURFACE_ID,
    FORBIDDEN_CONSUMER_KEYS,
    M25_CODE_PATH,
    _assert_legacy_anchors,
    _legacy_fixture_hashes,
    _run_transaction,
    _tool_request,
    build_contract,
    build_qualification_receipt,
    verify_qualification,
)
from g7confirm.m25_independent_audit import (
    AUDITOR_PATH,
    audit_qualification,
    build_audit_receipt,
    verify_audit_receipt,
)
from g7confirm.orchestration_contract import (
    ContractViolation,
    OrchestrationRung,
    TypedObservation,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
M25_ATTEMPT_ROOT = PACKAGE_ROOT / "artifacts" / "m25_adapter_transaction_attempt1"
FROZEN_ROADMAP_SHA256 = (
    "c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b"
)
FROZEN_SPEC_SHA256 = (
    "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
)
FROZEN_ORCHESTRATION_SHA256 = (
    "2bfb23ffb8e17aac9f4c2ec41755d7cf97b01b1c70fc93cef26a637544294d3b"
)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def readdress_invocation(receipt: dict) -> dict:
    changed = copy.deepcopy(receipt)
    changed.pop("invocation_id", None)
    changed["invocation_id"] = "m24invoke_" + canonical_hash(changed)
    return changed


def make_pending_real_result(
        rung: OrchestrationRung = OrchestrationRung.IA4,
        *, receipt_change=None) -> tuple[IAInteractiveSession, RealAdapterToolResult]:
    protocol = build_m7_protocol(build_m7_adapter())
    session = IAInteractiveSession(
        protocol=protocol,
        profile=build_m7_capability_profile(rung),
        observation=TypedObservation(
            window=0,
            time_s=0,
            values={"context": "m25_test", "candidate_difference": "target_only"},
        ),
        history=(),
        decision_core_id="m25_offline_argmax_replay",
    )
    request = session.next_request()
    session.accept_model_turn(
        request_sha256=request["request_sha256"],
        payload=_tool_request(session),
        model_id=session.decision_core_id,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    outstanding = session.outstanding_request
    assert outstanding is not None
    invocation = EmpiricalSensitivityAdapter(
        contract=build_m24_contract()
    ).invoke(arguments=outstanding.arguments, caller_rung=rung.value)
    receipt = copy.deepcopy(invocation.receipt)
    if receipt_change is not None:
        receipt_change(receipt)
    result = RealAdapterToolResult.build(
        protocol=protocol,
        request=outstanding,
        output=invocation.payload,
        adapter_invocation_receipt=receipt,
        caller_rung=rung,
    )
    return session, result


class M25AdapterTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = build_contract()
        cls.qualification = build_qualification_receipt(cls.contract)

    def test_contract_is_deterministic_and_keeps_every_online_gate_closed(self):
        self.assertEqual(self.contract, build_contract())
        self.assertFalse(self.contract["source_admitted"])
        self.assertFalse(self.contract["campaign_authorized"])
        self.assertFalse(self.contract["evaluation_opened"])
        boundary = self.contract["access_boundary"]
        self.assertTrue(boundary["real_local_read_only_adapter_authorized"])
        for key, value in boundary.items():
            if key.endswith("_authorized") and key != (
                    "real_local_read_only_adapter_authorized"):
                self.assertFalse(value, key)

    def test_M5_and_M7_legacy_bytes_and_identities_are_unchanged(self):
        anchors = _legacy_fixture_hashes()
        self.assertEqual(
            anchors["fixture_result_sha256"],
            EXPECTED_LEGACY_FIXTURE_RESULT_SHA256,
        )
        self.assertEqual(
            anchors["fixture_episode_receipt_sha256"],
            EXPECTED_LEGACY_FIXTURE_RECEIPT_SHA256,
        )
        self.assertEqual(_assert_legacy_anchors(), anchors)
        protocol = build_m7_protocol(build_m7_adapter())
        self.assertEqual(protocol.protocol_id, EXPECTED_M7_PROTOCOL_ID)
        self.assertEqual(
            protocol.adapter.search_surface.search_surface_id,
            EXPECTED_M7_SEARCH_SURFACE_ID,
        )

    def test_real_result_uses_common_atomic_transition(self):
        session, result = make_pending_real_result()
        self.assertEqual(
            result.to_dict()["schema_version"],
            M5_REAL_ADAPTER_TOOL_RESULT_SCHEMA_VERSION,
        )
        session.submit_tool_result(result)
        self.assertEqual(session.turn_index, 1)
        self.assertEqual(len(session.tool_calls), 1)
        receipt = session._transcript[-1]
        self.assertEqual(receipt["event"], "tool_result")
        self.assertEqual(receipt["output"], result.output)

    def test_consumer_event_excludes_all_adapter_provenance(self):
        for rung in (OrchestrationRung.IA3, OrchestrationRung.IA4):
            transaction = _run_transaction(
                rung=rung, m24_contract=build_m24_contract()
            )
            event = transaction["consumer_tool_result_event"]
            encoded = json.dumps(event, sort_keys=True)
            for key in FORBIDDEN_CONSUMER_KEYS:
                self.assertNotIn(key, encoded)
            self.assertEqual(
                set(event["output"]),
                {"schema_version", "window", "time_s", "metric", "values"},
            )
            self.assertEqual(set(event["output"]["values"]), set(M7_TARGETS))

    def test_qualification_has_exact_matched_consumer_parity(self):
        self.assertEqual(self.qualification["status"], "passed")
        self.assertTrue(all(self.qualification["parity"].values()))
        self.assertTrue(all(
            self.qualification["provenance_separation"].values()
        ))
        ia3 = self.qualification["transactions"]["IA3"]
        ia4 = self.qualification["transactions"]["IA4"]
        self.assertEqual(ia3["tool_request"], ia4["tool_request"])
        self.assertEqual(
            ia3["consumer_tool_result_event"],
            ia4["consumer_tool_result_event"],
        )
        self.assertEqual(ia3["selected_target"], ia4["selected_target"])
        self.assertEqual(ia3["selected_target"], "DER_B")

    def test_terminal_receipts_distinguish_real_fixture_and_external_execution(self):
        for transaction in self.qualification["transactions"].values():
            receipt = transaction["session_receipt"]
            self.assertTrue(receipt["tool_execution_used"])
            self.assertTrue(receipt["real_local_read_only_adapter_executed"])
            self.assertFalse(receipt["synthetic_fixture_injected"])
            self.assertFalse(receipt["external_tool_execution_used"])
            self.assertFalse(receipt["model_transport_used"])
            self.assertFalse(receipt["simulator_accessed"])
            self.assertFalse(receipt["detector_accessed"])
            self.assertFalse(receipt["embedding_accessed"])
            self.assertEqual(receipt["accounting"]["outer_rollouts"], 0)

    def test_actual_adapter_reads_exactly_two_upstream_files_per_rung(self):
        expected = [
            "v3/g7_confirmatory/artifacts/"
            "m23_system_identification_seed6101_attempt1/"
            "m23_system_identification.json",
            "v3/g7_confirmatory/artifacts/"
            "m23_system_identification_seed6101_attempt1/"
            "independent_audit_receipt.json",
        ]
        for transaction in self.qualification["transactions"].values():
            self.assertEqual(transaction["actual_files_read"], expected)

    def test_readdressed_invocation_semantic_mutations_fail_closed(self):
        mutations = (
            (
                lambda item: item["access_boundary"].update(
                    network_accessed=True
                ),
                "access boundary",
            ),
            (
                lambda item: item["source_binding"].update(admitted=True),
                "source binding",
            ),
            (
                lambda item: item["audit_binding"].update(status="failed"),
                "audit binding",
            ),
            (
                lambda item: item["side_effects"].update(
                    simulation_time_advance_s=1.0
                ),
                "side-effect",
            ),
            (
                lambda item: item.update(caller_rung="IA3"),
                "caller rung",
            ),
            (
                lambda item: item.update(extra="forbidden"),
                "fields differ",
            ),
        )
        for mutate, expected in mutations:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ContractViolation, expected):
                    make_pending_real_result(
                        receipt_change=lambda item, mutate=mutate: (
                            mutate(item), item.update(readdress_invocation(item))
                        )
                    )

    def test_request_payload_hash_and_self_address_mutations_fail_closed(self):
        mutations = (
            (lambda item: item.update(request_sha256="0" * 64), "request hash"),
            (lambda item: item.update(payload_sha256="0" * 64), "payload hash"),
            (lambda item: item.update(invocation_id="m24invoke_wrong"), "self-address"),
        )
        for mutate, expected in mutations:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ContractViolation, expected):
                    make_pending_real_result(receipt_change=mutate)

    def test_common_session_rejects_real_result_lineage_and_cost_drift(self):
        for field, value, expected in (
            ("call_id", "call_other", "call_id"),
            ("protocol_id", "m5proto_wrong", "protocol_id"),
            ("simulation_time_advance_s", 1.0, "advanced simulation time"),
            ("outer_rollout_cost", 1, "outer rollout"),
        ):
            with self.subTest(field=field):
                session, result = make_pending_real_result()
                with self.assertRaisesRegex(ContractViolation, expected):
                    session.submit_tool_result(replace(result, **{field: value}))
                self.assertEqual(session.state.value, "failed_closed")
                self.assertEqual(session.turn_index, 0)

    def test_real_result_is_defensively_copied_at_acceptance(self):
        session, result = make_pending_real_result()
        session.submit_tool_result(result)
        before = session._tool_results[0].to_dict()
        result.adapter_invocation_receipt["caller_rung"] = "IA3"
        result.output["values"]["DER_A"] = 0.1
        self.assertEqual(session._tool_results[0].to_dict(), before)

    def test_transaction_code_has_no_online_service_imports(self):
        tree = ast.parse(M25_CODE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            {"requests", "httpx", "openai", "docker", "socket"}.isdisjoint(
                imported
            )
        )
        auditor_tree = ast.parse(AUDITOR_PATH.read_text(encoding="utf-8"))
        self.assertFalse(any(
            isinstance(node, ast.ImportFrom) and
            node.module == "m25_adapter_transaction"
            for node in ast.walk(auditor_tree)
        ))

    def test_temporary_artifact_passes_primary_and_independent_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = build_contract()
            receipt = build_qualification_receipt(contract)
            (root / "contract.json").write_text(
                json.dumps(contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (root / "qualification_receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_qualification(root), [])
            self.assertEqual(audit_qualification(root), [])
            audit = build_audit_receipt(root)
            self.assertEqual(audit["status"], "passed")
            self.assertEqual(verify_audit_receipt(root, audit), [])

    def test_independent_audit_detects_consumer_leak_and_access_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = build_contract()
            receipt = build_qualification_receipt(contract)
            transaction = receipt["transactions"]["IA4"]
            transaction["consumer_tool_result_event"][
                "source_binding"
            ] = {"leak": True}
            transaction["session_receipt"][
                "external_tool_execution_used"
            ] = True
            content = copy.deepcopy(receipt)
            content.pop("qualification_id")
            receipt["qualification_id"] = "m25qual_" + canonical_hash(content)
            (root / "contract.json").write_text(
                json.dumps(contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (root / "qualification_receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            issues = audit_qualification(root)
            self.assertIn(
                "transaction:IA4:consumer_event_field_drift", issues
            )
            self.assertIn(
                "transaction:IA4:consumer_provenance_leak:source_binding",
                issues,
            )
            self.assertIn("transaction:IA4:session_access_state_drift", issues)

    def test_checked_in_artifact_passes_both_verifiers(self):
        self.assertEqual(verify_qualification(M25_ATTEMPT_ROOT), [])
        self.assertEqual(audit_qualification(M25_ATTEMPT_ROOT), [])
        audit = json.loads(
            (M25_ATTEMPT_ROOT / "independent_audit_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(verify_audit_receipt(M25_ATTEMPT_ROOT, audit), [])

    def test_schema_is_closed_and_frozen_files_are_unchanged(self):
        schema = json.loads(
            (PACKAGE_ROOT / "m25_adapter_transaction.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            "grideval-g7-m25-adapter-transaction-qualification/v1",
        )
        for path, expected in (
            (PACKAGE_ROOT / "roadmap_2026" / "report.html", FROZEN_ROADMAP_SHA256),
            (PACKAGE_ROOT / "experiment_spec.yaml", FROZEN_SPEC_SHA256),
            (
                PACKAGE_ROOT / "ORCHESTRATION_CONTRACT.md",
                FROZEN_ORCHESTRATION_SHA256,
            ),
        ):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()

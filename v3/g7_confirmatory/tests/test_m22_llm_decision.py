from __future__ import annotations

import json
import unittest
from pathlib import Path

from g7confirm.m22_llm_decision import (
    BASE_URL,
    DEVELOPMENT_SEEDS,
    MODEL_ID,
    build_contract,
    build_receipt,
    verify_receipt,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ATTEMPT_ROOT = PACKAGE_ROOT / "artifacts" / "m22_current_service_regression_attempt1"
ACTION_REQUESTS = (
    ATTEMPT_ROOT / "action_request_seed8105.json",
    ATTEMPT_ROOT / "action_request_seed8106.json",
)


class M22DecisionTests(unittest.TestCase):
    def test_contract_preserves_M7_surface_and_closes_every_live_access(self):
        contract = build_contract(ACTION_REQUESTS)
        self.assertEqual(DEVELOPMENT_SEEDS, (8105, 8106))
        self.assertEqual(MODEL_ID, "qwen3.6-35b-a3b")
        self.assertEqual(BASE_URL, "http://ccil1s26m8hj6lws:8000/v1")
        self.assertTrue(contract["contract_id"].startswith("m22contract_"))
        self.assertEqual(
            contract["exact_M7_interface"]["tool_names"],
            ["observe_sensitivity"],
        )
        self.assertEqual(len(contract["exact_M7_interface"]["candidate_ids"]), 2)
        self.assertEqual(
            [item["selected_target"] for item in contract["matched_ia3_controls"]],
            ["DER_A", "DER_B"],
        )
        self.assertFalse(any(
            value
            for key, value in contract["access_boundary"].items()
            if key != "fixture_injection"
        ))

    def test_receipt_mutation_fails_closed(self):
        contract = build_contract(ACTION_REQUESTS)
        result = {
            "status": "passed",
            "network_requests": 5,
            "completion_requests": 4,
            "qualification": {
                "directional_accuracy": 1.0,
                "candidate_switched": True,
            },
            "tool_execution_used": False,
            "simulator_accessed": False,
            "detector_accessed": False,
            "embedding_accessed": False,
            "evaluation_accessed": False,
        }
        receipt = build_receipt(contract=contract, result=result)
        self.assertEqual(verify_receipt(receipt, contract), [])
        receipt["real_tool_executed"] = True
        issues = verify_receipt(receipt, contract)
        self.assertIn("access_boundary_drift:real_tool_executed", issues)
        self.assertIn("receipt_content_address_drift", issues)

    def test_checked_in_contract_and_receipt_are_current_and_non_actuating(self):
        contract = json.loads(
            (ATTEMPT_ROOT / "contract.json").read_text(encoding="utf-8")
        )
        receipt = json.loads(
            (ATTEMPT_ROOT / "receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract, build_contract(ACTION_REQUESTS))
        self.assertEqual(verify_receipt(receipt, contract), [])
        self.assertEqual(receipt["result"]["network_requests"], 5)
        self.assertEqual(receipt["result"]["completion_requests"], 4)
        self.assertTrue(receipt["result"]["model_transport_used"])
        self.assertFalse(receipt["real_tool_executed"])
        self.assertFalse(receipt["simulator_accessed"])


if __name__ == "__main__":
    unittest.main()

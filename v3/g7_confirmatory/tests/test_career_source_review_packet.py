from __future__ import annotations

import json
import unittest
from pathlib import Path

from g7confirm.career_source_freeze_design import M9_CANDIDATE_IDS, REVIEW_STATUS
from g7confirm.career_source_review_packet import (
    M13_BASE_COMMIT,
    OPEN_STATUS,
    PACKET_STATUS,
    REVIEW_SNAPSHOT,
    SOURCE_REVIEW_PACKET_SCHEMA_VERSION,
    CareerSourceReviewPacket,
    build_career_source_review_packet,
    load_career_source_review_packet,
    packet_id_for,
    verify_review_snapshot,
)
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
ARTIFACT_PATH = (
    PACKAGE_ROOT / "artifacts" / "career_source_review_packet_m14.json"
)
SCHEMA_PATH = PACKAGE_ROOT / "career_source_review_packet.schema.json"
EXPECTED_PACKET_ID = (
    "m14reviewpacket_6efed441aebe881691b3596321ca7255edf67af8d24ef59412be923"
    "e12098b25"
)


def readdress(payload: dict) -> dict:
    payload["packet_id"] = packet_id_for(payload)
    return payload


class CareerSourceReviewPacketTests(unittest.TestCase):
    def test_checked_in_packet_matches_canonical_builder(self):
        built = build_career_source_review_packet()
        stored = load_career_source_review_packet(ARTIFACT_PATH)

        self.assertEqual(stored.to_dict(), built.to_dict())
        self.assertEqual(stored.packet_id, EXPECTED_PACKET_ID)
        self.assertEqual(stored.to_dict()["status"], PACKET_STATUS)

    def test_schema_is_parseable_and_names_packet_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            SOURCE_REVIEW_PACKET_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])

    def test_all_thirteen_review_snapshot_files_match_exact_bytes(self):
        self.assertEqual(len(REVIEW_SNAPSHOT), 13)
        self.assertEqual(verify_review_snapshot(REPO_ROOT), [])

    def test_snapshot_binds_frozen_spec_report_and_M13_commit(self):
        payload = build_career_source_review_packet().to_dict()
        manifest = {
            entry["path"]: entry for entry in payload["exact_review_snapshot"]
        }

        self.assertEqual(
            manifest["v3/g7_confirmatory/experiment_spec.yaml"]["sha256"],
            "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d",
        )
        self.assertEqual(
            manifest["v3/g7_confirmatory/roadmap_2026/report.html"]["sha256"],
            "c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b",
        )
        self.assertEqual(
            payload["source_lineage"]["m13_base_commit"], M13_BASE_COMMIT
        )

    def test_every_prerequisite_is_open_without_evidence(self):
        register = build_career_source_review_packet().to_dict()[
            "prerequisite_register"
        ]

        for items in register.values():
            for item in items:
                self.assertEqual(item["status"], OPEN_STATUS)
                self.assertIsNone(item["evidence_id"])

    def test_generation_envelopes_are_unauthorized_and_numerically_empty(self):
        envelopes = build_career_source_review_packet().to_dict()[
            "proposed_generation_envelopes"
        ]

        for envelope in envelopes.values():
            self.assertEqual(
                envelope["status"], "NOT_AUTHORIZED_REVIEW_PROPOSAL_ONLY"
            )
            self.assertTrue(envelope["numeric_values"])
            self.assertTrue(
                all(value is None for value in envelope["numeric_values"].values())
            )

    def test_M_keeps_exact_candidates_and_unselected_physical_binding(self):
        envelope = build_career_source_review_packet().to_dict()[
            "proposed_generation_envelopes"]["M"]

        self.assertEqual(
            envelope["candidate_binding"]["ordered_candidate_ids"],
            list(M9_CANDIDATE_IDS),
        )
        self.assertIsNone(
            envelope["candidate_binding"]["physical_instantiation_manifest"]
        )
        self.assertIsNone(
            envelope["candidate_binding"]["primary_endpoint_definition"]
        )
        self.assertIsNone(envelope["ranker_constraints"]["algorithm_family"])

    def test_review_dispositions_are_empty_and_self_review_is_disabled(self):
        protocol = build_career_source_review_packet().to_dict()[
            "independent_review_protocol"
        ]

        self.assertFalse(protocol["packet_preparer_may_review"])
        self.assertEqual(protocol["required_distinct_reviewers"], 2)
        for slot in protocol["disposition_slots"]:
            self.assertIsNone(slot["reviewer_id"])
            self.assertIsNone(slot["disposition"])
            self.assertIsNone(slot["comments_sha256"])
            self.assertIsNone(slot["bound_packet_id"])
            self.assertIsNone(slot["receipt_id"])
            self.assertEqual(slot["status"], REVIEW_STATUS)

    def test_readdressed_self_approval_is_rejected(self):
        payload = build_career_source_review_packet().to_dict()
        slot = payload["independent_review_protocol"]["disposition_slots"][0]
        slot["reviewer_id"] = "packet_preparer"
        slot["disposition"] = "accept_exact_packet"

        with self.assertRaisesRegex(ContractViolation, "was populated"):
            CareerSourceReviewPacket(readdress(payload))

    def test_governance_cannot_authorize_source_generation(self):
        payload = build_career_source_review_packet().to_dict()
        payload["governance"]["real_source_generation_authorized"] = True

        with self.assertRaisesRegex(ContractViolation, "governance"):
            CareerSourceReviewPacket(readdress(payload))

    def test_content_address_rejects_unacknowledged_snapshot_mutation(self):
        payload = build_career_source_review_packet().to_dict()
        payload["exact_review_snapshot"][0]["sha256"] = "0" * 64

        with self.assertRaisesRegex(ContractViolation, "packet_id mismatch"):
            CareerSourceReviewPacket(payload)

    def test_packet_readiness_preserves_all_real_holds(self):
        status = build_career_source_review_packet().to_dict()[
            "canonical_status"
        ]

        self.assertEqual(status["packet"], PACKET_STATUS)
        self.assertEqual(status["independent_review"], REVIEW_STATUS)
        self.assertEqual(status["S_source_package"], "UNBUILT_DESIGN_ONLY")
        self.assertEqual(status["M_source_package"], "UNBUILT_DESIGN_ONLY")
        self.assertEqual(status["evaluation"], "SEALED")
        self.assertEqual(status["campaign"], "HOLD")

    def test_next_gate_requires_two_reviews_and_remains_offline(self):
        next_gate = build_career_source_review_packet().to_dict()["next_gate"]

        self.assertTrue(next_gate[
            "requires_two_bound_independent_review_receipts"
        ])
        self.assertEqual(
            next_gate["permitted_without_receipts"], "packet_revision_only"
        )
        self.assertFalse(next_gate["real_source_generation_authorized"])
        self.assertFalse(next_gate["real_partition_assignment_authorized"])
        self.assertFalse(next_gate["model_or_embedding_call"])
        self.assertFalse(next_gate["simulator_or_detector_access"])
        self.assertFalse(next_gate["evaluation_access"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from g7confirm.manifest import OutputExistsError, build_manifest, create_once_json
from g7confirm.model_client import (
    ModelClientError,
    parse_proposal,
    proposal_response_format,
)


class ManifestAndModelTests(unittest.TestCase):
    def test_create_once_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifact.json"
            create_once_json(output, {"value": 1})
            with self.assertRaises(OutputExistsError):
                create_once_json(output, {"value": 2})
            self.assertIn('"value": 1', output.read_text())

    def test_manifest_hashes_files_relative_to_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("immutable\n")
            manifest = build_manifest(root=root, files=[source], metadata={"test": True})
            self.assertEqual(manifest["files"][0]["path"], "source.txt")
            self.assertEqual(len(manifest["files"][0]["sha256"]), 64)

    def test_parse_proposal_accepts_reasoning_prefix(self):
        proposal = parse_proposal(
            'analysis text\n{"amplitude_fraction": 0.1, "period_windows": 4, "rationale": "bounded test"}',
            [0.05, 0.1], [2, 4],
        )
        self.assertEqual(proposal.amplitude_fraction, 0.1)
        self.assertEqual(proposal.period_windows, 4)

    def test_parse_proposal_rejects_off_grid_value(self):
        with self.assertRaisesRegex(ModelClientError, "outside the candidate set"):
            parse_proposal(
                '{"amplitude_fraction": 0.11, "period_windows": 4, "rationale": "x"}',
                [0.05, 0.1], [2, 4],
            )

    def test_parse_proposal_rejects_additional_fields(self):
        with self.assertRaisesRegex(ModelClientError, "exact-contract"):
            parse_proposal(
                '{"amplitude_fraction": 0.1, "period_windows": 4, "rationale": "x", "alarm_hint": 68}',
                [0.05, 0.1], [2, 4],
            )

    def test_parse_proposal_rejects_empty_rationale(self):
        with self.assertRaisesRegex(ModelClientError, "rationale is empty"):
            parse_proposal(
                '{"amplitude_fraction": 0.1, "period_windows": 4, "rationale": ""}',
                [0.05, 0.1], [2, 4],
            )

    def test_response_format_is_strict_and_candidate_constrained(self):
        response_format = proposal_response_format([0.05, 0.1], [2, 4])
        contract = response_format["json_schema"]
        schema = contract["schema"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(contract["strict"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["amplitude_fraction"]["enum"], [0.05, 0.1])
        self.assertEqual(schema["properties"]["period_windows"]["enum"], [2, 4])
        self.assertEqual(schema["properties"]["rationale"]["type"], "string")


if __name__ == "__main__":
    unittest.main()

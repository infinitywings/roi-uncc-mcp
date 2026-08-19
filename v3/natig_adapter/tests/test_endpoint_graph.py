from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path


ADAPTER_DIR = Path(__file__).resolve().parents[1]
GRAPH_PATH = ADAPTER_DIR / "endpoint_graph.json"
VALIDATOR_PATH = ADAPTER_DIR / "validate_endpoint_graph.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_endpoint_graph", VALIDATOR_PATH
)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def load_graph():
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def hostile_edge(
    *,
    edge_id="hostile",
    stream="command",
    stage=99,
    source="controller/der_ev4",
    destination="gateway/der_ev4",
    transport="helics_message",
):
    return {
        "id": edge_id,
        "stream": stream,
        "stage": stage,
        "source": source,
        "destination": destination,
        "transport": transport,
    }


class EndpointGraphTests(unittest.TestCase):
    def assert_graph_fails(self, value, text):
        errors = validator.validate_endpoint_graph(value)
        self.assertTrue(errors)
        self.assertTrue(
            any(text in error for error in errors),
            f"{text!r} not found in {errors!r}",
        )

    def test_canonical_graph_passes_and_is_exactly_minimal(self):
        value = load_graph()
        self.assertEqual(validator.validate_endpoint_graph(value), [])
        endpoints = value["cyber_messages"]["endpoints"]
        self.assertEqual(
            {item["id"] for item in endpoints},
            set(validator.EXPECTED_ENDPOINTS),
        )
        self.assertEqual(len(endpoints), 4)
        self.assertEqual(len(value["cyber_messages"]["edges"]), 6)
        self.assertEqual(
            value["physical_values"]["gridlabd_message_endpoints"], []
        )

    def test_every_edge_source_and_destination_is_declared(self):
        value = load_graph()
        declared = {
            endpoint["id"]
            for endpoint in value["cyber_messages"]["endpoints"]
        }
        self.assertTrue(
            all(
                edge["source"] in declared and edge["destination"] in declared
                for edge in value["cyber_messages"]["edges"]
            )
        )

    def test_banned_legacy_endpoints_fail_closed(self):
        for bad_name in (
            "CC/Monitor",
            "ns3/fout",
            "natig/trip_shad_inv1$Pref",
        ):
            with self.subTest(bad_name=bad_name):
                value = load_graph()
                value["cyber_messages"]["endpoints"][0]["id"] = bad_name
                self.assert_graph_fails(value, "banned endpoint")

    def test_undeclared_destination_fails_closed(self):
        value = load_graph()
        value["cyber_messages"]["edges"][0]["destination"] = "natig/missing"
        self.assert_graph_fails(
            value, "destination is not a declared cyber endpoint"
        )

    def test_direct_controller_to_gateway_bypass_fails_closed(self):
        value = load_graph()
        value["cyber_messages"]["edges"].append(hostile_edge())
        self.assert_graph_fails(
            value, "forbidden direct controller-to-gateway edge"
        )

    def test_natig_to_gridlabd_bypass_fails_closed(self):
        value = load_graph()
        value["cyber_messages"]["edges"].append(
            hostile_edge(
                source="natig/der_ev4",
                destination="gridlabd/der_coupling_load",
            )
        )
        self.assert_graph_fails(value, "physical/GridLAB-D namespace")

    def test_cyber_message_to_physical_value_fails_closed(self):
        for destination in (
            "gridlabd/ev4_voltage_c",
            "gateway/feeder_load_va",
        ):
            with self.subTest(destination=destination):
                value = load_graph()
                value["cyber_messages"]["edges"].append(
                    hostile_edge(destination=destination)
                )
                self.assert_graph_fails(
                    value, "physical/GridLAB-D namespace"
                )

    def test_gridlabd_cannot_own_a_cyber_message_endpoint(self):
        value = load_graph()
        endpoint = value["cyber_messages"]["endpoints"][0]
        endpoint["id"] = "gridlabd/command"
        endpoint["owner"] = "gridlabd"
        self.assert_graph_fails(
            value, "GridLAB-D may not own a message endpoint"
        )

    def test_nonempty_declared_gridlabd_endpoints_fail_closed(self):
        value = load_graph()
        value["physical_values"]["gridlabd_message_endpoints"] = [
            "gridlabd/command"
        ]
        self.assert_graph_fails(value, "zero message endpoints")

    def test_physical_plane_cannot_be_retyped_as_messages(self):
        value = load_graph()
        value["physical_values"]["transport"] = "helics_message"
        self.assert_graph_fails(
            value, "physical_values.transport must be helics_value"
        )

    def test_cyber_owner_cannot_participate_in_physical_value_link(self):
        for side, owner in (
            ("publisher", "natig"),
            ("subscriber", "controller"),
        ):
            with self.subTest(side=side, owner=owner):
                value = load_graph()
                value["physical_values"]["links"][0][side] = owner
                self.assert_graph_fails(value, "cyber owner")

    def test_missing_required_dnp3_edge_fails_closed(self):
        value = load_graph()
        del value["cyber_messages"]["edges"][1]
        self.assert_graph_fails(
            value, "directed command/telemetry edge set must be exact"
        )

    def test_duplicate_endpoint_and_edge_fail_closed(self):
        value = load_graph()
        value["cyber_messages"]["endpoints"].append(
            deepcopy(value["cyber_messages"]["endpoints"][0])
        )
        value["cyber_messages"]["edges"].append(
            deepcopy(value["cyber_messages"]["edges"][0])
        )
        errors = validator.validate_endpoint_graph(value)
        self.assertIn("cyber endpoint ids must be unique", errors)
        self.assertIn("cyber edge ids must be unique", errors)
        self.assertIn("cyber directed edge tuples must be unique", errors)

    def test_policy_removal_fails_closed(self):
        value = load_graph()
        del value["policies"]["forbidden_direct_edges"]
        self.assert_graph_fails(value, "policies must exactly retain")

    def test_external_gridlabd_config_accepts_empty_or_missing_endpoints(self):
        self.assertEqual(
            validator.validate_gridlabd_physical_config({"endpoints": []}),
            [],
        )
        self.assertEqual(
            validator.validate_gridlabd_physical_config(
                {
                    "publications": [
                        {"key": "gridlabd/ev4_voltage_c"}
                    ]
                }
            ),
            [],
        )

    def test_external_gridlabd_config_rejects_nonempty_endpoints(self):
        config = {
            "federates": [
                {
                    "name": "gridlabd",
                    "endpoints": [{"name": "gridlabd/direct_command"}],
                }
            ]
        }
        errors = validator.validate_gridlabd_physical_config(config)
        self.assertEqual(len(errors), 1)
        self.assertIn("must be empty; found 1 message endpoint", errors[0])


if __name__ == "__main__":
    unittest.main()

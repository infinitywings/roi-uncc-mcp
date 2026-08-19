from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from v3.natig_adapter.run_live_direct import (
    DEFAULT_CONTRACT,
    DEFAULT_IMAGE_MANIFEST,
    PreflightError,
    load_json,
    prepare,
    validate_contract,
)

sys.modules.setdefault("helics", SimpleNamespace())

from v3.natig_adapter.live_direct.live_controller_federate import (  # noqa: E402
    semantic_command,
)
from v3.natig_adapter.live_direct.live_gateway_federate import (  # noqa: E402
    validate_direct_wire,
)


def test_canonical_direct_contract_passes_static_preflight():
    contract = load_json(DEFAULT_CONTRACT)
    assert validate_contract(contract, DEFAULT_CONTRACT) == []


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: value["broker"].__setitem__("federate_count", 4),
        lambda value: value["federates"].append(
            {
                "owner": "natig",
                "name": "forbidden",
                "config": "natig.json",
            }
        ),
        lambda value: value["security_condition"][
            "attacker_processes"
        ].append("attacker"),
        lambda value: value["cyber_routes"].pop(),
        lambda value: value["source_locks"][0].__setitem__(
            "sha256", "0" * 64
        ),
    ),
)
def test_direct_contract_mutations_fail_closed(mutation):
    contract = deepcopy(load_json(DEFAULT_CONTRACT))
    mutation(contract)
    assert validate_contract(contract, DEFAULT_CONTRACT)


def test_direct_dry_run_stages_canonical_arm_create_once(tmp_path):
    output = tmp_path / "direct-preflight"
    result = prepare(output_dir=output)
    assert result["static_preflight"] == "PASS"
    assert result["image_preflight"] == "READY"
    assert result["execution_attempted"] is False
    assert result["federate_count"] == 3
    assert result["cyber_endpoint_count"] == 2
    assert result["cyber_route_count"] == 2
    assert result["physical_value_link_count"] == 2
    assert result["gridlabd_message_endpoint_count"] == 0
    assert result["attacker_process_count"] == 0
    assert result["network_impairment_count"] == 0
    assert (output / "live_direct_preflight.json").is_file()
    assert (
        output / "effective/runtime/live_controller_federate.py"
    ).is_file()
    assert (
        output / "effective/runtime/live_gateway_federate.py"
    ).is_file()
    assert (output / "effective/model/mainglm.json").read_bytes() == (
        DEFAULT_CONTRACT.parent.parent / "live_benign/gridlabd.json"
    ).read_bytes()
    assert (
        load_json(output / "effective/model/mainglm.json")["endpoints"]
        == []
    )
    assert (
        output / "live_image_manifest.json"
    ).read_bytes() == DEFAULT_IMAGE_MANIFEST.read_bytes()
    with pytest.raises(FileExistsError):
        prepare(output_dir=output)


def test_direct_runner_rejects_manifest_substitution_even_if_bytes_match(
    tmp_path,
):
    substituted = tmp_path / "copied-manifest.json"
    substituted.write_bytes(DEFAULT_IMAGE_MANIFEST.read_bytes())
    with pytest.raises(
        PreflightError, match="only the immutable r24-derived manifest"
    ):
        prepare(
            output_dir=tmp_path / "direct",
            image_manifest_path=substituted,
        )


def test_direct_wire_accepts_only_exact_canonical_semantic_envelope():
    semantic = semantic_command(
        point_index=0,
        value=10.0,
        event_time_s=60.0,
        sequence=2,
    )
    wire = {
        "wire_schema": "grideval-g4-live-direct-command/1.0",
        "operation": "select_operate",
        "point_index": 0,
        "semantic_message": semantic,
    }
    point_index, validated = validate_direct_wire(wire)
    assert point_index == 0
    assert validated == semantic
    assert validated is not semantic

    for mutation in (
        lambda value: value.__setitem__("operation", "operate"),
        lambda value: value.__setitem__("extra", True),
        lambda value: value["semantic_message"].__setitem__(
            "source", "forged"
        ),
        lambda value: value["semantic_message"]["payload"].__setitem__(
            "quality", ["online", "stale"]
        ),
        lambda value: value.__setitem__("point_index", True),
    ):
        malformed = deepcopy(wire)
        mutation(malformed)
        with pytest.raises(ValueError):
            validate_direct_wire(malformed)


def test_preflight_json_has_exact_reader_contract(tmp_path):
    output = tmp_path / "direct-preflight"
    prepare(output_dir=output)
    evidence = json.loads(
        (output / "live_direct_preflight.json").read_text(encoding="utf-8")
    )
    assert set(evidence) == {
        "schema_version",
        "scope",
        "mode",
        "static_preflight",
        "image_preflight",
        "image_errors",
        "image_evidence",
        "execution_attempted",
        "execution_result",
        "claims_permitted",
        "equivalence_claim_permitted",
        "seed",
        "federate_count",
        "cyber_endpoint_count",
        "cyber_route_count",
        "physical_value_link_count",
        "gridlabd_message_endpoint_count",
        "attacker_process_count",
        "network_impairment_count",
        "effective_inventory",
    }

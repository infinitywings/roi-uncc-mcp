from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from v3.natig_adapter.analyze_live_equivalence import validate_execution
from v3.natig_adapter.normalize_g3_direct_reference import (
    CROSS_VERSION_QUALIFICATION,
    CURRENT_RUNNER_SHA256,
    EXPECTED_ARTIFACTS,
    EXPECTED_ASSERTIONS,
    EXPECTED_IDENTITY,
    PRODUCING_RUNNER_SHA256,
    SOURCE_SHA256,
    NormalizationError,
    normalize,
    sha256,
    validate_document,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE = (
    REPO_ROOT
    / "v3"
    / "opender_federate"
    / "pulse_coupling10_r3"
    / "g3_physical_loop.json"
)
NORMALIZER = (
    REPO_ROOT / "v3" / "natig_adapter" / "normalize_g3_direct_reference.py"
)


def source_document() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_exact_pinned_artifact_normalizes_without_claiming_new_execution():
    assert sha256(SOURCE) == SOURCE_SHA256
    trace = normalize(source=SOURCE, repo_root=REPO_ROOT)
    errors, _normalized = validate_execution(
        trace, expected_path="direct_reference"
    )
    assert errors == []
    assert len(trace["commands"]) == 18
    assert len(trace["applications"]) == 18
    assert len(trace["samples"]) == 84
    assert trace["provenance"]["normalization"]["is_new_execution"] is False
    assert CROSS_VERSION_QUALIFICATION in trace["provenance"][
        "comparison_qualifications"
    ]
    assert trace["provenance"]["producer"] == {
        "runner_sha256": PRODUCING_RUNNER_SHA256,
        "helics_version": "3.6.1 (2025-02-24)",
        "opender_version": "2.2.0",
    }
    assert trace["commands"][0]["accepted_time_s"] == 10.0
    assert trace["applications"][0]["applied_time_s"] == 10.0
    assert trace["commands"][2]["accepted_time_s"] == 60.0


def test_producing_runner_identity_is_not_replaced_by_current_runner():
    document = source_document()
    assert document["identity"]["runner_sha256"] == PRODUCING_RUNNER_SHA256
    assert sha256(
        REPO_ROOT / "v3/opender_federate/run_physical_loop.py"
    ) == CURRENT_RUNNER_SHA256
    assert PRODUCING_RUNNER_SHA256 != CURRENT_RUNNER_SHA256


def test_mutated_source_bytes_fail_before_normalization(tmp_path):
    mutated = tmp_path / "g3_physical_loop.json"
    mutated.write_bytes(SOURCE.read_bytes() + b"\n")
    with pytest.raises(NormalizationError, match="source trace SHA-256"):
        normalize(source=mutated, repo_root=REPO_ROOT)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.__setitem__("scenario", "null"), "scenario"),
        (
            lambda value: value["identity"].__setitem__(
                "runner_sha256", "0" * 64
            ),
            "identity locks",
        ),
        (
            lambda value: value["assertions"].__setitem__(
                next(iter(EXPECTED_ASSERTIONS)), False
            ),
            "assertion",
        ),
        (
            lambda value: value["schedule"].__delitem__(0),
            "schedule",
        ),
        (
            lambda value: value["adapter_trace"].__delitem__(4),
            "84 adapter rows",
        ),
        (
            lambda value: value["adapter_trace"][5].__setitem__(
                "desired_p_kw", -10.0
            ),
            "source schedule",
        ),
        (
            lambda value: value["process"].__setitem__(
                "gridlabd_returncode", 1
            ),
            "did not complete",
        ),
        (
            lambda value: value["artifacts"].__setitem__(
                "gridlabd.log", {"sha256": "0" * 64, "bytes": 1}
            ),
            "artifact lock table",
        ),
    ],
)
def test_hostile_document_mutations_fail_closed(mutation, message):
    document = source_document()
    mutation(document)
    with pytest.raises(NormalizationError, match=message):
        validate_document(
            document,
            bundle_dir=SOURCE.parent,
            repo_root=REPO_ROOT,
        )


def test_companion_artifact_byte_drift_is_rejected(tmp_path):
    bundle = tmp_path / "bundle"
    shutil.copytree(SOURCE.parent, bundle)
    target = bundle / "gridlabd.log"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(NormalizationError, match="artifact drift"):
        validate_document(
            source_document(),
            bundle_dir=bundle,
            repo_root=REPO_ROOT,
        )


def test_every_companion_lock_is_reverified_and_recorded():
    trace = normalize(source=SOURCE, repo_root=REPO_ROOT)
    metadata = {
        item["path"]: (item["sha256"], item["bytes"])
        for item in trace["provenance"]["source_artifacts"]
    }
    for relative, expected in EXPECTED_ARTIFACTS.items():
        path = f"v3/opender_federate/pulse_coupling10_r3/{relative}"
        assert metadata[path] == (expected["sha256"], expected["bytes"])
    assert EXPECTED_IDENTITY["source_glm_sha256"] in {
        value[0] for value in metadata.values()
    }


def test_cli_is_create_once_and_reports_no_equivalence_claim(tmp_path):
    output = tmp_path / "direct_reference_trace.json"
    command = [
        sys.executable,
        NORMALIZER,
        "--source",
        SOURCE,
        "--repo-root",
        REPO_ROOT,
        "--output",
        output,
    ]
    first = subprocess.run(
        [str(item) for item in command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0
    status = json.loads(first.stdout)
    assert status["status"] == "normalized_existing_execution"
    assert status["equivalence_claim_permitted"] is False
    assert output.is_file()

    second = subprocess.run(
        [str(item) for item in command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode != 0
    assert "refusing existing output" in second.stderr

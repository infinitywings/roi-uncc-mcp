from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from v3.natig_adapter.analyze_live_equivalence import (
    EXPECTED_COMMANDS,
    EXPECTED_SAMPLE_TIMES,
    TRACE_SCHEMA,
    Tolerances,
    analyze_equivalence,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYZER = REPO_ROOT / "v3" / "natig_adapter" / "analyze_live_equivalence.py"


def synthetic_trace(path: str) -> dict:
    path_offset = 0.2 if path == "direct_reference" else 1.2
    apply_offset = 1.0 if path == "direct_reference" else 2.0
    commands = []
    applications = []
    for expected in EXPECTED_COMMANDS:
        key = expected["schedule_key"]
        command_id = f"{path}-{key}-command"
        application_id = f"{path}-{key}-application"
        commands.append(
            {
                **expected,
                "accepted": True,
                "accepted_time_s": expected["event_time_s"] + path_offset,
                "command_id": command_id,
                "application_id": application_id,
            }
        )
        applications.append(
            {
                "application_id": application_id,
                "command_id": command_id,
                "schedule_key": key,
                "point_index": expected["point_index"],
                "value": expected["value"],
                "unit": expected["unit"],
                "applied_time_s": expected["event_time_s"] + apply_offset,
            }
        )
    samples = [
        {
            "time_s": time_s,
            "p_kw": float((time_s // 60) % 3 - 1),
            "q_kvar": float((time_s // 120) % 3 - 1),
            "voltage_pu": 1.0,
            "soc_pu": 0.5 - time_s / 100_000.0,
        }
        for time_s in EXPECTED_SAMPLE_TIMES
    ]
    return {
        "schema_version": TRACE_SCHEMA,
        "path": path,
        "execution": {
            "status": "complete",
            "start_time_s": 0.0,
            "end_time_s": 840.0,
            "duration_s": 840.0,
        },
        "provenance": {
            "source_artifacts": [
                {
                    "path": f"/synthetic/{path}.json",
                    "sha256": "a" * 64,
                    "bytes": 1,
                }
            ],
            "producer": {
                "runner_sha256": "b" * 64,
                "helics_version": "test-only",
                "opender_version": "test-only",
            },
            "normalization": {
                "normalizer_sha256": "c" * 64,
                "method": "synthetic test fixture",
                "is_new_execution": False,
            },
            "field_provenance": {
                "observed": ["synthetic samples"],
                "derived": ["synthetic command lineage"],
            },
            "comparison_qualifications": [],
        },
        "commands": commands,
        "applications": applications,
        "samples": samples,
    }


def assert_execution_failure(report: dict) -> None:
    assert report["execution"]["status"] == "FAIL"
    assert report["equivalence"]["status"] == "NOT_EVALUATED"
    assert report["equivalence_claim_permitted"] is False


def test_synthetic_paired_840s_18_operation_trace_passes():
    report = analyze_equivalence(
        synthetic_trace("direct_reference"),
        synthetic_trace("natig"),
    )
    assert report["execution"]["status"] == "PASS"
    assert report["equivalence"]["status"] == "PASS"
    assert report["equivalence_claim_permitted"] is True
    assert report["equivalence"]["metrics"][
        "natig_application_latency_s"
    ] == pytest.approx(2.0)
    assert report["equivalence"]["metrics"][
        "application_latency_delta_s"
    ] == pytest.approx(1.0)


@pytest.mark.parametrize("collection", ["commands", "applications", "samples"])
def test_missing_rows_fail_execution_and_skip_equivalence(collection):
    natig = synthetic_trace("natig")
    natig[collection].pop(4)
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert_execution_failure(report)
    assert any(
        "exactly" in error
        for error in report["execution"]["natig_errors"]
    )


def test_extra_command_fails_as_not_an_equivalence_comparison():
    natig = synthetic_trace("natig")
    natig["commands"].append(deepcopy(natig["commands"][-1]))
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert_execution_failure(report)
    assert any(
        "exactly 18" in error
        for error in report["execution"]["natig_errors"]
    )


def test_reordered_commands_fail_the_frozen_schedule():
    natig = synthetic_trace("natig")
    natig["commands"][0], natig["commands"][1] = (
        natig["commands"][1],
        natig["commands"][0],
    )
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert_execution_failure(report)
    assert any(
        "paired 840s schedule" in error
        for error in report["execution"]["natig_errors"]
    )


def test_mismatched_accepted_command_value_fails_execution():
    natig = synthetic_trace("natig")
    natig["commands"][5]["value"] = 4.0
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert_execution_failure(report)
    assert any(
        ".value violates paired 840s schedule" in error
        for error in report["execution"]["natig_errors"]
    )


def test_broken_application_lineage_fails_execution():
    natig = synthetic_trace("natig")
    natig["applications"][3]["command_id"] = "wrong-command"
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert_execution_failure(report)
    assert any(
        "breaks application lineage" in error
        for error in report["execution"]["natig_errors"]
    )


def test_delayed_application_executes_but_fails_equivalence():
    natig = synthetic_trace("natig")
    natig["applications"][7]["applied_time_s"] = (
        natig["commands"][7]["event_time_s"] + 12.001
    )
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert report["execution"]["status"] == "PASS"
    assert report["equivalence"]["status"] == "FAIL"
    assert report["equivalence_claim_permitted"] is False
    assert any(
        "application latency exceeds bound" in error
        for error in report["equivalence"]["errors"]
    )


@pytest.mark.parametrize(
    ("field", "difference", "error_fragment"),
    [
        ("p_kw", 0.0011, "p_kw difference"),
        ("q_kvar", 0.0011, "q_kvar difference"),
        ("voltage_pu", 0.00011, "voltage_pu difference"),
        ("soc_pu", 0.0000011, "soc_pu difference"),
    ],
)
def test_physical_mismatch_fails_equivalence(field, difference, error_fragment):
    natig = synthetic_trace("natig")
    natig["samples"][20][field] += difference
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert report["execution"]["status"] == "PASS"
    assert report["equivalence"]["status"] == "FAIL"
    assert any(
        error_fragment in error for error in report["equivalence"]["errors"]
    )


def test_unaccepted_operation_fails_execution():
    natig = synthetic_trace("natig")
    natig["commands"][0]["accepted"] = False
    report = analyze_equivalence(
        synthetic_trace("direct_reference"), natig
    )
    assert_execution_failure(report)


def test_tolerances_must_be_explicitly_finite_and_nonnegative():
    with pytest.raises(ValueError, match="finite and nonnegative"):
        analyze_equivalence(
            synthetic_trace("direct_reference"),
            synthetic_trace("natig"),
            tolerances=Tolerances(p_abs_kw=-1.0),
        )


def test_cross_version_comparison_requires_exact_qualification():
    direct = synthetic_trace("direct_reference")
    natig = synthetic_trace("natig")
    direct["provenance"]["producer"]["helics_version"] = "3.6.1"
    natig["provenance"]["producer"]["helics_version"] = "2.7.1"
    report = analyze_equivalence(direct, natig)
    assert report["execution"]["status"] == "PASS"
    assert report["equivalence"]["status"] == "FAIL"
    assert any(
        "without exact cross-version" in error
        for error in report["equivalence"]["errors"]
    )

    qualification = (
        "cross-version HELICS comparison: "
        "direct_reference=3.6.1; natig=2.7.1"
    )
    direct["provenance"]["comparison_qualifications"].append(qualification)
    qualified = analyze_equivalence(direct, natig)
    assert qualified["equivalence"]["status"] == "PASS"
    assert qualification in qualified["comparison_qualifications"]


def test_cli_writes_create_once_pass_report_from_synthetic_inputs(tmp_path):
    direct = tmp_path / "direct.json"
    natig = tmp_path / "natig.json"
    report = tmp_path / "report.json"
    direct.write_text(json.dumps(synthetic_trace("direct_reference")))
    natig.write_text(json.dumps(synthetic_trace("natig")))
    result = subprocess.run(
        [
            sys.executable,
            ANALYZER,
            "--direct-trace",
            direct,
            "--natig-trace",
            natig,
            "--output",
            report,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    parsed = json.loads(report.read_text())
    assert parsed["equivalence_claim_permitted"] is True
    assert parsed["input_traces"]["direct_reference"]["sha256"]
    assert parsed["input_traces"]["natig"]["sha256"]
    assert parsed["equivalence"]["metrics"]["accepted_operation_count"] == 18
    assert parsed["equivalence"]["metrics"]["paired_sample_count"] == 84

    refused = subprocess.run(
        [
            sys.executable,
            ANALYZER,
            "--direct-trace",
            direct,
            "--natig-trace",
            natig,
            "--output",
            report,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0
    assert "refusing existing output" in refused.stderr


def test_invalid_json_fails_closed_and_does_not_evaluate_equivalence(tmp_path):
    direct = tmp_path / "direct.json"
    natig = tmp_path / "natig.json"
    direct.write_text("{", encoding="utf-8")
    natig.write_text(json.dumps(synthetic_trace("natig")), encoding="utf-8")
    from v3.natig_adapter.analyze_live_equivalence import analyze_files

    report = analyze_files(direct, natig)
    assert_execution_failure(report)
    assert report["execution"]["direct_reference_errors"]

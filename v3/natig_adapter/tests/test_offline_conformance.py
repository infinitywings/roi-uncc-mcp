from __future__ import annotations

from v3.natig_adapter.run_offline_conformance import (
    DURATION_S,
    FLOAT32_RESIDUAL_BOUNDS,
    SCHEDULE_WINDOWS,
    SCOPE,
    TRACE_ABS_TOLERANCE,
    run_experiment,
)


def test_full_offline_adapter_conformance_and_repeatability():
    artifact = run_experiment()
    assert artifact["verdict"] == "PASS"
    assert artifact["scope"] == SCOPE
    assert artifact["repeatability"]["runs"] == 2
    assert artifact["repeatability"]["exact_canonical_match"] is True

    result = artifact["result"]
    metrics = result["metrics"]
    assert len(result["schedule"]) == len(SCHEDULE_WINDOWS) == 9
    assert metrics["commands_per_path"] == 18
    assert metrics["lifecycle_records"] == 36
    assert metrics["steps_per_path"] == DURATION_S == 840
    assert metrics["analog_telemetry_objects_encoded_decoded"] == 3360
    assert metrics["binary_telemetry_objects_encoded_decoded"] == 1680
    assert metrics["telemetry_objects_encoded_decoded"] == 5040
    assert len(result["command_roundtrips"]) == 18
    assert len(result["direct_trace"]) == 840
    assert len(result["dnp3_trace"]) == 840
    assert len(result["dnp3_telemetry_trace"]) == 840
    assert all(
        row["binary_points"]["BI0"]["decoded_value"] is True
        and row["binary_points"]["BI1"]["decoded_value"] is True
        for row in result["dnp3_telemetry_trace"]
    )

    assert all(
        record["select_status"] == "selected"
        and record["operate_status"] == "accepted"
        and record["sink_status"] == "queued"
        and record["application_status"] == "applied"
        and record["accept_to_apply_s"] == 1.0
        for record in result["lifecycle"]
    )
    assert all(
        value <= TRACE_ABS_TOLERANCE
        for value in metrics["trace_max_abs_difference"].values()
    )
    assert all(
        metrics["telemetry_max_abs_residual"][key] <= bound
        for key, bound in FLOAT32_RESIDUAL_BOUNDS.items()
    )

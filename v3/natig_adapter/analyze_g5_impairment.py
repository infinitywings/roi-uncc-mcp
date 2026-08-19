#!/usr/bin/env python3
"""G5 impairment metric extractor (screening tier).

Reads one G5 impairment run and a paired baseline (the 0 ms control or the G4
benign run) and reports the protocol-Section-8 screening metrics WITHOUT bending
the frozen G4 equivalence analyzer: DNP3 command-lifecycle counts (SELECT/OPERATE
accepted vs rejected + reasons), applied-fraction, and the physical departure
from baseline (per-step dP/dQ/dV, integrated control error, divergent-step count).

Usage:
    PYTHONPATH=. python3 v3/natig_adapter/analyze_g5_impairment.py \
        --run-dir  v3/natig_adapter/g5_impairment_delay200ms_r2 \
        --baseline-dir v3/natig_adapter/g5_impairment_delay0ms_r1 \
        --output   v3/natig_adapter/g5_impairment_delay200ms_r2/g5_metrics.json
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

COUPLING_S = 10.0  # physical coupling step, for time integration


def _gateway(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "runtime_output" / "gateway_trace.json").read_text())


def _lifecycle(trace: dict[str, Any]) -> dict[str, Any]:
    reasons: collections.Counter = collections.Counter()
    for cmd in trace.get("commands", []):
        res = cmd.get("result", {})
        gr = res.get("gateway_result", {}) if isinstance(res, dict) else {}
        reasons[gr.get("reason") or res.get("reason") or res.get("adapter_decision")] += 1
    steps = trace.get("steps", [])
    return {
        "command_message_count": trace.get("command_message_count"),
        "select_accepted": reasons.get("select_accepted", 0),
        "operate_accepted": reasons.get("operate_accepted", 0),
        "reason_distribution": dict(reasons),
        "applied_steps": sum(1 for s in steps if s.get("applied")),
        "step_count": len(steps),
    }


def _physical_delta(base: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    bs, rs = base.get("steps", []), run.get("steps", [])
    if len(bs) != len(rs):
        return {"error": f"step-count mismatch base={len(bs)} run={len(rs)}"}
    n_div = 0
    max_dp = max_dq = max_dv = 0.0
    int_dp = int_dq = 0.0
    sum_dv = 0.0
    for sb, sr in zip(bs, rs):
        dp = abs(sr.get("p_out_kw", 0.0) - sb.get("p_out_kw", 0.0))
        dq = abs(sr.get("q_out_kvar", 0.0) - sb.get("q_out_kvar", 0.0))
        dv = abs(sr.get("terminal_voltage_v", 0.0) - sb.get("terminal_voltage_v", 0.0))
        if dp > 1e-6 or dq > 1e-6:
            n_div += 1
        max_dp, max_dq, max_dv = max(max_dp, dp), max(max_dq, dq), max(max_dv, dv)
        int_dp += dp * COUPLING_S
        int_dq += dq * COUPLING_S
        sum_dv += dv
    return {
        "divergent_steps": n_div,
        "total_steps": len(bs),
        "max_abs_dp_kw": round(max_dp, 6),
        "max_abs_dq_kvar": round(max_dq, 6),
        "max_abs_dv_v": round(max_dv, 6),
        "integrated_abs_dp_kw_s": round(int_dp, 3),
        "integrated_abs_dq_kvar_s": round(int_dq, 3),
        "summed_abs_dv_v": round(sum_dv, 4),
    }


def analyze(run_dir: Path, baseline_dir: Path) -> dict[str, Any]:
    run_tr, base_tr = _gateway(run_dir), _gateway(baseline_dir)
    base_life = _lifecycle(base_tr)
    run_life = _lifecycle(run_tr)
    summary = json.loads((run_dir / "g5_impairment_summary.json").read_text()) \
        if (run_dir / "g5_impairment_summary.json").is_file() else {}
    return {
        "schema_version": "grideval-g5-impairment-metrics/1.0",
        "run_dir": str(run_dir),
        "baseline_dir": str(baseline_dir),
        "impairment": summary.get("impairment"),
        "cyber_lifecycle": {"baseline": base_life, "impaired": run_life},
        "operates_dropped": base_life["operate_accepted"] - run_life["operate_accepted"],
        "operate_accept_fraction": (
            run_life["operate_accepted"] / base_life["operate_accepted"]
            if base_life["operate_accepted"] else None
        ),
        "physical_departure_from_baseline": _physical_delta(base_tr, run_tr),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--baseline-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    report = analyze(args.run_dir.resolve(), args.baseline_dir.resolve())
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

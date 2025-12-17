#!/usr/bin/env python3
"""Analyze experiment results and produce summary statistics."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def load_results(results_dir: Path) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for result_file in results_dir.rglob("results.json"):
        with result_file.open() as f:
            data = json.load(f)
        data["source_file"] = str(result_file)
        results.append(data)
    return results


def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_condition: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        attacker = r.get("attacker_type", "unknown")
        name = r.get("experiment_name", "").lower()
        if "ai" in name or "timing" in name:
            attacker = "ai"
        elif "random" in name:
            attacker = "random"
        elif "baseline" in name:
            attacker = "baseline"

        interval = 60
        for token in name.split("_"):
            if token.startswith("ctrl"):
                try:
                    interval = int(token.replace("ctrl", "").replace("s", ""))
                except ValueError:
                    pass
        condition = f"{attacker}_{interval}s"
        by_condition[condition].append(r)

    summary: Dict[str, Any] = {}
    for condition, runs in by_condition.items():
        success_rates = [r.get("success_rate", 0) for r in runs]
        tvd = [r.get("total_violation_duration_sec", 0) for r in runs]
        attacks = [r.get("total_attacks", 0) for r in runs]

        summary[condition] = {
            "n_runs": len(runs),
            "success_rate": {
                "mean": statistics.mean(success_rates) if success_rates else 0,
                "std": statistics.stdev(success_rates) if len(success_rates) > 1 else 0,
                "values": success_rates,
            },
            "violation_duration_sec": {
                "mean": statistics.mean(tvd) if tvd else 0,
                "std": statistics.stdev(tvd) if len(tvd) > 1 else 0,
                "values": tvd,
            },
            "total_attacks": {
                "mean": statistics.mean(attacks) if attacks else 0,
                "values": attacks,
            },
        }
    return summary


def compute_evaluation_gap(summary: Dict[str, Any]) -> Dict[str, Any]:
    gaps: Dict[str, Any] = {}
    for interval in [30, 60, 120]:
        ai_key = f"ai_{interval}s"
        random_key = f"random_{interval}s"
        if ai_key in summary and random_key in summary:
            ai_tvd = summary[ai_key]["violation_duration_sec"]["mean"]
            random_tvd = summary[random_key]["violation_duration_sec"]["mean"]
            ratio = ai_tvd / random_tvd if random_tvd > 0 else float("inf")
            gaps[f"gap_{interval}s"] = {
                "ai_tvd": ai_tvd,
                "random_tvd": random_tvd,
                "ratio": ratio,
                "interpretation": f"AI achieves {ratio:.1f}x the violation duration of random at {interval}s",
            }
    return gaps


def generate_latex_table(summary: Dict[str, Any]) -> str:
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Attack effectiveness by attacker type and controller interval}",
        r"\label{tab:results}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Condition & Success Rate (\%) & TVD (sec) & Attacks \\",
        r"\midrule",
    ]
    for condition in sorted(summary.keys()):
        stats = summary[condition]
        sr = stats["success_rate"]
        tvd = stats["violation_duration_sec"]
        attacks = stats["total_attacks"]
        lines.append(
            f"{condition} & {sr['mean']:.1f} $\\pm$ {sr['std']:.1f} & "
            f"{tvd['mean']:.0f} $\\pm$ {tvd['std']:.0f} & {attacks['mean']:.0f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze experiment results")
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results = load_results(results_dir)
    summary = analyze_results(results)
    gaps = compute_evaluation_gap(summary)
    latex_table = generate_latex_table(summary)

    output = {"summary": summary, "evaluation_gap": gaps, "latex_table": latex_table}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"Loaded {len(results)} experiment results")
    for gap_name, gap_data in gaps.items():
        print(f"{gap_name}: {gap_data['interpretation']}")
    print("\n=== LaTeX Table ===")
    print(latex_table)


if __name__ == "__main__":
    main()

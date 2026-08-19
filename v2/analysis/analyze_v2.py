#!/usr/bin/env python3
"""
LLM-GridEval v2 — Results Analyzer

Groups by attacker variant (random, ai_v1, ai_v2) and computes:
  - Summary statistics (TVD, ASR, PHAR, MACP, unique EVs, efficiency)
  - Hypothesis tests (V2>Random, V2>V1, diversification, EVG)
  - Effect sizes (Cohen's d)

Usage:
  python v2/analysis/analyze_v2.py --results-dir v2/results/phase2
  python v2/analysis/analyze_v2.py --results-dir v2/results/phase3 --output v2/results/analysis/phase3.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@dataclass
class ExperimentResult:
    name: str
    attacker_type: str  # baseline, random, ai_v1, ai_v2
    duration_label: str  # 5m, 1h
    seed: int

    tvd_sec: float = 0.0
    asr_pct: float = 0.0
    phar_pct: float = 0.0
    macp: float = 0.5
    total_attacks: int = 0
    avg_macro_score: float = 0.0
    avg_micro_score: float = 0.0
    unique_evs: int = 0
    efficiency: float = 0.0  # TVD per attack


def parse_name(name: str) -> tuple[str, str, int]:
    """Parse v2 experiment names like 'ai_v2_5m_s1' or 'random_300s_s2'."""
    # Try v2 format: {variant}_{duration}_s{seed}
    m = re.match(r"(ai_v[12]|random|baseline)_(\w+)_s(\d+)", name)
    if m:
        return m.group(1), m.group(2), int(m.group(3))

    # Fallback
    if "baseline" in name.lower():
        return "baseline", "5m", 0
    if "random" in name.lower():
        return "random", "5m", 1
    if "v1" in name.lower():
        return "ai_v1", "5m", 1
    if "v2" in name.lower() or "ai" in name.lower():
        return "ai_v2", "5m", 1
    return "unknown", "5m", 1


def load_result(path: Path) -> Optional[ExperimentResult]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading {path}: {e}")
        return None

    name = data.get("config", {}).get("experiment_name", path.stem)
    variant, dur, seed = parse_name(name)

    # Override with explicit attacker_type
    atype = data.get("attacker_type", variant)
    if atype in ("none", "baseline"):
        atype = "baseline"

    metrics = data.get("final_metrics", {})
    primary = metrics.get("primary_metrics", {})
    timing = metrics.get("timing_metrics", {})

    total_attacks = int(primary.get("total_attacks", 0))
    tvd = float(primary.get("tvd_sec", 0))

    # Count unique EVs from attack log
    attack_log = data.get("attack_log", [])
    ev_ids = set()
    for entry in attack_log:
        action = entry.get("action", {})
        ev_id = action.get("ev_id") if isinstance(action, dict) else None
        if ev_id:
            ev_ids.add(ev_id)

    return ExperimentResult(
        name=name,
        attacker_type=atype,
        duration_label=dur,
        seed=seed,
        tvd_sec=tvd,
        asr_pct=float(primary.get("asr_pct", 0)),
        phar_pct=float(timing.get("phar_pct", 0)),
        macp=float(timing.get("avg_attack_cycle_position", 0.5)),
        total_attacks=total_attacks,
        avg_macro_score=float(timing.get("avg_macro_score_at_attack", 0)),
        avg_micro_score=float(timing.get("avg_micro_score_at_attack", 0)),
        unique_evs=len(ev_ids),
        efficiency=tvd / total_attacks if total_attacks > 0 else 0.0,
    )


def load_all(results_dir: Path) -> List[ExperimentResult]:
    results = []
    for p in sorted(results_dir.rglob("*.json")):
        if p.name == "analysis.json":
            continue
        r = load_result(p)
        if r:
            results.append(r)
    return results


def mean_std(vals: List[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    m = sum(vals) / len(vals)
    if len(vals) < 2:
        return m, 0.0
    return m, math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def cohens_d(a: List[float], b: List[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    sp = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return (ma - mb) / sp if sp > 0 else 0.0


def analyze(results: List[ExperimentResult]) -> Dict:
    groups: Dict[str, List[ExperimentResult]] = {}
    for r in results:
        groups.setdefault(r.attacker_type, []).append(r)

    analysis: Dict = {"summary": {}, "hypothesis_tests": {}, "evg": {}}

    # Summary
    for gname in ["baseline", "random", "ai_v1", "ai_v2"]:
        grp = groups.get(gname, [])
        if not grp:
            continue
        tvd_m, tvd_s = mean_std([r.tvd_sec for r in grp])
        asr_m, asr_s = mean_std([r.asr_pct for r in grp])
        macp_m, macp_s = mean_std([r.macp for r in grp])
        micro_m, _ = mean_std([r.avg_micro_score for r in grp])
        evs_m, evs_s = mean_std([float(r.unique_evs) for r in grp])
        eff_m, eff_s = mean_std([r.efficiency for r in grp])
        atk_m, _ = mean_std([float(r.total_attacks) for r in grp])

        analysis["summary"][gname] = {
            "n": len(grp),
            "tvd": {"mean": round(tvd_m, 1), "std": round(tvd_s, 1)},
            "asr": {"mean": round(asr_m, 1), "std": round(asr_s, 1)},
            "macp": {"mean": round(macp_m, 3), "std": round(macp_s, 3)},
            "avg_micro": round(micro_m, 1),
            "unique_evs": {"mean": round(evs_m, 1), "std": round(evs_s, 1)},
            "efficiency": {"mean": round(eff_m, 1), "std": round(eff_s, 1)},
            "total_attacks": round(atk_m, 1),
        }

    # EVG
    rnd = groups.get("random", [])
    v1 = groups.get("ai_v1", [])
    v2 = groups.get("ai_v2", [])

    rnd_tvd = [r.tvd_sec for r in rnd]
    v1_tvd = [r.tvd_sec for r in v1]
    v2_tvd = [r.tvd_sec for r in v2]

    rnd_mean = sum(rnd_tvd) / len(rnd_tvd) if rnd_tvd else 0
    if rnd_mean > 0:
        if v2_tvd:
            analysis["evg"]["v2_vs_random"] = round(sum(v2_tvd) / len(v2_tvd) / rnd_mean, 2)
        if v1_tvd:
            analysis["evg"]["v1_vs_random"] = round(sum(v1_tvd) / len(v1_tvd) / rnd_mean, 2)

    # Hypothesis tests (need scipy + enough samples)
    if not HAS_SCIPY:
        analysis["hypothesis_tests"]["note"] = "scipy not installed — skipping statistical tests"
    elif len(rnd_tvd) >= 2:

        def one_tailed_greater(a, b, label):
            t, p2 = stats.ttest_ind(a, b)
            p = p2 / 2 if t > 0 else 1 - p2 / 2
            d = cohens_d(a, b)
            analysis["hypothesis_tests"][label] = {
                "t": round(t, 3), "p": round(p, 4),
                "d": round(d, 3), "reject": p < 0.05,
                "means": [round(sum(a) / len(a), 1), round(sum(b) / len(b), 1)],
            }

        # H1: V2 TVD > Random TVD
        if len(v2_tvd) >= 2:
            one_tailed_greater(v2_tvd, rnd_tvd, "H1_v2_tvd_gt_random")

        # H2: V2 TVD > V1 TVD
        if len(v2_tvd) >= 2 and len(v1_tvd) >= 2:
            one_tailed_greater(v2_tvd, v1_tvd, "H2_v2_tvd_gt_v1")

        # H3: V2 unique_evs > V1 unique_evs
        v2_evs = [float(r.unique_evs) for r in v2]
        v1_evs = [float(r.unique_evs) for r in v1]
        if len(v2_evs) >= 2 and len(v1_evs) >= 2:
            one_tailed_greater(v2_evs, v1_evs, "H3_v2_diversity_gt_v1")

        # H4: EVG > 1.0
        if v2_tvd and rnd_tvd:
            evg_per_seed = []
            for s in [1, 2, 3]:
                a = [r.tvd_sec for r in v2 if r.seed == s]
                b = [r.tvd_sec for r in rnd if r.seed == s]
                if a and b and sum(b) > 0:
                    evg_per_seed.append((sum(a) / len(a)) / (sum(b) / len(b)))
            if len(evg_per_seed) >= 2:
                t, p2 = stats.ttest_1samp(evg_per_seed, 1.0)
                p = p2 / 2 if t > 0 else 1 - p2 / 2
                analysis["hypothesis_tests"]["H4_evg_gt_1"] = {
                    "t": round(t, 3), "p": round(p, 4),
                    "values": [round(v, 2) for v in evg_per_seed],
                    "mean_evg": round(sum(evg_per_seed) / len(evg_per_seed), 2),
                    "reject": p < 0.05,
                }

    return analysis


def print_analysis(a: Dict) -> None:
    print("\n" + "=" * 70)
    print("LLM-GRIDEVAL v2 — EXPERIMENT ANALYSIS")
    print("=" * 70)

    print(f"\n{'Variant':<10} {'N':>3} {'TVD (s)':>14} {'Attacks':>8} "
          f"{'UniqueEVs':>10} {'Efficiency':>11} {'MACP':>8} {'MicroAvg':>9}")
    print("-" * 70)
    for name, s in a.get("summary", {}).items():
        print(f"{name:<10} {s['n']:>3} "
              f"{s['tvd']['mean']:>6.1f}±{s['tvd']['std']:<5.1f} "
              f"{s['total_attacks']:>7.1f} "
              f"{s['unique_evs']['mean']:>5.1f}±{s['unique_evs']['std']:<3.1f} "
              f"{s['efficiency']['mean']:>5.1f}±{s['efficiency']['std']:<3.1f} "
              f"{s['macp']['mean']:>7.3f} "
              f"{s['avg_micro']:>8.1f}")

    print("\n## Evaluation Validity Gap")
    for k, v in a.get("evg", {}).items():
        print(f"  {k}: {v}×")

    print("\n## Hypothesis Tests")
    for name, t in a.get("hypothesis_tests", {}).items():
        if isinstance(t, str):
            print(f"  {t}")
            continue
        tag = "✓ REJECT" if t.get("reject") else "✗ FAIL"
        print(f"  {name}: {tag}  t={t.get('t', 'N/A')}  p={t.get('p', 'N/A')}  "
              f"d={t.get('d', '')}  means={t.get('means', t.get('values', ''))}")

    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-GridEval v2 Analysis")
    parser.add_argument("--results-dir", default="v2/results",
                        help="Directory containing result JSON files (searched recursively)")
    parser.add_argument("--output", default=None, help="Output analysis JSON path")
    args = parser.parse_args()

    rdir = Path(args.results_dir)
    if not rdir.exists():
        print(f"Error: {rdir} not found")
        return

    results = load_all(rdir)
    if not results:
        print(f"No result files found in {rdir}")
        return

    print(f"Loaded {len(results)} results from {rdir}")
    a = analyze(results)
    print_analysis(a)

    out = Path(args.output) if args.output else rdir / "analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(a, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to: {out}")


if __name__ == "__main__":
    main()

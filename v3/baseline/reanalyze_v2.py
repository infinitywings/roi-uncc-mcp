#!/usr/bin/env python3
"""Independent, non-destructive reanalysis of the frozen GridEval v2 campaign."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml
from scipy import stats


ATTACKERS = ("random", "ai_v1", "ai_v2")
OPERATING_POINTS = ("hr4", "hr7", "hr14")
SEEDS = (1, 2, 3, 4, 5)
MAX_TVD_SEC = 300.0
BOOTSTRAP_REPS = 50_000


@dataclass(frozen=True)
class Run:
    name: str
    path: str
    attacker: str
    operating_point: str
    seed: int
    duration_sec: float
    controller_interval_sec: float
    tvd_sec: float
    total_attacks: int
    successful_attacks: int
    unique_evs: int
    asr_pct: float
    cycle_position: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def campaign_tree_digest(repo: Path) -> tuple[str, int]:
    root = repo / "v2/results/campaign"
    digest = hashlib.sha256()
    count = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = str(path.relative_to(repo))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
        count += 1
    return digest.hexdigest(), count


def expected_slots() -> list[str]:
    return [
        f"{attacker}_{op}_s{seed}"
        for op in OPERATING_POINTS
        for attacker in ATTACKERS
        for seed in SEEDS
    ]


def parse_name(name: str) -> tuple[str, str, int]:
    match = re.fullmatch(r"(random|ai_v1|ai_v2)_(hr4|hr7|hr14)_s([1-5])", name)
    if not match:
        raise ValueError(f"unexpected campaign experiment name: {name}")
    return match.group(1), match.group(2), int(match.group(3))


def load_run(repo: Path, path: Path) -> tuple[Run, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    issues: list[str] = []
    config = data.get("config", {})
    name = config.get("experiment_name", path.stem)
    attacker, operating_point, seed = parse_name(name)
    if path.stem != name:
        issues.append(f"{name}: filename stem differs from experiment_name")
    if data.get("attacker_type") != attacker:
        issues.append(
            f"{name}: attacker_type={data.get('attacker_type')!r}, expected {attacker!r}"
        )
    if config.get("seed") != seed:
        issues.append(f"{name}: config seed={config.get('seed')!r}, expected {seed}")

    primary = data.get("final_metrics", {}).get("primary_metrics", {})
    timing = data.get("final_metrics", {}).get("timing_metrics", {})
    attacks = data.get("attack_log", [])
    unique_evs = {
        entry.get("action", {}).get("ev_id")
        for entry in attacks
        if isinstance(entry.get("action"), dict)
        and entry.get("action", {}).get("ev_id")
    }
    total_attacks = int(primary.get("total_attacks", -1))
    if total_attacks != int(data.get("total_attacks", -2)):
        issues.append(f"{name}: top-level and final total_attacks disagree")
    if total_attacks != len(attacks):
        issues.append(
            f"{name}: total_attacks={total_attacks}, attack_log entries={len(attacks)}"
        )
    tvd = float(primary.get("tvd_sec", math.nan))
    if not 0 <= tvd <= MAX_TVD_SEC:
        issues.append(f"{name}: TVD {tvd} outside [0, {MAX_TVD_SEC}]")

    return (
        Run(
            name=name,
            path=str(path.relative_to(repo)),
            attacker=attacker,
            operating_point=operating_point,
            seed=seed,
            duration_sec=float(config.get("duration_sec", math.nan)),
            controller_interval_sec=float(
                config.get("controller_interval_sec", math.nan)
            ),
            tvd_sec=tvd,
            total_attacks=total_attacks,
            successful_attacks=int(primary.get("successful_attacks", -1)),
            unique_evs=len(unique_evs),
            asr_pct=float(primary.get("asr_pct", math.nan)),
            cycle_position=float(
                timing.get("avg_attack_cycle_position", math.nan)
            ),
        ),
        issues,
    )


def mean_sd(values: Iterable[float]) -> tuple[float, float]:
    array = np.asarray(list(values), dtype=float)
    return float(np.mean(array)), float(np.std(array, ddof=1)) if len(array) > 1 else 0.0


def summarize(values: list[float]) -> dict[str, Any]:
    mean, sd = mean_sd(values)
    if len(values) > 1:
        half = float(stats.t.ppf(0.975, len(values) - 1) * sd / math.sqrt(len(values)))
        ci = [mean - half, mean + half]
    else:
        ci = [None, None]
    return {
        "n": len(values),
        "values": values,
        "mean": mean,
        "sd": sd,
        "mean_95ci_t": ci,
        "min": min(values),
        "max": max(values),
    }


def welch_df(a: np.ndarray, b: np.ndarray) -> float | None:
    va = float(np.var(a, ddof=1))
    vb = float(np.var(b, ddof=1))
    term_a = va / len(a)
    term_b = vb / len(b)
    denominator = term_a**2 / (len(a) - 1) + term_b**2 / (len(b) - 1)
    if denominator == 0:
        return None
    return (term_a + term_b) ** 2 / denominator


def pooled_cohens_d(a: np.ndarray, b: np.ndarray) -> float | None:
    va = float(np.var(a, ddof=1))
    vb = float(np.var(b, ddof=1))
    pooled = ((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2)
    difference = float(np.mean(a) - np.mean(b))
    if pooled == 0:
        return 0.0 if difference == 0 else None
    return difference / math.sqrt(pooled)


def exact_permutation_greater(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    pooled = np.concatenate([a, b])
    observed = float(np.mean(a) - np.mean(b))
    total = math.comb(len(pooled), len(a))
    extreme = 0
    for indices in itertools.combinations(range(len(pooled)), len(a)):
        chosen = set(indices)
        perm_a = [pooled[index] for index in indices]
        perm_b = [
            pooled[index] for index in range(len(pooled)) if index not in chosen
        ]
        difference = float(np.mean(perm_a) - np.mean(perm_b))
        if difference >= observed - 1e-12:
            extreme += 1
    return {
        "statistic_mean_difference": observed,
        "p_one_sided_exact": extreme / total,
        "extreme_assignments": extreme,
        "total_assignments": total,
    }


def deterministic_seed(label: str) -> int:
    return int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def bootstrap_contrast(
    a: np.ndarray, b: np.ndarray, label: str
) -> dict[str, Any]:
    rng = np.random.default_rng(deterministic_seed(label))
    a_samples = rng.choice(a, size=(BOOTSTRAP_REPS, len(a)), replace=True)
    b_samples = rng.choice(b, size=(BOOTSTRAP_REPS, len(b)), replace=True)
    a_means = np.mean(a_samples, axis=1)
    b_means = np.mean(b_samples, axis=1)
    differences = a_means - b_means
    valid = b_means != 0
    ratios = a_means[valid] / b_means[valid]
    return {
        "repetitions": BOOTSTRAP_REPS,
        "mean_difference_95ci_percentile": [
            float(np.percentile(differences, 2.5)),
            float(np.percentile(differences, 97.5)),
        ],
        "ratio_of_means_95ci_percentile": (
            [float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))]
            if len(ratios)
            else [None, None]
        ),
        "ratio_invalid_zero_denominator_fraction": 1.0 - float(np.mean(valid)),
    }


def contrast(a_values: list[float], b_values: list[float], label: str) -> dict[str, Any]:
    a = np.asarray(a_values, dtype=float)
    b = np.asarray(b_values, dtype=float)
    difference = float(np.mean(a) - np.mean(b))
    df = welch_df(a, b)
    va = float(np.var(a, ddof=1))
    vb = float(np.var(b, ddof=1))
    if va == 0 and vb == 0:
        if difference == 0:
            welch = {
                "status": "undefined_equal_constant_groups",
                "t": None,
                "df": None,
                "p_one_sided": 1.0,
                "mean_difference_95ci": [0.0, 0.0],
            }
        else:
            welch = {
                "status": "degenerate_zero_variance_separation",
                "t": None,
                "t_limit": "positive_infinity" if difference > 0 else "negative_infinity",
                "df": None,
                "p_one_sided": 0.0 if difference > 0 else 1.0,
                "mean_difference_95ci": [difference, difference],
            }
    else:
        result = stats.ttest_ind(a, b, equal_var=False, alternative="greater")
        standard_error = math.sqrt(va / len(a) + vb / len(b))
        critical = float(stats.t.ppf(0.975, df))
        welch = {
            "status": "defined",
            "t": float(result.statistic),
            "df": df,
            "p_one_sided": float(result.pvalue),
            "mean_difference_95ci": [
                difference - critical * standard_error,
                difference + critical * standard_error,
            ],
        }
    d = pooled_cohens_d(a, b)
    hedges_g = None
    if d is not None:
        correction = 1 - 3 / (4 * (len(a) + len(b)) - 9)
        hedges_g = d * correction
    return {
        "label": label,
        "n_a": len(a),
        "n_b": len(b),
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "mean_difference": difference,
        "ratio_of_means": (
            float(np.mean(a) / np.mean(b)) if float(np.mean(b)) != 0 else None
        ),
        "welch_one_sided_greater": welch,
        "exact_independent_permutation": exact_permutation_greater(a, b),
        "cohens_d_pooled": d,
        "hedges_g_pooled": hedges_g,
        "bootstrap": bootstrap_contrast(a, b, label),
    }


def holm_adjust(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, (label, pvalue) in enumerate(ordered):
        candidate = min(1.0, (total - rank) * pvalue)
        running = max(running, candidate)
        adjusted[label] = running
    return adjusted


def parse_failure_logs(repo: Path) -> dict[str, Any]:
    failures: dict[str, Any] = {}
    for op in OPERATING_POINTS:
        path = repo / f"v2/results/campaign/{op}_run.log"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        active: str | None = None
        segment: list[str] = []

        def finish(name: str | None, content: list[str]) -> None:
            if not name:
                return
            failed = any(f"] ✗ {name} FAILED" in line for line in content)
            if not failed:
                return
            elapsed = [
                int(value)
                for line in content
                for value in re.findall(r"\[(\d+)s\]", line)
            ]
            attacks = sum(" ATTACK " in line for line in content)
            failures[name] = {
                "operating_point": op,
                "last_logged_sim_second": max(elapsed) if elapsed else None,
                "logged_attack_count_before_failure": attacks,
                "wrapper_failure_marker": True,
                "exception_or_root_cause_in_run_log": any(
                    token in "\n".join(content)
                    for token in ("Traceback", "HelicsException", "TimeoutError")
                ),
            }

        for line in lines:
            match = re.search(rf"\[{op}\] --- (\S+) ---", line)
            if match:
                finish(active, segment)
                active = match.group(1)
                segment = [line]
            elif active:
                segment.append(line)
        finish(active, segment)
    return failures


def missingness_analysis(
    completed: set[str], failures: dict[str, Any]
) -> dict[str, Any]:
    expected = set(expected_slots())
    missing = sorted(expected - completed)
    if set(missing) != set(failures):
        mismatch = {
            "missing_without_failure_marker": sorted(set(missing) - set(failures)),
            "failure_marker_with_result": sorted(set(failures) - set(missing)),
        }
    else:
        mismatch = {}

    def group_count(key_fn):
        output: dict[str, dict[str, int | float]] = {}
        groups: dict[str, list[str]] = defaultdict(list)
        for slot in sorted(expected):
            groups[str(key_fn(slot))].append(slot)
        for key, slots in groups.items():
            successes = sum(slot in completed for slot in slots)
            output[key] = {
                "planned": len(slots),
                "completed": successes,
                "failed": len(slots) - successes,
                "completion_fraction": successes / len(slots),
            }
        return output

    by_attacker = group_count(lambda name: parse_name(name)[0])
    by_op = group_count(lambda name: parse_name(name)[1])
    by_seed = group_count(lambda name: parse_name(name)[2])
    seed2_completed = int(by_seed["2"]["completed"])
    other_completed = sum(
        int(values["completed"]) for key, values in by_seed.items() if key != "2"
    )
    seed2_failed = int(by_seed["2"]["failed"])
    other_failed = sum(
        int(values["failed"]) for key, values in by_seed.items() if key != "2"
    )
    fisher = stats.fisher_exact(
        [[seed2_completed, seed2_failed], [other_completed, other_failed]],
        alternative="two-sided",
    )
    return {
        "planned": len(expected),
        "completed": len(completed),
        "failed": len(missing),
        "missing_slots": missing,
        "failure_log_reconciliation": mismatch or "exact",
        "by_attacker": by_attacker,
        "by_operating_point": by_op,
        "by_seed": by_seed,
        "seed2_vs_other_completion_fisher_exact": {
            "table": [
                [seed2_completed, seed2_failed],
                [other_completed, other_failed],
            ],
            "odds_ratio": float(fisher.statistic),
            "p_two_sided": float(fisher.pvalue),
        },
        "failure_log_evidence": failures,
        "root_cause_status": (
            "The run logs preserve wrapper failure markers and partial progress "
            "but no exception/root-cause text for the eight campaign failures. "
            "The campaign report labels them HELICS timeouts; that mechanism is "
            "not independently recoverable from the retained per-condition logs."
        ),
    }


def worst_case_bounds(
    grouped: dict[tuple[str, str], list[Run]], completed: set[str]
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for op in OPERATING_POINTS:
        sums = {}
        missing_counts = {}
        for attacker in ("ai_v2", "random"):
            values = [run.tvd_sec for run in grouped[(op, attacker)]]
            sums[attacker] = sum(values)
            missing_counts[attacker] = sum(
                f"{attacker}_{op}_s{seed}" not in completed for seed in SEEDS
            )
        v2_low = sums["ai_v2"] / 5
        v2_high = (sums["ai_v2"] + missing_counts["ai_v2"] * MAX_TVD_SEC) / 5
        random_low = sums["random"] / 5
        random_high = (
            sums["random"] + missing_counts["random"] * MAX_TVD_SEC
        ) / 5
        output[op] = {
            "assumption": "Each missing TVD is bounded only by [0, 300] seconds.",
            "ai_v2_mean_bounds": [v2_low, v2_high],
            "random_mean_bounds": [random_low, random_high],
            "v2_minus_random_mean_difference_bounds": [
                v2_low - random_high,
                v2_high - random_low,
            ],
            "evg_ratio_bounds": [
                v2_low / random_high if random_high else None,
                v2_high / random_low if random_low else None,
            ],
        }
    return output


def timing_and_config_audit(repo: Path) -> dict[str, Any]:
    controller_config_path = repo / "v2/controller/v2_control.json"
    controller_config = json.loads(controller_config_path.read_text(encoding="utf-8"))
    controller_source_path = repo / "v2/controller/ev_controller_v2.py"
    controller_source = controller_source_path.read_text(encoding="utf-8")
    experiment_config_path = repo / "v2/configs/experiment.yaml"
    experiment_config = yaml.safe_load(
        experiment_config_path.read_text(encoding="utf-8")
    )
    v1_source_path = repo / "v2/attackers/ai_v1_timing.py"
    v2_source_path = repo / "v2/attackers/ai_v2_strategy.py"
    v1_source = v1_source_path.read_text(encoding="utf-8")
    v2_source = v2_source_path.read_text(encoding="utf-8")
    feeder_a_config_path = repo / "examples/2bus-13bus/mainglm.json"
    feeder_b_config_path = repo / "examples/2bus-13bus/mainglm_2.json"
    feeder_a_config = json.loads(
        feeder_a_config_path.read_text(encoding="utf-8")
    )
    feeder_b_config = json.loads(
        feeder_b_config_path.read_text(encoding="utf-8")
    )
    feeder_a_glm_path = repo / "examples/2bus-13bus/1c_IEEE_123_feeder.glm"
    feeder_b_glm_path = (
        repo / "examples/2bus-13bus/1c_IEEE_123_feeder_2.glm"
    )
    feeder_a_glm = feeder_a_glm_path.read_text(encoding="utf-8")
    feeder_b_glm = feeder_b_glm_path.read_text(encoding="utf-8")

    period = int(controller_config["period"])
    logical_interval = int(experiment_config["experiment"]["controller_interval_sec"])
    logical_times = list(range(0, 300, logical_interval))
    grant = -1
    helics_current = 0
    mapping = []
    for logical_time in logical_times:
        requested = None
        if grant < logical_time:
            requested = logical_time
            if logical_time <= helics_current:
                grant = helics_current + period
            else:
                grant = math.ceil(logical_time / period) * period
            helics_current = grant
        mapping.append(
            {
                "logical_decision_time_s": logical_time,
                "request_made_s": requested,
                "allowed_grant_s_under_period_semantics": grant,
            }
        )

    hardcoded_v1 = [int(value) for value in re.findall(r"max_tokens=(\d+)", v1_source)]
    hardcoded_v2 = [int(value) for value in re.findall(r"max_tokens=(\d+)", v2_source)]
    return {
        "controller": {
            "helics_period_s": period,
            "logical_update_interval_s": logical_interval,
            "source_has_range_update_interval_loop": (
                "range(0, config.sim_duration_sec, config.update_interval_sec)"
                in controller_source
            ),
            "source_requests_logical_t": (
                "helicsFederateRequestTime(fed, t)" in controller_source
            ),
            "source_skips_request_when_grant_ahead": (
                "while granted_time < t:" in controller_source
            ),
            "official_helics_period_semantics": (
                "Granted times are constrained to n*period + offset. Requests "
                "at invalid or already-current times advance to the next "
                "allowed time. A live HELICS 3.6.1 probe is stored separately "
                "in v3/baseline/cadence_probe_r1."
            ),
            "static_300s_grant_mapping": mapping,
            "distinct_allowed_grants_used_by_loop": sorted(
                {
                    row["allowed_grant_s_under_period_semantics"]
                    for row in mapping
                }
            ),
            "decisions_per_allowed_grant": dict(
                sorted(
                    Counter(
                        row["allowed_grant_s_under_period_semantics"]
                        for row in mapping
                    ).items()
                )
            ),
            "verdict": (
                "The source executes 10-second logical decisions, but period=60 "
                "constrains HELICS grants to 60-second multiples. Its initial "
                "request for t=0 advances to the first 60-second grant, so the "
                "loop executes logical decisions t=0 through t=60 against that "
                "one granted time; later grants also service multiple logical "
                "decisions. Retained campaign artifacts contain no successful "
                "controller grant/decision trace to demonstrate an actual "
                "10-second physical defender cadence."
            ),
        },
        "physical_feeder_cadence": {
            "feeder_a_helics_period_s": int(feeder_a_config["period"]),
            "feeder_b_helics_period_s": int(feeder_b_config["period"]),
            "feeder_a_minimum_timestep_s": int(
                re.search(
                    r"#set\s+minimum_timestep=(\d+)",
                    feeder_a_glm,
                ).group(1)
            ),
            "feeder_b_minimum_timestep_s": int(
                re.search(
                    r"#set\s+minimum_timestep=(\d+)",
                    feeder_b_glm,
                ).group(1)
            ),
            "verdict": (
                "Both GridLAB-D feeder federates have HELICS period=60. "
                "Feeder A has minimum_timestep=60 and Feeder B has "
                "minimum_timestep=120. A controller-only period=10 repair "
                "cannot demonstrate fresh physical feeder samples or applied "
                "EV effects every 10 seconds; both feeder couplings must also "
                "be changed and convergence-validated, or the mechanism must "
                "be described as acting on a plant sampled no faster than "
                "60 seconds."
            ),
        },
        "llm_max_tokens": {
            "experiment_yaml": int(experiment_config["llm"]["max_tokens"]),
            "ai_v1_source_literals": hardcoded_v1,
            "ai_v2_source_literals": hardcoded_v2,
            "effective_campaign_attacker_value": (
                hardcoded_v1[0]
                if hardcoded_v1
                and hardcoded_v2
                and hardcoded_v1[0] == hardcoded_v2[0]
                else None
            ),
            "verdict": (
                "The campaign attacker implementations hard-code 4000 and do not "
                "read experiment.yaml's 300 value; the YAML is stale/misleading "
                "rather than the effective campaign token limit."
            ),
        },
        "source_hashes": {
            str(path.relative_to(repo)): sha256(path)
            for path in (
                controller_config_path,
                controller_source_path,
                experiment_config_path,
                v1_source_path,
                v2_source_path,
                feeder_a_config_path,
                feeder_b_config_path,
                feeder_a_glm_path,
                feeder_b_glm_path,
            )
        },
    }


def write_completion_csv(
    path: Path, runs_by_name: dict[str, Run], failures: dict[str, Any]
) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "experiment",
                "operating_point",
                "attacker",
                "seed",
                "status",
                "tvd_sec",
                "last_logged_sim_second",
                "logged_attacks_before_failure",
            ],
        )
        writer.writeheader()
        for name in expected_slots():
            attacker, op, seed = parse_name(name)
            run = runs_by_name.get(name)
            failure = failures.get(name, {})
            writer.writerow(
                {
                    "experiment": name,
                    "operating_point": op,
                    "attacker": attacker,
                    "seed": seed,
                    "status": "completed" if run else "failed",
                    "tvd_sec": run.tvd_sec if run else "",
                    "last_logged_sim_second": failure.get(
                        "last_logged_sim_second", ""
                    ),
                    "logged_attacks_before_failure": failure.get(
                        "logged_attack_count_before_failure", ""
                    ),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "reanalysis_r4",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()
    output_dir = args.output_dir.resolve()
    output_json = output_dir / "v2_reanalysis.json"
    completion_csv = output_dir / "completion_matrix.csv"
    if output_json.exists() or completion_csv.exists():
        print(f"Refusing to overwrite existing reanalysis in {output_dir}", file=sys.stderr)
        return 2

    manifest = json.loads(
        (repo / "v3/baseline/v2_freeze_manifest.json").read_text(encoding="utf-8")
    )
    observed_tree, observed_count = campaign_tree_digest(repo)
    frozen_tree = manifest["campaign_tree"]["tree_sha256"]
    if observed_tree != frozen_tree:
        print(
            f"Campaign tree changed: frozen={frozen_tree}, observed={observed_tree}",
            file=sys.stderr,
        )
        return 1

    runs: list[Run] = []
    validation_issues: list[str] = []
    for path in sorted((repo / "v2/results/campaign").glob("hr*/*.json")):
        if path.name == "analysis.json":
            continue
        run, issues = load_run(repo, path)
        runs.append(run)
        validation_issues.extend(issues)
    runs_by_name = {run.name: run for run in runs}
    if len(runs_by_name) != len(runs):
        validation_issues.append("duplicate experiment names found")
    completed = set(runs_by_name)
    unexpected = sorted(completed - set(expected_slots()))
    if unexpected:
        validation_issues.append(f"unexpected completed experiments: {unexpected}")

    grouped: dict[tuple[str, str], list[Run]] = defaultdict(list)
    for run in runs:
        grouped[(run.operating_point, run.attacker)].append(run)
    for values in grouped.values():
        values.sort(key=lambda item: item.seed)

    cells: dict[str, Any] = {}
    for op in OPERATING_POINTS:
        cells[op] = {}
        for attacker in ATTACKERS:
            cell_runs = grouped[(op, attacker)]
            cells[op][attacker] = {
                "tvd": summarize([run.tvd_sec for run in cell_runs]),
                "unique_evs": summarize(
                    [float(run.unique_evs) for run in cell_runs]
                ),
                "total_attacks": summarize(
                    [float(run.total_attacks) for run in cell_runs]
                ),
                "cycle_position": summarize(
                    [run.cycle_position for run in cell_runs]
                ),
                "seeds_completed": [run.seed for run in cell_runs],
            }

    comparisons: dict[str, Any] = {}
    for op in OPERATING_POINTS:
        for metric, pair in (
            ("tvd_v2_gt_random", ("ai_v2", "random", "tvd_sec")),
            ("tvd_v2_gt_v1", ("ai_v2", "ai_v1", "tvd_sec")),
            ("tvd_v1_gt_random", ("ai_v1", "random", "tvd_sec")),
            ("unique_evs_v2_gt_v1", ("ai_v2", "ai_v1", "unique_evs")),
        ):
            attacker_a, attacker_b, field = pair
            a_values = [
                float(getattr(run, field)) for run in grouped[(op, attacker_a)]
            ]
            b_values = [
                float(getattr(run, field)) for run in grouped[(op, attacker_b)]
            ]
            label = f"{op}:{metric}"
            comparisons[label] = contrast(a_values, b_values, label)

    responsive_h1 = {
        label: result
        for label, result in comparisons.items()
        if label in ("hr4:tvd_v2_gt_random", "hr7:tvd_v2_gt_random")
    }
    holm = {
        "family": list(responsive_h1),
        "welch_one_sided": holm_adjust(
            {
                label: result["welch_one_sided_greater"]["p_one_sided"]
                for label, result in responsive_h1.items()
            }
        ),
        "exact_permutation_one_sided": holm_adjust(
            {
                label: result["exact_independent_permutation"][
                    "p_one_sided_exact"
                ]
                for label, result in responsive_h1.items()
            }
        ),
    }

    failures = parse_failure_logs(repo)
    output = {
        "schema_version": "0.1",
        "analysis_identity": {
            "script": str(Path(__file__).resolve().relative_to(repo)),
            "script_sha256_before_run": sha256(Path(__file__).resolve()),
            "frozen_campaign_tree_sha256": frozen_tree,
            "observed_campaign_tree_sha256": observed_tree,
            "campaign_tree_file_count": observed_count,
            "python": sys.version,
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "bootstrap_repetitions": BOOTSTRAP_REPS,
        },
        "validation": {
            "completed_result_count": len(runs),
            "unique_result_count": len(runs_by_name),
            "issues": validation_issues,
        },
        "runs": [asdict(run) for run in sorted(runs, key=lambda item: item.name)],
        "cells": cells,
        "comparisons": comparisons,
        "holm_adjustment_primary_responsive_h1": holm,
        "missingness": missingness_analysis(completed, failures),
        "worst_case_missing_tvd_bounds": worst_case_bounds(
            grouped, completed
        ),
        "timing_and_config_audit": timing_and_config_audit(repo),
        "interpretation_limits": [
            "Run is the experimental unit; timesteps are not treated as independent.",
            "The campaign is unbalanced and lacks complete paired seeds across attacker cells.",
            "Exact permutation tests are independent-label tests, not paired tests.",
            "Bootstrap intervals are descriptive with N=3-5 and should not be read as precise.",
            "Hour 14 is a ceiling/negative-control condition and excluded from responsive H1 multiplicity adjustment.",
            "No missing TVD is imputed; worst-case bounds use only the physical [0, 300] range.",
            "The controller timing verdict is based on source/config semantics because successful granted-time traces were not retained.",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    output_json.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_completion_csv(completion_csv, runs_by_name, failures)
    print(f"Wrote {output_json}")
    print(f"Wrote {completion_csv}")
    print(
        f"Verified {len(runs)} completed + {len(failures)} failed = "
        f"{len(runs) + len(failures)} planned slots"
    )
    for label in ("hr4:tvd_v2_gt_random", "hr7:tvd_v2_gt_random"):
        result = comparisons[label]
        print(
            f"{label}: Welch p={result['welch_one_sided_greater']['p_one_sided']:.6g}; "
            "exact p="
            f"{result['exact_independent_permutation']['p_one_sided_exact']:.6g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

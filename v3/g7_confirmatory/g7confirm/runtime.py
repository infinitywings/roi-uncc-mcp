"""Bounded derived composition of the frozen G7 co-simulation runner."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

from .budget import DualBudget, RunnerOwnedDualBudgetPolicyAdapter
from .manifest import create_once_json
from .operating_points import OPERATING_POINTS, actuate_glm_clock
from .partitions import gridlabd_random_seed, require_component_seeds
from .spec import load_spec


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
FREEZE_ROOT = REPO_ROOT / "v3" / "g7_condition_freeze" / "20260830_r1"
FROZEN_ATTACK_RUNNER = FREEZE_ROOT / "formal_uninformed" / "run_g7_attack_loop.py"
FROZEN_BASE_RUNNER = FREEZE_ROOT / "shared" / "run_multi_der_loop.py"
FROZEN_DETECTOR = FREEZE_ROOT / "shared" / "detector_g7.py"
FROZEN_SENSITIVITY = FREEZE_ROOT / "shared" / "sensitivity_g7.json"
FROZEN_BENIGN = FREEZE_ROOT / "shared" / "g7_pilot_b0"
SOURCE_GLM = REPO_ROOT / "examples" / "2bus-13bus" / "1c_IEEE_123_feeder.glm"
LOAD_PLAYER = (
    REPO_ROOT / "examples" / "2bus-13bus" / "include" / "players"
    / "load_shape_player.player"
)
DEFAULT_CONFIG = REPO_ROOT / "v3" / "configs" / "der_devices.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_frozen_runtime() -> tuple[ModuleType, ModuleType, dict[str, str]]:
    """Load exact frozen bytes and repair only their relocated path globals."""
    for path in (FROZEN_ATTACK_RUNNER, FROZEN_BASE_RUNNER, SOURCE_GLM,
                 LOAD_PLAYER, DEFAULT_CONFIG):
        if not path.is_file():
            raise FileNotFoundError(path)

    opender_path = str(REPO_ROOT / "v3" / "opender")
    shared_path = str(FREEZE_ROOT / "shared")
    for path in (opender_path, shared_path):
        if path not in sys.path:
            sys.path.insert(0, path)

    base = _load_module("g7confirm_frozen_base", FROZEN_BASE_RUNNER)
    # The frozen copy retains its original repository-relative globals.  Point
    # them at the same external inputs by absolute path; no source bytes change.
    base.REPO = REPO_ROOT
    base.CONFIG_PATH = DEFAULT_CONFIG
    base.SOURCE_GLM = SOURCE_GLM

    previous = sys.modules.get("run_multi_der_loop")
    sys.modules["run_multi_der_loop"] = base
    try:
        attack = _load_module("g7confirm_frozen_attack", FROZEN_ATTACK_RUNNER)
    finally:
        if previous is None:
            sys.modules.pop("run_multi_der_loop", None)
        else:
            sys.modules["run_multi_der_loop"] = previous

    hashes = {
        "frozen_attack_runner_sha256": _sha256(FROZEN_ATTACK_RUNNER),
        "frozen_base_runner_sha256": _sha256(FROZEN_BASE_RUNNER),
        "source_glm_sha256": _sha256(SOURCE_GLM),
        "load_shape_player_sha256": _sha256(LOAD_PLAYER),
        "device_config_sha256": _sha256(DEFAULT_CONFIG),
    }
    if FROZEN_DETECTOR.is_file():
        hashes["frozen_detector_sha256"] = _sha256(FROZEN_DETECTOR)
    if FROZEN_SENSITIVITY.is_file():
        hashes["frozen_sensitivity_sha256"] = _sha256(FROZEN_SENSITIVITY)
    return base, attack, hashes


def _normalise_commands(raw: Mapping[str, Any]) -> dict[str, tuple[float, float]]:
    result: dict[str, tuple[float, float]] = {}
    for device_id, command in raw.items():
        if not isinstance(command, (list, tuple)) or len(command) != 2:
            raise RuntimeError(f"invalid command trace for {device_id}")
        result[device_id] = (float(command[0]), float(command[1]))
    return result


def reconcile_delivery(*, adapter: RunnerOwnedDualBudgetPolicyAdapter,
                       attack_trace: list[dict[str, Any]],
                       device_traces: dict[str, list[dict[str, Any]]],
                       benign_commands: Mapping[str, tuple[float, float]],
                       window_seconds: float) -> dict[str, Any]:
    """Prove admitted commands are the only commands delivered by the runner."""
    if len(adapter.trace) != len(attack_trace):
        raise RuntimeError(
            f"budget/attack trace length mismatch: {len(adapter.trace)} != {len(attack_trace)}"
        )
    records: list[dict[str, Any]] = []
    delivered_energy = 0.0
    for index, (budget_record, attack_record) in enumerate(zip(adapter.trace, attack_trace)):
        admitted = _normalise_commands(budget_record["admitted"])
        runner_attack = _normalise_commands(attack_record.get("attack", {}))
        if admitted != runner_attack:
            raise RuntimeError(
                f"window {index} admitted/runner attack drift: {admitted!r} != {runner_attack!r}"
            )
        delivered: dict[str, tuple[float, float]] = {}
        perturbed_devices: set[str] = set()
        for device_id, rows in device_traces.items():
            if index >= len(rows):
                raise RuntimeError(f"device {device_id} is missing window {index}")
            row = rows[index]
            if bool(row.get("perturbed")):
                perturbed_devices.add(device_id)
            if device_id in admitted:
                delivered[device_id] = (
                    float(row["cmd_p_kw"]), float(row["cmd_q_kvar"]),
                )
        if perturbed_devices != set(admitted):
            raise RuntimeError(
                f"window {index} perturbed-device drift: "
                f"{sorted(perturbed_devices)} != {sorted(admitted)}"
            )
        for device_id, command in admitted.items():
            actual = delivered[device_id]
            if not (math.isclose(command[0], actual[0], abs_tol=1e-9)
                    and math.isclose(command[1], actual[1], abs_tol=1e-9)):
                raise RuntimeError(
                    f"window {index} delivered-command drift for {device_id}: "
                    f"{command!r} != {actual!r}"
                )
            p0, q0 = benign_commands[device_id]
            delivered_energy += math.hypot(actual[0] - p0, actual[1] - q0) * window_seconds / 3600.0
        record = dict(budget_record)
        record["delivered"] = delivered
        record["delivery_reconciled"] = True
        records.append(record)

    admitted_energy = adapter.dual_budget.energy_spent_kvah
    if not math.isclose(delivered_energy, admitted_energy, rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(
            f"admitted/delivered energy drift: {admitted_energy} != {delivered_energy}"
        )
    if adapter.spent != adapter.dual_budget.windows_spent:
        raise RuntimeError(
            f"inner/dual window drift: {adapter.spent} != {adapter.dual_budget.windows_spent}"
        )
    return {
        "schema_version": "grideval-g7-dual-budget-trace/v1",
        "window_cap": adapter.dual_budget.window_cap,
        "apparent_energy_cap_kvah": adapter.dual_budget.energy_cap,
        "windows_spent": adapter.dual_budget.windows_spent,
        "admitted_energy_kvah": admitted_energy,
        "delivered_command_energy_kvah": delivered_energy,
        "delivery_reconciled": True,
        "records": records,
    }


def _require_scoped_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(PACKAGE_ROOT):
        raise ValueError(f"output must remain under {PACKAGE_ROOT}")
    return resolved


def run_bounded(args: argparse.Namespace) -> int:
    if int(args.windows) != 1:
        raise ValueError("runtime-integration build is hard-capped at one window")
    spec = load_spec(args.spec)
    simulator_seed = gridlabd_random_seed(SOURCE_GLM)
    partition, component_seeds = require_component_seeds(
        spec,
        replicate_seed=int(args.attacker_seed),
        gridlabd_random_seed=simulator_seed,
        explicit_noise_seed=args.noise_seed,
        allowed=tuple(spec["seed_controls"]["allowed_runtime_partitions"]),
        purpose="bounded runtime integration",
    )
    args.noise_seed = component_seeds.measurement_noise_seed
    if args.detector:
        raise ValueError(
            "detector execution is held until a calibrated create-once parameter "
            "artifact passes evidence review"
        )
    output_dir = _require_scoped_output(args.output_dir)
    base, attack, dependency_hashes = load_frozen_runtime()
    duration_s = int(args.windows) * int(args.coupling_step)

    original_builder = base.build_multi_der_glm
    operating_point_metadata: dict[str, Any] = {}

    def build_at_operating_point(devices: list[dict[str, Any]], step_s: int) -> str:
        nonlocal operating_point_metadata
        generated = original_builder(devices, step_s)
        generated, operating_point_metadata = actuate_glm_clock(
            generated,
            point_id=args.operating_point,
            duration_s=duration_s,
            player_path=LOAD_PLAYER,
        )
        return generated

    base.build_multi_der_glm = build_at_operating_point
    attack.DURATION_S = duration_s

    adapter_state: dict[str, Any] = {}
    original_factory = attack.make_policy

    def make_budgeted_policy(arm: str, devices: list[dict[str, Any]],
                             envs: dict[str, dict[str, float]], budget: int,
                             seed: int, **kwargs: Any) -> RunnerOwnedDualBudgetPolicyAdapter:
        policy = original_factory(arm, devices, envs, budget, seed, **kwargs)
        benign = {
            device["id"]: attack.benign_command(device, envs[device["id"]])
            for device in devices
        }
        adapter = RunnerOwnedDualBudgetPolicyAdapter(
            policy,
            DualBudget(
                window_cap=int(budget),
                apparent_energy_cap_kvah=float(args.energy_cap_kvah),
                window_seconds=float(args.coupling_step),
            ),
            benign,
        )
        adapter_state.update({"adapter": adapter, "benign": benign})
        return adapter

    attack.make_policy = make_budgeted_policy
    args.output_dir = output_dir
    status = int(attack.run(args))

    integration = {
        "schema_version": "grideval-g7-runtime-integration/v1",
        "mode": "gen-only" if args.gen_only else "one-window-runtime-smoke",
        "campaign_authorized": False,
        "runtime_window_limit": 1,
        "evaluation_opened": False,
        "seed_lineage": {
            "partition": partition,
            **component_seeds.as_dict(),
        },
        "operating_point": operating_point_metadata,
        "dependency_hashes": dependency_hashes,
        "composition": {
            "attack_runner": str(FROZEN_ATTACK_RUNNER),
            "base_runner": str(FROZEN_BASE_RUNNER),
            "clock_hook": "g7confirm.operating_points.actuate_glm_clock",
            "budget_hook": "g7confirm.budget.RunnerOwnedDualBudgetPolicyAdapter",
        },
        "budget": {
            "perturbed_window_cap": int(args.budget_windows),
            "apparent_energy_cap_kvah": float(args.energy_cap_kvah),
        },
        "status": "passed" if status == 0 else "failed_closed",
    }
    if not args.gen_only:
        adapter = adapter_state.get("adapter")
        if adapter is None:
            raise RuntimeError("frozen runner did not instantiate the budget adapter")
        dual_trace = reconcile_delivery(
            adapter=adapter,
            attack_trace=json.loads((output_dir / "attack_trace.json").read_text()),
            device_traces=json.loads((output_dir / "multi_der_traces.json").read_text()),
            benign_commands=adapter_state["benign"],
            window_seconds=float(args.coupling_step),
        )
        create_once_json(output_dir / "dual_budget_trace.json", dual_trace)
        integration["delivery"] = {
            key: dual_trace[key]
            for key in (
                "windows_spent", "admitted_energy_kvah",
                "delivered_command_energy_kvah", "delivery_reconciled",
            )
        }
    create_once_json(output_dir / "runtime_integration.json", integration)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", default="scripted_max", choices=[
        "scripted_max", "random", "ssv_llm", "sensi_opt", "detector_evasive",
        "sched_evasive", "llm_planner", "probe",
    ])
    parser.add_argument("--spec", type=Path, default=PACKAGE_ROOT / "experiment_spec.yaml")
    parser.add_argument("--operating-point", required=True, choices=sorted(OPERATING_POINTS))
    parser.add_argument("--energy-cap-kvah", type=float, default=2.0)
    parser.add_argument("--budget-windows", type=int, default=1)
    parser.add_argument("--windows", type=int, default=1)
    parser.add_argument("--coupling-step", type=int, default=10)
    parser.add_argument("--attacker-seed", type=int, default=8101)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--volt-var", action="store_true")
    parser.add_argument("--meas-noise-pu", type=float, default=0.002)
    parser.add_argument("--noise-seed", type=int, default=None)
    parser.add_argument("--sensitivity", type=Path, default=FROZEN_SENSITIVITY)
    parser.add_argument("--probe-id", default=None)
    parser.add_argument("--probe-kw", type=float, default=0.0)
    parser.add_argument("--detector", action="store_true")
    parser.add_argument("--detector-benign", type=Path, default=FROZEN_BENIGN)
    parser.add_argument("--det-far", type=float, default=0.05)
    parser.add_argument("--l3-safety", type=float, default=0.3)
    parser.add_argument("--l3-cooldown", type=int, default=4)
    parser.add_argument("--l4-alpha", type=float, default=0.3)
    parser.add_argument("--l4-period", type=int, default=6)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gen-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_bounded(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())

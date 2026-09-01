"""Atomic dual-budget accounting for perturbed DER commands."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping


Command = tuple[float, float]
CommandMap = Mapping[str, Command]


@dataclass(frozen=True)
class BudgetDecision:
    accepted: bool
    commands: dict[str, Command]
    window_cost: int
    apparent_energy_kvah: float
    windows_spent: int
    energy_spent_kvah: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DualBudget:
    """Meter attack deviation from benign and reject over-cap actions atomically."""

    def __init__(self, *, window_cap: int, apparent_energy_cap_kvah: float,
                 window_seconds: float, tolerance: float = 1e-9):
        if int(window_cap) < 0:
            raise ValueError("window_cap must be non-negative")
        if float(apparent_energy_cap_kvah) < 0:
            raise ValueError("apparent_energy_cap_kvah must be non-negative")
        if float(window_seconds) <= 0:
            raise ValueError("window_seconds must be positive")
        self.window_cap = int(window_cap)
        self.energy_cap = float(apparent_energy_cap_kvah)
        self.window_seconds = float(window_seconds)
        self.tolerance = float(tolerance)
        self.windows_spent = 0
        self.energy_spent_kvah = 0.0

    @staticmethod
    def _coerce(command: Command, device_id: str) -> Command:
        if not isinstance(command, (tuple, list)) or len(command) != 2:
            raise ValueError(f"command for {device_id} must be a (p_kw, q_kvar) pair")
        p, q = float(command[0]), float(command[1])
        if not math.isfinite(p) or not math.isfinite(q):
            raise ValueError(f"command for {device_id} must be finite")
        return p, q

    def try_admit(self, commands: CommandMap, benign: CommandMap) -> BudgetDecision:
        canonical: dict[str, Command] = {}
        energy = 0.0
        for device_id, raw in commands.items():
            if device_id not in benign:
                raise ValueError(f"missing benign command for {device_id}")
            p, q = self._coerce(raw, device_id)
            p0, q0 = self._coerce(benign[device_id], device_id)
            dp, dq = p - p0, q - q0
            if abs(dp) <= self.tolerance and abs(dq) <= self.tolerance:
                continue
            canonical[device_id] = (p, q)
            energy += math.hypot(dp, dq) * self.window_seconds / 3600.0

        window_cost = int(bool(canonical))
        next_windows = self.windows_spent + window_cost
        next_energy = self.energy_spent_kvah + energy
        if next_windows > self.window_cap:
            return BudgetDecision(False, {}, window_cost, energy, self.windows_spent,
                                  self.energy_spent_kvah, "perturbed_window_cap")
        if next_energy > self.energy_cap + self.tolerance:
            return BudgetDecision(False, {}, window_cost, energy, self.windows_spent,
                                  self.energy_spent_kvah, "apparent_energy_cap")

        self.windows_spent = next_windows
        self.energy_spent_kvah = next_energy
        reason = "accepted_perturbation" if canonical else "accepted_benign"
        return BudgetDecision(True, canonical, window_cost, energy, self.windows_spent,
                              self.energy_spent_kvah, reason)

    def remaining(self) -> dict[str, float | int]:
        return {
            "perturbed_windows": self.window_cap - self.windows_spent,
            "apparent_energy_kvah": max(0.0, self.energy_cap - self.energy_spent_kvah),
        }


class DualBudgetPolicyAdapter:
    """Adapt a side-effect-free policy decision to identical dual-budget rules.

    The wrapped policy may update its own spend state only through
    ``note_spent``. This matches the frozen G7 policy interface and lets an
    over-budget proposal be replaced by a benign action without partially
    consuming either budget.
    """

    def __init__(self, policy: Any, budget: DualBudget,
                 benign_commands: Mapping[str, Command] |
                 Callable[[int, int, dict[str, float]], Mapping[str, Command]]):
        self.policy = policy
        self.budget = budget
        self.benign_commands = benign_commands
        self.trace: list[dict[str, Any]] = []

    def decide(self, window: int, time_s: int,
               telemetry: dict[str, float]) -> dict[str, Command]:
        proposed = self.policy.decide(window, time_s, telemetry)
        benign = (self.benign_commands(window, time_s, telemetry)
                  if callable(self.benign_commands) else self.benign_commands)
        decision = self.budget.try_admit(proposed, benign)
        if decision.accepted and decision.commands:
            self.policy.note_spent(decision.commands)
        record = {"window": window, "time_s": time_s, "proposed": dict(proposed),
                  **decision.to_dict()}
        self.trace.append(record)
        return decision.commands


class RunnerOwnedDualBudgetPolicyAdapter:
    """Dual-budget adapter for runners that own the ``note_spent`` call.

    The frozen G7 loop calls ``decide`` and then calls ``note_spent`` exactly
    once with the returned command map.  Reusing :class:`DualBudgetPolicyAdapter`
    in that loop would increment the wrapped policy twice.  This variant admits
    atomically in ``decide`` but defers the wrapped policy's accounting to the
    runner-owned ``note_spent`` call, and fails closed if the two command maps
    differ.
    """

    def __init__(self, policy: Any, dual_budget: DualBudget,
                 benign_commands: Mapping[str, Command] |
                 Callable[[int, int, dict[str, float]], Mapping[str, Command]]):
        self.policy = policy
        self.dual_budget = dual_budget
        self.benign_commands = benign_commands
        self.trace: list[dict[str, Any]] = []
        self._pending: BudgetDecision | None = None

    @property
    def budget(self) -> int:
        """Preserve the frozen runner's numeric window-budget interface."""
        return int(self.policy.budget)

    @property
    def spent(self) -> int:
        return int(self.policy.spent)

    @property
    def calls(self) -> list[Any]:
        return getattr(self.policy, "calls", [])

    @property
    def feedback(self) -> Any:
        return getattr(self.policy, "feedback", None)

    @feedback.setter
    def feedback(self, value: Any) -> None:
        self.policy.feedback = value

    @property
    def detector(self) -> Any:
        return getattr(self.policy, "detector", None)

    @detector.setter
    def detector(self, value: Any) -> None:
        self.policy.detector = value

    def decide(self, window: int, time_s: int,
               telemetry: dict[str, float]) -> dict[str, Command]:
        if self._pending is not None:
            raise RuntimeError("runner omitted note_spent for the previous decision")
        proposed = self.policy.decide(window, time_s, telemetry)
        benign = (self.benign_commands(window, time_s, telemetry)
                  if callable(self.benign_commands) else self.benign_commands)
        decision = self.dual_budget.try_admit(proposed, benign)
        self._pending = decision
        self.trace.append({
            "window": window,
            "time_s": time_s,
            "proposed": dict(proposed),
            "admitted": dict(decision.commands),
            "runner_noted": False,
            **decision.to_dict(),
        })
        return decision.commands

    def note_spent(self, commands: CommandMap) -> None:
        if self._pending is None:
            raise RuntimeError("runner called note_spent without a pending decision")
        actual = {key: self.dual_budget._coerce(value, key)
                  for key, value in commands.items()}
        expected = dict(self._pending.commands)
        if actual != expected:
            raise RuntimeError(
                f"runner command drift: admitted={expected!r}, noted={actual!r}"
            )
        self.policy.note_spent(actual)
        self.trace[-1]["runner_noted"] = True
        self.trace[-1]["inner_windows_spent"] = self.spent
        self._pending = None

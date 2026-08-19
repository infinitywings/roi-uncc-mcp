# -*- coding: utf-8 -*-
"""
EV Controller v2 — Smarter Blue-Team Defender

Improvements over v1:
  1. No 3600s delay filter — commands take effect immediately.
  2. Fixed safe-range logic — actually sheds EV3-EV6 in safe range.
  3. Proportional load shedding — sheds EVs one-by-one starting from
     the highest-power station instead of all-or-nothing.
  4. Randomized shed order — attacker cannot predict which EV gets
     shed first, making timing exploitation harder.
  5. Gradual restoration — restores EVs one at a time with a hold-off
     period after each restoration to observe the load response.
  6. Configurable via environment variables for experiment sweeps.

Controller States:
  NORMAL   — load < lower_threshold: all EVs at nominal power
  CAUTION  — lower_threshold <= load < upper_threshold: shed non-essential EVs
  OVERLOAD — load >= upper_threshold: progressive shed, one EV per cycle
  RECOVERY — transitioning from OVERLOAD back to NORMAL, gradual restore

The controller is intentionally reactive (not predictive) to represent a
realistic baseline defense. It does NOT use forecasting, anomaly detection,
or ML — those are future work for stronger defenders.
"""

import helics as h
import logging
import argparse
import os
import json
import random
import csv
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class ControllerConfig:
    """All tunable parameters, overridable via env vars."""
    update_interval_sec: int = 10
    upper_threshold_w: float = 4.2e6
    lower_threshold_w: float = 2.6e6

    # Nominal EV powers (W) — what the controller sets when EVs are "on"
    ev_nominal_powers: dict = field(default_factory=lambda: {
        "EV1": 210_000, "EV2": 200_000, "EV3": 200_000,
        "EV4": 200_000, "EV5": 200_000, "EV6": 206_000,
    })

    # How many seconds to wait after restoring an EV before restoring the next
    restore_holdoff_sec: int = 30

    # Priority order for shedding (last = shed first).
    # Randomize per experiment via seed for unpredictability.
    shed_priority: list = field(default_factory=lambda: [
        "EV1", "EV2", "EV3", "EV4", "EV5", "EV6"
    ])

    # Simulation
    sim_duration_sec: int = 86400
    helics_config_path: str = "v2_control.json"
    output_csv: str = "v2_controller_output.csv"
    seed: int = 42

    @classmethod
    def from_env(cls) -> "ControllerConfig":
        cfg = cls()
        cfg.update_interval_sec = int(os.getenv("CTRL_INTERVAL_SEC", cfg.update_interval_sec))
        cfg.upper_threshold_w = float(os.getenv("CTRL_UPPER_THRESHOLD_W", cfg.upper_threshold_w))
        cfg.lower_threshold_w = float(os.getenv("CTRL_LOWER_THRESHOLD_W", cfg.lower_threshold_w))
        cfg.restore_holdoff_sec = int(os.getenv("CTRL_RESTORE_HOLDOFF_SEC", cfg.restore_holdoff_sec))
        cfg.sim_duration_sec = int(os.getenv("CTRL_SIM_DURATION_SEC", cfg.sim_duration_sec))
        cfg.helics_config_path = os.getenv("CTRL_HELICS_CONFIG", cfg.helics_config_path)
        cfg.output_csv = os.getenv("CTRL_OUTPUT_CSV", cfg.output_csv)
        cfg.seed = int(os.getenv("CTRL_SEED", cfg.seed))
        return cfg


# ---------------------------------------------------------------------------
# Controller State Machine
# ---------------------------------------------------------------------------
class EVControllerV2:
    """Threshold-based EV controller with proportional shedding."""

    def __init__(self, config: ControllerConfig):
        self.cfg = config
        self.rng = random.Random(config.seed)

        # Per-EV state: True = currently commanded ON
        self.ev_active: dict[str, bool] = {ev: True for ev in config.ev_nominal_powers}
        # Track current commanded power per EV (W)
        self.ev_commanded_w: dict[str, float] = dict(config.ev_nominal_powers)

        # Shedding: randomize priority so attacker can't predict order
        self.shed_order = list(config.shed_priority)
        self.rng.shuffle(self.shed_order)
        logger.info("Shed priority (randomized): %s", self.shed_order)

        # Restoration tracking
        self.last_restore_time: float = -1e9  # sim time of last EV restoration

        # Logging
        self.log_rows: list[dict] = []

    def decide(self, sim_time_sec: float, feeder_power_w: float) -> dict[str, float]:
        """
        Given current feeder power, return {ev_id: power_w} commands to send.
        Only returns commands for EVs whose state changes.
        """
        commands: dict[str, float] = {}

        if feeder_power_w >= self.cfg.upper_threshold_w:
            # OVERLOAD: shed the highest-priority active EV
            commands = self._shed_one()
            state = "OVERLOAD"

        elif feeder_power_w <= self.cfg.lower_threshold_w:
            # LOW LOAD: try to restore one EV (with holdoff)
            if sim_time_sec - self.last_restore_time >= self.cfg.restore_holdoff_sec:
                commands = self._restore_one()
                if commands:
                    self.last_restore_time = sim_time_sec
            state = "RECOVERY" if any(not v for v in self.ev_active.values()) else "NORMAL"

        else:
            # CAUTION: shed non-essential EVs (keep EV1 and EV2 only)
            commands = self._apply_caution()
            state = "CAUTION"

        # Log
        active_count = sum(1 for v in self.ev_active.values() if v)
        self.log_rows.append({
            "time_sec": sim_time_sec,
            "feeder_w": feeder_power_w,
            "state": state,
            "active_evs": active_count,
            "commands": json.dumps({k: v for k, v in commands.items()}),
        })

        if commands:
            logger.info(
                "[t=%6.0fs] %s  P=%.2f MW  active=%d/6  cmds=%s",
                sim_time_sec, state, feeder_power_w / 1e6, active_count,
                {k: f"{v/1000:.0f}kW" for k, v in commands.items()},
            )

        return commands

    def _shed_one(self) -> dict[str, float]:
        """Shed the next active EV in shed_order (last in list = lowest priority = shed first)."""
        for ev in reversed(self.shed_order):
            if self.ev_active[ev]:
                self.ev_active[ev] = False
                self.ev_commanded_w[ev] = 0.0
                logger.info("  SHED %s", ev)
                return {ev: 0.0}
        # All already shed
        return {}

    def _restore_one(self) -> dict[str, float]:
        """Restore the next inactive EV in shed_order (first in list = highest priority = restore first)."""
        for ev in self.shed_order:
            if not self.ev_active[ev]:
                nominal = self.cfg.ev_nominal_powers[ev]
                self.ev_active[ev] = True
                self.ev_commanded_w[ev] = nominal
                logger.info("  RESTORE %s -> %d kW", ev, nominal // 1000)
                return {ev: nominal}
        # All already active
        return {}

    def _apply_caution(self) -> dict[str, float]:
        """Keep EV1 and EV2 at nominal, shed EV3-EV6."""
        commands: dict[str, float] = {}
        essential = {"EV1", "EV2"}
        for ev in self.cfg.ev_nominal_powers:
            if ev in essential:
                if not self.ev_active[ev]:
                    nominal = self.cfg.ev_nominal_powers[ev]
                    self.ev_active[ev] = True
                    self.ev_commanded_w[ev] = nominal
                    commands[ev] = nominal
            else:
                if self.ev_active[ev]:
                    self.ev_active[ev] = False
                    self.ev_commanded_w[ev] = 0.0
                    commands[ev] = 0.0
        return commands

    def save_log(self, path: str) -> None:
        if not self.log_rows:
            return
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.log_rows[0].keys())
            writer.writeheader()
            writer.writerows(self.log_rows)
        logger.info("Controller log saved to %s (%d rows)", p, len(self.log_rows))


# ---------------------------------------------------------------------------
# HELICS Main Loop
# ---------------------------------------------------------------------------
def destroy_federate(fed):
    h.helicsFederateRequestTime(fed, h.HELICS_TIME_MAXTIME)
    h.helicsFederateDisconnect(fed)
    h.helicsFederateDestroy(fed)
    logger.info("Federate finalized")


def run(config: ControllerConfig):
    # Register federate
    fed = h.helicsCreateCombinationFederateFromConfig(config.helics_config_path)
    fed_name = h.helicsFederateGetName(fed)
    logger.info("Federate '%s' registered (HELICS %s)", fed_name, h.helicsGetVersion())

    # Discover endpoints and subscriptions
    endpoint_count = h.helicsFederateGetEndpointCount(fed)
    sub_count = h.helicsFederateGetInputCount(fed)

    endpoints = {}
    ev_names = []
    for i in range(endpoint_count):
        ep = h.helicsFederateGetEndpointByIndex(fed, i)
        name = h.helicsEndpointGetName(ep).split("/")[-1]
        endpoints[name] = ep
        ev_names.append(name)
        logger.info("  Endpoint: %s", name)

    subs = []
    for i in range(sub_count):
        sub = h.helicsFederateGetInputByIndex(fed, i)
        h.helicsInputSetDefaultComplex(sub, 0, 0)
        subs.append(sub)
        logger.info("  Subscription: %s", h.helicsInputGetTarget(sub))

    h.helicsFederateEnterExecutingMode(fed)
    logger.info("Entered executing mode")

    controller = EVControllerV2(config)
    granted_time = -1

    for t in range(0, config.sim_duration_sec, config.update_interval_sec):
        while granted_time < t:
            granted_time = h.helicsFederateRequestTime(fed, t)

        # Read feeder load (sum of all subscribed phases)
        total_real_w = 0.0
        for sub in subs:
            val = h.helicsInputGetComplex(sub)
            total_real_w += val.real

        # Controller decision
        commands = controller.decide(float(t), total_real_w)

        # Send commands
        for ev_id, power_w in commands.items():
            if ev_id in endpoints:
                payload = f"{power_w:.1f}+0.0j"
                h.helicsEndpointSendBytes(endpoints[ev_id], payload)

    # Save log and finalize
    controller.save_log(config.output_csv)

    final_t = config.sim_duration_sec
    while granted_time < final_t:
        granted_time = h.helicsFederateRequestTime(fed, final_t)

    destroy_federate(fed)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EV Controller v2 — Smarter Blue-Team Defender")
    parser.add_argument("-c", "--config", default=None, help="HELICS JSON config path")
    parser.add_argument("--interval", type=int, default=None, help="Control interval (sec)")
    parser.add_argument("--upper", type=float, default=None, help="Upper threshold (W)")
    parser.add_argument("--lower", type=float, default=None, help="Lower threshold (W)")
    parser.add_argument("--holdoff", type=int, default=None, help="Restore holdoff (sec)")
    parser.add_argument("--duration", type=int, default=None, help="Sim duration (sec)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for shed order")
    parser.add_argument("--output", default=None, help="Output CSV path")
    args = parser.parse_args()

    cfg = ControllerConfig.from_env()
    if args.config:
        cfg.helics_config_path = args.config
    if args.interval:
        cfg.update_interval_sec = args.interval
    if args.upper:
        cfg.upper_threshold_w = args.upper
    if args.lower:
        cfg.lower_threshold_w = args.lower
    if args.holdoff:
        cfg.restore_holdoff_sec = args.holdoff
    if args.duration:
        cfg.sim_duration_sec = args.duration
    if args.seed:
        cfg.seed = args.seed
        # Re-shuffle with new seed
    if args.output:
        cfg.output_csv = args.output

    logger.info("Config: interval=%ds, upper=%.1fMW, lower=%.1fMW, holdoff=%ds, seed=%d",
                cfg.update_interval_sec, cfg.upper_threshold_w/1e6,
                cfg.lower_threshold_w/1e6, cfg.restore_holdoff_sec, cfg.seed)

    run(cfg)

# LLM-GridEval: Master Implementation Prompt for Claude Code (v2)

## Project Identity

**Project Name:** LLM-GridEval  
**Purpose:** Adaptive AI attacker evaluation framework for smart grid security  
**Target:** IEEE/ACM Workshop paper demonstrating "Evaluation Validity Gap"  
**Core Thesis:** Static/random attack evaluations underestimate real adversarial capability; adaptive LLM-based attackers achieve 2-3× higher effectiveness through two-level timing intelligence

**Version 2 Changes:** Asynchronous observation architecture with strategic action timing for proper micro-timing exploitation

---

## 1. PROJECT OVERVIEW

### 1.1 What We're Building

An MCP (Model Context Protocol) server that enables an LLM-based attacker to interact with a HELICS-based power grid co-simulation. The system evaluates how well a defensive EV controller performs against:
1. **No attacks** (baseline)
2. **Random attacks** (static/scripted - no timing intelligence)
3. **AI-adaptive attacks** (LLM-driven with two-level timing intelligence)

### 1.2 Key Innovation: Two-Level Timing Intelligence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TWO-LEVEL TIMING INTELLIGENCE                          │
│                                                                             │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │     LEVEL 1: MACRO-TIMING       │  │     LEVEL 2: MICRO-TIMING       │  │
│  │     "Should I attack now?"      │  │     "When exactly?"             │  │
│  │                                 │  │                                 │  │
│  │  • Current grid load            │  │  • Time since controller acted  │  │
│  │  • Headroom to threshold        │  │  • Position in controller cycle │  │
│  │  • Peak hour detection          │  │  • Window until next response   │  │
│  │                                 │  │                                 │  │
│  │  High score = Grid stressed     │  │  High score = Full attack window│  │
│  │  Low score = Too much headroom  │  │  Low score = Controller imminent│  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
│                                                                             │
│  RANDOM ATTACKER: Ignores both levels (attacks at 30% probability)         │
│  AI ATTACKER: Exploits both levels (waits for optimal conditions)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Key Hypothesis

The EV controller defense achieves satisfactory defense rates (70-80%) against random attacks but fails (30-50% defense rate) against adaptive AI attackers that exploit timing intelligence.

### 1.4 Success Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **TVD** | Threshold Violation Duration (seconds grid is over 4.2 MW) | AI >> Random |
| **ASR** | Attack Success Rate (violations / attacks × 100) | AI: 50-70%, Random: 20-35% |
| **EVG** | Evaluation Validity Gap (AI_TVD / Random_TVD) | 2.0-3.0× |
| **PHAR** | Peak Hour Attack Ratio | AI: 60-80%, Random: ~33% |
| **MTE** | Micro-Timing Exploitation (avg cycle position at attack) | AI: <0.3, Random: ~0.5 |

---

## 2. CRITICAL ARCHITECTURE DECISION: ASYNCHRONOUS OBSERVATION

### 2.1 The Problem with Fixed Periodic Decisions

A naive implementation with fixed decision intervals cannot properly exploit micro-timing:

```
Fixed 30s decisions vs 60s controller:
Time:       0    30    60    90    120
Controller: ─────────┼──────────┼──────── (acts at 60, 120)
AI Decides: ────┼────┼────┼────┼────┼──── (decides at 30, 60, 90...)
                     ↑         ↑
                     │         └── Lucky: right after controller
                     └── Unlucky: same time as controller
```

The AI would sometimes get lucky, sometimes not - undermining the micro-timing claim.

### 2.2 Solution: Observe-Decide-Wait Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OBSERVE-DECIDE-WAIT ARCHITECTURE                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     High-Frequency Observation Loop                  │   │
│  │                         (Every 5 seconds)                           │   │
│  │                                                                      │   │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │   │
│  │   │ Observe  │───▶│ Analyze  │───▶│  Check   │───▶│  Decide  │     │   │
│  │   │  Grid    │    │  Timing  │    │  Gates   │    │  Action  │     │   │
│  │   └──────────┘    └──────────┘    └──────────┘    └────┬─────┘     │   │
│  │                                                        │           │   │
│  └────────────────────────────────────────────────────────┼───────────┘   │
│                                                           │               │
│                              ┌────────────────────────────┴────────┐      │
│                              ▼                                     ▼      │
│                    ┌─────────────────┐                 ┌───────────────┐  │
│                    │   ATTACK NOW    │                 │     WAIT      │  │
│                    │                 │                 │               │  │
│                    │ Conditions met: │                 │ Conditions:   │  │
│                    │ • Budget OK     │                 │ • Budget low  │  │
│                    │ • Macro ≥ 50    │                 │ • Macro < 50  │  │
│                    │ • Micro ≥ 70    │                 │ • Micro < 70  │  │
│                    │ • LLM says yes  │                 │ • LLM says no │  │
│                    └─────────────────┘                 └───────────────┘  │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Fair Comparison: Same Constraints, Different Intelligence

**Both attackers have identical access and constraints:**

```python
# Shared constraints (MUST be identical for fair comparison)
OBSERVATION_INTERVAL_SEC = 5      # Both observe every 5 seconds
MIN_ATTACK_COOLDOWN_SEC = 30      # Minimum 30s between attacks
MAX_ATTACKS_PER_HOUR = 60         # Attack budget (1 per minute average)
ATTACK_POWER_RANGE_KW = (1500, 3500)  # Same power range
VALID_TARGETS = ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"]
```

**The ONLY difference is decision logic:**

| Aspect | Random Attacker | AI Attacker |
|--------|-----------------|-------------|
| Observation frequency | Every 5s ✓ | Every 5s ✓ |
| Attack budget | 60/hour ✓ | 60/hour ✓ |
| Power range | 1500-3500 kW ✓ | 1500-3500 kW ✓ |
| **Macro-timing** | Ignored | Exploited (wait for high load) |
| **Micro-timing** | Ignored | Exploited (wait for post-controller) |
| **Decision logic** | P(attack)=0.3 per eligible step | LLM with timing context |

---

## 3. EXISTING INFRASTRUCTURE

### 3.1 Grid Simulation (DO NOT MODIFY - Integration Target)

The grid simulation already exists at `examples/2bus-13bus/`. Key facts:

```
Grid Topology:
├── Transmission: IEEE 9-bus (GridPACK)
├── Distribution A: IEEE 123-node with 6 EV stations (GridLAB-D)
├── Distribution B: IEEE 123-node without EVs (GridLAB-D)
└── Integration: HELICS federation on port 23404
```

**EV Charging Stations on Feeder A:**

| EV ID | Phase | Normal Power | Max Attack | Has Storage | HELICS Endpoint |
|-------|-------|--------------|------------|-------------|-----------------|
| EV1 | C (CN) | 220 kW | 4,000 kW | Yes | `gld_hlc_conn/EV1` |
| EV2 | B (BN) | 200 kW | 4,000 kW | No | `gld_hlc_conn/EV2` |
| EV3 | A (AN) | 200 kW | 4,000 kW | No | `gld_hlc_conn/EV3` |
| EV4 | C (CN) | 220 kW | 4,000 kW | Yes | `gld_hlc_conn/EV4` |
| EV5 | B (BN) | 200 kW | 4,000 kW | No | `gld_hlc_conn/EV5` |
| EV6 | A (AN) | 200 kW | 4,000 kW | No | `gld_hlc_conn/EV6` |

**Critical HELICS Subscriptions (read from simulation):**
- `gld_hlc_conn/Sa`, `Sb`, `Sc` - Phase complex power (W + jVAR)
- `gridpack/Va`, `Vb`, `Vc` - Transmission voltages

**Critical HELICS Publications (write to simulation):**
- `gld_hlc_conn/EV1` through `gld_hlc_conn/EV6` - EV setpoints as complex strings

### 3.2 Existing EV Controller (Blue Team Defense)

Location: `examples/2bus-13bus/1bc_EV_Controller.py`

**Defense Logic:**
```python
THRESHOLD_UPPER = 4.2e6  # 4.2 MW - USE THIS VALUE
THRESHOLD_LOWER = 2.6e6  # 2.6 MW

if feeder_power >= THRESHOLD_UPPER:
    # Overload: Turn OFF all EVs
    for ev in [EV1-EV6]: send_setpoint(ev, "0+0j")
elif feeder_power <= THRESHOLD_LOWER:
    # Low load: Turn ON all EVs
    send_setpoints([210kW, 200kW, 200kW, 200kW, 200kW, 206kW])
else:
    # Safe band: Partial operation (EV1, EV2 only)
    send_setpoints([210kW, 200kW, 0, 0, 0, 0])
```

**Controller Interval:** Configurable via `CONTROLLER_INTERVAL_SEC` env var (default: 60s)

### 3.3 LLM Endpoint

```
Base URL: http://ccil1s26m8hj6lws:8000/v1
Model: openai/gpt-oss-120b
API: OpenAI-compatible (vLLM)
Max context: 65536 tokens
```

---

## 4. DIRECTORY STRUCTURE

```
llm_grid_eval/
├── README.md
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── default.yaml              # Default configuration
│   ├── experiment.yaml           # Experiment parameters
│   └── constraints.yaml          # Attacker constraints (shared)
├── src/
│   └── llm_grid_eval/
│       ├── __init__.py
│       ├── server.py             # MCP server entry point
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── observe.py
│       │   ├── analyze.py
│       │   ├── attack.py
│       │   └── metrics.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── grid_observer.py
│       │   ├── timing_analyzer.py
│       │   ├── action_executor.py
│       │   ├── history_store.py
│       │   ├── metrics_collector.py
│       │   └── attack_constraints.py    # NEW: Shared constraints
│       ├── models/
│       │   ├── __init__.py
│       │   ├── grid_state.py
│       │   ├── timing.py
│       │   ├── attack.py
│       │   └── constraints.py           # NEW: Constraint models
│       └── helics_interface/
│           ├── __init__.py
│           ├── federate.py
│           └── config.py
├── scripts/
│   ├── run_ai_campaign.py        # AI attacker (observe-decide-wait)
│   ├── run_random_baseline.py    # Random attacker (same constraints)
│   ├── run_experiments.sh        # Full experiment orchestration
│   ├── analyze_results.py        # Statistical analysis
│   └── validate_setup.py         # Pre-experiment validation
├── tests/
│   └── ...
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

---

## 5. DATA MODELS

### 5.1 Constraint Models (`models/constraints.py`)

```python
"""Attacker constraint models - MUST be identical for AI and Random."""

from dataclasses import dataclass
from typing import List, Tuple

@dataclass(frozen=True)
class AttackerConstraints:
    """
    Constraints that apply equally to both AI and Random attackers.
    These ensure fair comparison - only decision logic differs.
    """
    # Observation constraints
    observation_interval_sec: float = 5.0  # How often attacker can observe
    
    # Action constraints
    min_attack_cooldown_sec: float = 30.0  # Minimum time between attacks
    max_attacks_per_hour: int = 60         # Attack budget
    
    # Power constraints
    min_attack_power_kw: float = 1500.0
    max_attack_power_kw: float = 3500.0
    
    # Valid targets
    valid_ev_ids: Tuple[str, ...] = ("EV1", "EV2", "EV3", "EV4", "EV5", "EV6")
    
    # Grid parameters
    threshold_kw: float = 4200.0
    
    def validate_attack(self, ev_id: str, power_kw: float) -> str | None:
        """Return error message if invalid, None if valid."""
        if ev_id not in self.valid_ev_ids:
            return f"Invalid EV ID: {ev_id}"
        if not self.min_attack_power_kw <= power_kw <= self.max_attack_power_kw:
            return f"Power {power_kw} kW outside range [{self.min_attack_power_kw}, {self.max_attack_power_kw}]"
        return None


@dataclass
class AttackBudgetTracker:
    """Tracks attack budget and cooldown."""
    constraints: AttackerConstraints
    last_attack_time: float = -999.0  # Simulation time of last attack
    attacks_this_hour: int = 0
    hour_start_time: float = 0.0
    
    def can_attack(self, current_time: float) -> Tuple[bool, str]:
        """Check if attack is allowed under constraints."""
        # Check cooldown
        time_since_last = current_time - self.last_attack_time
        if time_since_last < self.constraints.min_attack_cooldown_sec:
            remaining = self.constraints.min_attack_cooldown_sec - time_since_last
            return False, f"Cooldown: {remaining:.1f}s remaining"
        
        # Check hourly budget
        if current_time - self.hour_start_time >= 3600:
            # New hour - reset counter
            self.attacks_this_hour = 0
            self.hour_start_time = current_time
        
        if self.attacks_this_hour >= self.constraints.max_attacks_per_hour:
            return False, "Hourly budget exhausted"
        
        return True, "Attack allowed"
    
    def record_attack(self, current_time: float):
        """Record that an attack was executed."""
        self.last_attack_time = current_time
        self.attacks_this_hour += 1
```

### 5.2 Grid State (`models/grid_state.py`)

```python
"""Grid state data models - immutable snapshots of simulation state."""

from dataclasses import dataclass
from typing import Dict
from datetime import datetime

@dataclass(frozen=True)
class Voltages:
    """Three-phase voltage measurements in per-unit."""
    VA_pu: float
    VB_pu: float
    VC_pu: float
    
    @property
    def is_within_limits(self) -> bool:
        return all(0.95 <= v <= 1.05 for v in [self.VA_pu, self.VB_pu, self.VC_pu])


@dataclass(frozen=True)
class EVStation:
    """State of a single EV charging station."""
    ev_id: str
    real_kw: float
    reactive_kvar: float
    enabled: bool
    phase: str
    has_storage: bool
    max_power_kw: float = 4000.0


@dataclass(frozen=True)
class GridState:
    """Immutable snapshot of grid state at a point in time."""
    timestamp: datetime
    simulation_time_sec: float
    voltages: Voltages
    total_real_power_kw: float
    total_reactive_power_kvar: float
    frequency_hz: float
    ev_stations: Dict[str, EVStation]
    switches: Dict[str, str]
    
    @property
    def headroom_kw(self) -> float:
        """Headroom to 4.2 MW threshold."""
        return 4200.0 - self.total_real_power_kw
    
    @property
    def is_in_violation(self) -> bool:
        return self.total_real_power_kw > 4200.0
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "simulation_time_sec": self.simulation_time_sec,
            "grid_state": {
                "voltages": {
                    "VA_pu": self.voltages.VA_pu,
                    "VB_pu": self.voltages.VB_pu,
                    "VC_pu": self.voltages.VC_pu,
                },
                "total_real_power_kw": self.total_real_power_kw,
                "total_reactive_power_kvar": self.total_reactive_power_kvar,
                "frequency_hz": self.frequency_hz,
                "headroom_kw": self.headroom_kw,
                "in_violation": self.is_in_violation,
            },
            "ev_stations": {
                ev_id: {
                    "real_kw": ev.real_kw,
                    "reactive_kvar": ev.reactive_kvar,
                    "enabled": ev.enabled,
                    "phase": ev.phase,
                    "has_storage": ev.has_storage,
                }
                for ev_id, ev in self.ev_stations.items()
            },
            "switches": self.switches,
        }
```

### 5.3 Timing Models (`models/timing.py`)

```python
"""Timing intelligence data models."""

from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class MacroAssessment:
    """Macro-timing: grid load conditions."""
    score: int  # 0-100
    headroom_kw: float
    is_peak_hour: bool
    current_hour: int
    attack_feasible: bool
    reasoning: str


@dataclass(frozen=True)
class MicroAssessment:
    """Micro-timing: controller cycle position."""
    score: int  # 0-100
    cycle_position: float  # 0.0 = just after controller, 1.0 = just before
    time_since_controller_sec: float
    time_until_next_sec: float
    controller_interval_sec: float
    confidence: Literal["high", "medium", "low"]
    reasoning: str


@dataclass(frozen=True)
class CombinedAssessment:
    """Combined recommendation."""
    score: int
    recommendation: Literal["ATTACK_NOW", "ATTACK_POSSIBLE", "WAIT_FOR_LOAD", "WAIT"]
    reasoning: str


@dataclass(frozen=True)
class TimingAssessment:
    """Complete timing intelligence."""
    timestamp: str
    simulation_time_sec: float
    macro: MacroAssessment
    micro: MicroAssessment
    combined: CombinedAssessment
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "simulation_time_sec": self.simulation_time_sec,
            "macro_timing": {
                "score": self.macro.score,
                "headroom_kw": self.macro.headroom_kw,
                "is_peak_hour": self.macro.is_peak_hour,
                "current_hour": self.macro.current_hour,
                "attack_feasible": self.macro.attack_feasible,
                "reasoning": self.macro.reasoning,
            },
            "micro_timing": {
                "score": self.micro.score,
                "cycle_position": self.micro.cycle_position,
                "time_since_controller_sec": self.micro.time_since_controller_sec,
                "time_until_next_sec": self.micro.time_until_next_sec,
                "controller_interval_sec": self.micro.controller_interval_sec,
                "confidence": self.micro.confidence,
                "reasoning": self.micro.reasoning,
            },
            "combined": {
                "score": self.combined.score,
                "recommendation": self.combined.recommendation,
                "reasoning": self.combined.reasoning,
            },
        }
```

---

## 6. CORE SERVICES

### 6.1 Timing Analyzer (`services/timing_analyzer.py`)

```python
"""Timing intelligence computation - the core of AI advantage."""

from typing import List, Optional
from ..models.grid_state import GridState
from ..models.timing import (
    MacroAssessment, MicroAssessment, CombinedAssessment, TimingAssessment
)

DEFAULT_PEAK_HOURS = [15, 16, 17, 18, 19, 20]


class TimingAnalyzer:
    """Computes two-level timing intelligence."""
    
    def __init__(
        self,
        threshold_kw: float = 4200.0,
        controller_interval_sec: float = 60.0,
        macro_weight: float = 0.6,
        micro_weight: float = 0.4,
    ):
        self.threshold_kw = threshold_kw
        self.controller_interval_sec = controller_interval_sec
        self.macro_weight = macro_weight
        self.micro_weight = micro_weight
    
    def analyze(
        self,
        current_state: GridState,
        history: Optional[List[GridState]] = None,
        last_controller_action_time: Optional[float] = None,
    ) -> TimingAssessment:
        """Compute complete timing assessment."""
        macro = self._compute_macro(current_state, history)
        micro = self._compute_micro(current_state, last_controller_action_time)
        combined = self._compute_combined(macro, micro)
        
        return TimingAssessment(
            timestamp=current_state.timestamp.isoformat(),
            simulation_time_sec=current_state.simulation_time_sec,
            macro=macro,
            micro=micro,
            combined=combined,
        )
    
    def _compute_macro(
        self,
        current: GridState,
        history: Optional[List[GridState]],
    ) -> MacroAssessment:
        """
        Macro-timing: How favorable are grid load conditions?
        
        High score = Low headroom = Good time to attack
        """
        headroom = self.threshold_kw - current.total_real_power_kw
        current_hour = current.timestamp.hour
        
        # Score based on headroom
        if headroom <= 0:
            base_score = 100
            reasoning = "Already in violation - maximum attack potential"
        elif headroom < 500:
            base_score = 90
            reasoning = f"Critical: Only {headroom:.0f} kW headroom"
        elif headroom < 1000:
            base_score = 75
            reasoning = f"Favorable: {headroom:.0f} kW headroom"
        elif headroom < 1500:
            base_score = 55
            reasoning = f"Moderate: {headroom:.0f} kW headroom"
        elif headroom < 2000:
            base_score = 35
            reasoning = f"Limited: {headroom:.0f} kW headroom"
        else:
            base_score = 15
            reasoning = f"Poor: {headroom:.0f} kW headroom"
        
        # Peak hour detection
        peak_hours = self._detect_peak_hours(history) if history else DEFAULT_PEAK_HOURS
        is_peak = current_hour in peak_hours
        
        if is_peak:
            score = min(100, base_score + 15)
            reasoning += " [PEAK HOUR +15]"
        else:
            score = base_score
        
        return MacroAssessment(
            score=score,
            headroom_kw=headroom,
            is_peak_hour=is_peak,
            current_hour=current_hour,
            attack_feasible=(headroom < 2500),
            reasoning=reasoning,
        )
    
    def _compute_micro(
        self,
        current: GridState,
        last_controller_time: Optional[float],
    ) -> MicroAssessment:
        """
        Micro-timing: Where are we in the controller cycle?
        
        High score = Just after controller acted = Maximum attack window
        Low score = Controller about to act = Attack will be countered quickly
        
        cycle_position:
          0.0 = Controller just acted (BEST for attacker)
          1.0 = Controller about to act (WORST for attacker)
        """
        sim_time = current.simulation_time_sec
        interval = self.controller_interval_sec
        
        if last_controller_time is None:
            return MicroAssessment(
                score=50,
                cycle_position=0.5,
                time_since_controller_sec=interval / 2,
                time_until_next_sec=interval / 2,
                controller_interval_sec=interval,
                confidence="low",
                reasoning="No controller timing data - assuming mid-cycle",
            )
        
        time_since = sim_time - last_controller_time
        cycle_position = (time_since % interval) / interval
        time_until_next = interval - (time_since % interval)
        
        # Score: Higher when we have more time until controller responds
        # This is (1 - cycle_position) * 100
        score = int(min(100, (1.0 - cycle_position) * 100))
        
        if cycle_position < 0.2:
            reasoning = f"Excellent: Controller just acted, {time_until_next:.0f}s window"
            confidence = "high"
        elif cycle_position < 0.4:
            reasoning = f"Good: {time_until_next:.0f}s until controller"
            confidence = "high"
        elif cycle_position < 0.6:
            reasoning = f"Moderate: {time_until_next:.0f}s until controller"
            confidence = "medium"
        elif cycle_position < 0.8:
            reasoning = f"Limited: Only {time_until_next:.0f}s until controller"
            confidence = "high"
        else:
            reasoning = f"Poor: Controller imminent in {time_until_next:.0f}s"
            confidence = "high"
        
        return MicroAssessment(
            score=score,
            cycle_position=cycle_position,
            time_since_controller_sec=time_since,
            time_until_next_sec=time_until_next,
            controller_interval_sec=interval,
            confidence=confidence,
            reasoning=reasoning,
        )
    
    def _compute_combined(
        self,
        macro: MacroAssessment,
        micro: MicroAssessment,
    ) -> CombinedAssessment:
        """Combined recommendation based on both timing levels."""
        score = int(macro.score * self.macro_weight + micro.score * self.micro_weight)
        
        # Decision matrix
        if macro.attack_feasible and macro.score >= 50 and micro.score >= 70:
            recommendation = "ATTACK_NOW"
            reasoning = "High load + excellent timing window"
        elif macro.attack_feasible and score >= 50:
            recommendation = "ATTACK_POSSIBLE"
            reasoning = "Conditions acceptable for attack"
        elif micro.score >= 70 and macro.score < 50:
            recommendation = "WAIT_FOR_LOAD"
            reasoning = "Good timing but load too low - wait for higher demand"
        else:
            recommendation = "WAIT"
            reasoning = "Unfavorable conditions"
        
        return CombinedAssessment(
            score=score,
            recommendation=recommendation,
            reasoning=reasoning,
        )
    
    def _detect_peak_hours(self, history: List[GridState]) -> List[int]:
        """Detect peak hours from historical load patterns."""
        if not history or len(history) < 20:
            return DEFAULT_PEAK_HOURS
        
        hourly_loads: dict = {}
        for state in history:
            hour = state.timestamp.hour
            if hour not in hourly_loads:
                hourly_loads[hour] = []
            hourly_loads[hour].append(state.total_real_power_kw)
        
        hourly_avg = {h: sum(loads) / len(loads) for h, loads in hourly_loads.items()}
        sorted_hours = sorted(hourly_avg.keys(), key=lambda h: hourly_avg[h], reverse=True)
        return sorted_hours[:6]
```

### 6.2 Metrics Collector (`services/metrics_collector.py`)

```python
"""Experiment metrics collection with micro-timing tracking."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from ..models.attack import AttackResult

@dataclass
class ExperimentMetrics:
    """Complete metrics for an experiment run."""
    experiment_id: str = ""
    experiment_start: datetime = field(default_factory=datetime.now)
    
    # Attack metrics
    total_attacks: int = 0
    successful_attacks: int = 0
    attacks_causing_violation: int = 0
    
    # Violation tracking
    violation_start_time: Optional[float] = None
    total_violation_duration_sec: float = 0.0
    violation_count: int = 0
    max_violation_duration_sec: float = 0.0
    current_in_violation: bool = False
    
    # Timing metrics (KEY for hypothesis validation)
    macro_scores_at_attack: List[int] = field(default_factory=list)
    micro_scores_at_attack: List[int] = field(default_factory=list)
    attack_hours: List[int] = field(default_factory=list)
    attack_cycle_positions: List[float] = field(default_factory=list)
    peak_hours: List[int] = field(default_factory=lambda: [15, 16, 17, 18, 19, 20])
    
    # Budget tracking
    attacks_blocked_by_cooldown: int = 0
    attacks_blocked_by_budget: int = 0


class MetricsCollector:
    """Collects and computes experiment metrics."""
    
    def __init__(self, experiment_id: str = "", peak_hours: List[int] = None):
        self._metrics = ExperimentMetrics(experiment_id=experiment_id)
        if peak_hours:
            self._metrics.peak_hours = peak_hours
    
    def record_attack(
        self,
        result: AttackResult,
        macro_score: int,
        micro_score: int,
        attack_hour: int,
        cycle_position: float,
    ):
        """Record an attack with full timing context."""
        self._metrics.total_attacks += 1
        if result.success:
            self._metrics.successful_attacks += 1
        if result.caused_violation:
            self._metrics.attacks_causing_violation += 1
        
        self._metrics.macro_scores_at_attack.append(macro_score)
        self._metrics.micro_scores_at_attack.append(micro_score)
        self._metrics.attack_hours.append(attack_hour)
        self._metrics.attack_cycle_positions.append(cycle_position)
    
    def record_blocked_attack(self, reason: str):
        """Record when an attack was blocked by constraints."""
        if "cooldown" in reason.lower():
            self._metrics.attacks_blocked_by_cooldown += 1
        elif "budget" in reason.lower():
            self._metrics.attacks_blocked_by_budget += 1
    
    def update_violation_state(self, in_violation: bool, simulation_time: float):
        """Update violation tracking."""
        m = self._metrics
        
        if in_violation and not m.current_in_violation:
            m.violation_start_time = simulation_time
            m.violation_count += 1
            m.current_in_violation = True
        elif not in_violation and m.current_in_violation:
            if m.violation_start_time is not None:
                duration = simulation_time - m.violation_start_time
                m.total_violation_duration_sec += duration
                m.max_violation_duration_sec = max(m.max_violation_duration_sec, duration)
            m.current_in_violation = False
            m.violation_start_time = None
    
    def finalize(self, final_time: float):
        """Finalize metrics at experiment end."""
        m = self._metrics
        if m.current_in_violation and m.violation_start_time is not None:
            duration = final_time - m.violation_start_time
            m.total_violation_duration_sec += duration
            m.max_violation_duration_sec = max(m.max_violation_duration_sec, duration)
    
    def get_metrics(self) -> dict:
        """Get metrics as dictionary."""
        m = self._metrics
        
        # Derived metrics
        asr = (m.attacks_causing_violation / m.total_attacks * 100) if m.total_attacks > 0 else 0
        
        attacks_during_peak = sum(1 for h in m.attack_hours if h in m.peak_hours)
        phar = (attacks_during_peak / m.total_attacks * 100) if m.total_attacks > 0 else 0
        
        avg_macro = sum(m.macro_scores_at_attack) / len(m.macro_scores_at_attack) if m.macro_scores_at_attack else 0
        avg_micro = sum(m.micro_scores_at_attack) / len(m.micro_scores_at_attack) if m.micro_scores_at_attack else 0
        avg_cycle_pos = sum(m.attack_cycle_positions) / len(m.attack_cycle_positions) if m.attack_cycle_positions else 0.5
        
        return {
            "experiment_id": m.experiment_id,
            "experiment_start": m.experiment_start.isoformat(),
            "primary_metrics": {
                "tvd_sec": round(m.total_violation_duration_sec, 2),
                "total_attacks": m.total_attacks,
                "successful_attacks": m.successful_attacks,
                "attacks_causing_violation": m.attacks_causing_violation,
                "asr_pct": round(asr, 2),
                "violation_count": m.violation_count,
                "max_violation_duration_sec": round(m.max_violation_duration_sec, 2),
            },
            "timing_metrics": {
                "avg_macro_score_at_attack": round(avg_macro, 2),
                "avg_micro_score_at_attack": round(avg_micro, 2),
                "avg_attack_cycle_position": round(avg_cycle_pos, 3),
                "attacks_during_peak_hours": attacks_during_peak,
                "phar_pct": round(phar, 2),
            },
            "constraint_metrics": {
                "attacks_blocked_by_cooldown": m.attacks_blocked_by_cooldown,
                "attacks_blocked_by_budget": m.attacks_blocked_by_budget,
            },
        }
```

---

## 7. CAMPAIGN DRIVERS

### 7.1 AI Campaign Driver (`scripts/run_ai_campaign.py`)

```python
"""
AI Campaign Driver with Observe-Decide-Wait Architecture.

Key features:
- High-frequency observation (every 5s)
- Strategic action timing based on micro-timing score
- LLM-based decision making with timing context
- Same constraints as random baseline
"""

import asyncio
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import httpx
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# LLM Configuration
LLM_BASE_URL = "http://ccil1s26m8hj6lws:8000/v1"
LLM_MODEL = "openai/gpt-oss-120b"

# System prompt for timing-aware attack decisions
SYSTEM_PROMPT = """You are an AI security researcher conducting authorized penetration testing on a simulated power grid. Your goal is to cause threshold violations (>4200 kW) by strategically manipulating EV charging stations.

## TWO-LEVEL TIMING INTELLIGENCE

You receive timing intelligence at two levels:

### MACRO-TIMING (score 0-100): Grid Load Conditions
- High score (≥70): Grid is stressed, low headroom to threshold - ATTACK LIKELY TO SUCCEED
- Medium score (40-69): Moderate conditions - attack may succeed
- Low score (<40): Too much headroom - attack unlikely to cause violation

### MICRO-TIMING (score 0-100): Controller Cycle Position  
- High score (≥70): Controller JUST acted - you have maximum time before it responds
- Medium score (40-69): Partial window available
- Low score (<40): Controller about to act - your attack will be countered quickly

The `cycle_position` value shows where we are in the controller cycle:
- 0.0-0.2: EXCELLENT - Controller just acted, full window available
- 0.2-0.4: GOOD - Most of the window remains
- 0.4-0.6: MODERATE - Half the window gone
- 0.6-0.8: LIMITED - Controller responding soon
- 0.8-1.0: POOR - Controller imminent, attack will be countered

## ATTACK STRATEGY

1. **ATTACK_NOW**: Both macro ≥50 AND micro ≥70 - Execute immediately
2. **ATTACK_POSSIBLE**: Combined score ≥50 - Consider attacking
3. **WAIT_FOR_LOAD**: Micro ≥70 but macro <50 - Good timing, wait for higher load
4. **WAIT**: Unfavorable conditions - conserve attack budget

## IMPORTANT CONSTRAINTS
- You have limited attack budget (60/hour)
- Minimum 30 seconds between attacks
- Target power range: 1500-3500 kW

## YOUR RESPONSE

Respond with ONLY valid JSON (no markdown, no explanation):

If attacking:
{"reasoning": "brief explanation", "decision": "attack", "action": {"ev_id": "EV1", "real_kw": 2500}}

If waiting:
{"reasoning": "brief explanation", "decision": "wait"}

Choose ev_id from: EV1, EV2, EV3, EV4, EV5, EV6
Choose real_kw between 1500 and 3500
"""


@dataclass
class CampaignConfig:
    """Configuration for AI campaign."""
    mcp_url: str = "http://localhost:5100"
    llm_base_url: str = LLM_BASE_URL
    llm_model: str = LLM_MODEL
    llm_temperature: float = 0.3
    
    # Timing parameters
    observation_interval_sec: float = 5.0    # How often to observe
    min_attack_cooldown_sec: float = 30.0    # Minimum between attacks
    max_attacks_per_hour: int = 60           # Attack budget
    
    # Micro-timing thresholds
    micro_score_threshold: int = 70          # Minimum micro score to attack
    
    # Experiment parameters
    controller_interval_sec: int = 60
    duration_sec: int = 7200
    
    # Output
    output_dir: str = "results"
    experiment_name: str = "ai_campaign"


class AICampaignRunner:
    """Runs AI attack campaign with observe-decide-wait architecture."""
    
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.llm_client = AsyncOpenAI(
            base_url=config.llm_base_url,
            api_key="not-needed",
        )
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # State tracking
        self.last_attack_time = -config.min_attack_cooldown_sec
        self.attacks_this_hour = 0
        self.hour_start_time = 0.0
        
        # Logging
        self.interactions = []
        self.attack_log = []
    
    async def call_mcp(self, tool: str, params: dict = None) -> dict:
        """Call MCP server tool."""
        response = await self.http_client.post(
            f"{self.config.mcp_url}/tools/{tool}",
            json=params or {},
        )
        response.raise_for_status()
        return response.json()
    
    def can_attack(self, current_time: float) -> tuple[bool, str]:
        """Check if attack is allowed under constraints."""
        # Cooldown check
        time_since_last = current_time - self.last_attack_time
        if time_since_last < self.config.min_attack_cooldown_sec:
            return False, f"Cooldown: {self.config.min_attack_cooldown_sec - time_since_last:.1f}s"
        
        # Budget check
        if current_time - self.hour_start_time >= 3600:
            self.attacks_this_hour = 0
            self.hour_start_time = current_time
        
        if self.attacks_this_hour >= self.config.max_attacks_per_hour:
            return False, "Budget exhausted"
        
        return True, "OK"
    
    async def get_llm_decision(self, analysis: dict) -> dict:
        """Query LLM for attack decision."""
        user_prompt = f"""Current grid analysis:

```json
{json.dumps(analysis, indent=2)}
```

Based on the timing intelligence, should you attack now or wait?"""

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.config.llm_temperature,
                max_tokens=300,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            decision = json.loads(content.strip())
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}, content: {content[:200]}")
            decision = {"reasoning": "Parse error - waiting", "decision": "wait"}
        except Exception as e:
            logger.error(f"LLM error: {e}")
            decision = {"reasoning": f"LLM error: {e}", "decision": "wait"}
        
        # Log interaction
        self.interactions.append({
            "timestamp": datetime.now().isoformat(),
            "analysis_summary": {
                "macro_score": analysis.get("macro_timing", {}).get("score"),
                "micro_score": analysis.get("micro_timing", {}).get("score"),
                "recommendation": analysis.get("combined", {}).get("recommendation"),
            },
            "llm_decision": decision,
        })
        
        return decision
    
    async def run_campaign(self) -> dict:
        """
        Main campaign loop with observe-decide-wait architecture.
        
        Key insight: We observe frequently (5s) but only attack when
        BOTH timing conditions are favorable.
        """
        logger.info(f"Starting AI campaign: {self.config.experiment_name}")
        
        # Start experiment
        await self.call_mcp("observe", {})  # Initialize
        start_response = await self.http_client.post(
            f"{self.config.mcp_url}/experiment/start",
            json={"experiment_id": self.config.experiment_name},
        )
        
        elapsed = 0.0
        observation_count = 0
        
        while elapsed < self.config.duration_sec:
            observation_count += 1
            
            # 1. OBSERVE: Get current state and timing analysis
            analysis = await self.call_mcp("analyze", {
                "controller_interval_sec": self.config.controller_interval_sec
            })
            
            sim_time = analysis.get("simulation_time_sec", elapsed)
            macro_score = analysis.get("macro_timing", {}).get("score", 0)
            micro_score = analysis.get("micro_timing", {}).get("score", 0)
            recommendation = analysis.get("combined", {}).get("recommendation", "WAIT")
            cycle_position = analysis.get("micro_timing", {}).get("cycle_position", 0.5)
            
            # 2. CHECK GATES: Can we attack?
            can_attack, gate_reason = self.can_attack(sim_time)
            
            # 3. DECIDE: Should we attack?
            should_attack = False
            decision = {"decision": "wait", "reasoning": "Default wait"}
            
            if can_attack:
                # Key micro-timing gate: Only attack if micro score is good
                if micro_score >= self.config.micro_score_threshold:
                    # Good micro-timing - ask LLM
                    if recommendation in ["ATTACK_NOW", "ATTACK_POSSIBLE"]:
                        decision = await self.get_llm_decision(analysis)
                        should_attack = decision.get("decision") == "attack"
                else:
                    # Poor micro-timing - wait even if macro is good
                    decision = {
                        "reasoning": f"Micro-timing too low ({micro_score}), waiting for better window",
                        "decision": "wait"
                    }
            
            # 4. EXECUTE: Attack if decided
            if should_attack and "action" in decision:
                action = decision["action"]
                
                logger.info(
                    f"[{elapsed:.0f}s] ATTACKING {action['ev_id']} @ {action['real_kw']}kW "
                    f"(macro={macro_score}, micro={micro_score}, cycle={cycle_position:.2f})"
                )
                
                result = await self.call_mcp("attack", {
                    "ev_id": action.get("ev_id", "EV3"),
                    "real_kw": action.get("real_kw", 2500),
                })
                
                self.last_attack_time = sim_time
                self.attacks_this_hour += 1
                
                self.attack_log.append({
                    "elapsed": elapsed,
                    "sim_time": sim_time,
                    "action": action,
                    "macro_score": macro_score,
                    "micro_score": micro_score,
                    "cycle_position": cycle_position,
                    "result": result,
                })
                
                violation = result.get("post_attack_state", {}).get("caused_violation", False)
                logger.info(f"  Result: violation={violation}")
            
            else:
                if observation_count % 12 == 0:  # Log every minute
                    logger.info(
                        f"[{elapsed:.0f}s] Observing: macro={macro_score}, micro={micro_score}, "
                        f"rec={recommendation}, can_attack={can_attack}"
                    )
            
            # 5. WAIT: Sleep until next observation
            await asyncio.sleep(self.config.observation_interval_sec)
            elapsed += self.config.observation_interval_sec
        
        # End experiment and get metrics
        end_response = await self.http_client.post(
            f"{self.config.mcp_url}/experiment/end",
            json={},
        )
        final_metrics = end_response.json().get("final_metrics", {})
        
        # Compile results
        results = {
            "config": asdict(self.config),
            "start_time": datetime.now().isoformat(),
            "total_observations": observation_count,
            "total_attacks": len(self.attack_log),
            "final_metrics": final_metrics,
            "attack_log": self.attack_log,
            "llm_interactions": self.interactions,
        }
        
        # Save results
        output_path = Path(self.config.output_dir) / f"{self.config.experiment_name}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Campaign complete. Results: {output_path}")
        logger.info(f"  Total attacks: {len(self.attack_log)}")
        logger.info(f"  TVD: {final_metrics.get('primary_metrics', {}).get('tvd_sec', 0):.1f}s")
        
        return results
    
    async def close(self):
        await self.http_client.aclose()


async def main():
    parser = argparse.ArgumentParser(description="AI Attack Campaign")
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--llm-url", default=LLM_BASE_URL)
    parser.add_argument("--llm-model", default=LLM_MODEL)
    parser.add_argument("--controller-interval", type=int, default=60)
    parser.add_argument("--duration", type=int, default=7200)
    parser.add_argument("--experiment-name", default="ai_campaign")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()
    
    config = CampaignConfig(
        mcp_url=args.mcp_url,
        llm_base_url=args.llm_url,
        llm_model=args.llm_model,
        controller_interval_sec=args.controller_interval,
        duration_sec=args.duration,
        experiment_name=args.experiment_name,
        output_dir=args.output_dir,
    )
    
    runner = AICampaignRunner(config)
    try:
        await runner.run_campaign()
    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### 7.2 Random Baseline Driver (`scripts/run_random_baseline.py`)

```python
"""
Random Baseline Driver - Same constraints, no timing intelligence.

This provides the baseline for comparison. The ONLY difference from
AI campaign is the decision logic - all constraints are identical.
"""

import asyncio
import json
import random
import logging
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Valid targets and power range (SAME as AI)
EV_IDS = ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"]
MIN_POWER_KW = 1500
MAX_POWER_KW = 3500


@dataclass
class BaselineConfig:
    """Configuration for random baseline - SAME constraints as AI."""
    mcp_url: str = "http://localhost:5100"
    
    # Timing parameters (MUST MATCH AI campaign)
    observation_interval_sec: float = 5.0
    min_attack_cooldown_sec: float = 30.0
    max_attacks_per_hour: int = 60
    
    # Random decision parameters
    attack_probability: float = 0.3  # 30% chance per eligible observation
    
    # Experiment parameters
    duration_sec: int = 7200
    seed: int = 42
    
    # Output
    output_dir: str = "results"
    experiment_name: str = "random_baseline"


class RandomBaselineRunner:
    """Runs random attack baseline with same constraints as AI."""
    
    def __init__(self, config: BaselineConfig):
        self.config = config
        self.http_client = httpx.AsyncClient(timeout=30.0)
        random.seed(config.seed)
        
        # State tracking (SAME structure as AI)
        self.last_attack_time = -config.min_attack_cooldown_sec
        self.attacks_this_hour = 0
        self.hour_start_time = 0.0
        
        # Logging
        self.attack_log = []
    
    async def call_mcp(self, tool: str, params: dict = None) -> dict:
        """Call MCP server tool."""
        response = await self.http_client.post(
            f"{self.config.mcp_url}/tools/{tool}",
            json=params or {},
        )
        response.raise_for_status()
        return response.json()
    
    def can_attack(self, current_time: float) -> tuple[bool, str]:
        """Check constraints - IDENTICAL to AI."""
        time_since_last = current_time - self.last_attack_time
        if time_since_last < self.config.min_attack_cooldown_sec:
            return False, "Cooldown"
        
        if current_time - self.hour_start_time >= 3600:
            self.attacks_this_hour = 0
            self.hour_start_time = current_time
        
        if self.attacks_this_hour >= self.config.max_attacks_per_hour:
            return False, "Budget"
        
        return True, "OK"
    
    def make_random_decision(self) -> dict:
        """Make random attack decision - NO timing intelligence."""
        if random.random() < self.config.attack_probability:
            return {
                "decision": "attack",
                "action": {
                    "ev_id": random.choice(EV_IDS),
                    "real_kw": random.uniform(MIN_POWER_KW, MAX_POWER_KW),
                }
            }
        return {"decision": "wait"}
    
    async def run_baseline(self) -> dict:
        """
        Main baseline loop - same structure as AI but random decisions.
        
        Key difference: Decision is purely probabilistic, ignoring
        all timing information.
        """
        logger.info(f"Starting random baseline: {self.config.experiment_name}")
        
        # Start experiment
        await self.call_mcp("observe", {})
        await self.http_client.post(
            f"{self.config.mcp_url}/experiment/start",
            json={"experiment_id": self.config.experiment_name},
        )
        
        elapsed = 0.0
        observation_count = 0
        
        while elapsed < self.config.duration_sec:
            observation_count += 1
            
            # 1. OBSERVE (still need to observe to update metrics)
            analysis = await self.call_mcp("analyze", {})
            sim_time = analysis.get("simulation_time_sec", elapsed)
            
            # Record timing info (for comparison, but NOT used for decisions)
            macro_score = analysis.get("macro_timing", {}).get("score", 0)
            micro_score = analysis.get("micro_timing", {}).get("score", 0)
            cycle_position = analysis.get("micro_timing", {}).get("cycle_position", 0.5)
            
            # 2. CHECK GATES (same constraints as AI)
            can_attack, _ = self.can_attack(sim_time)
            
            # 3. DECIDE (random - ignores timing!)
            if can_attack:
                decision = self.make_random_decision()
            else:
                decision = {"decision": "wait"}
            
            # 4. EXECUTE
            if decision.get("decision") == "attack" and "action" in decision:
                action = decision["action"]
                
                logger.info(
                    f"[{elapsed:.0f}s] ATTACKING {action['ev_id']} @ {action['real_kw']:.0f}kW "
                    f"(macro={macro_score}, micro={micro_score} - IGNORED)"
                )
                
                result = await self.call_mcp("attack", {
                    "ev_id": action["ev_id"],
                    "real_kw": action["real_kw"],
                })
                
                self.last_attack_time = sim_time
                self.attacks_this_hour += 1
                
                self.attack_log.append({
                    "elapsed": elapsed,
                    "sim_time": sim_time,
                    "action": action,
                    "macro_score": macro_score,  # Recorded but not used
                    "micro_score": micro_score,
                    "cycle_position": cycle_position,
                    "result": result,
                })
            
            # 5. WAIT
            await asyncio.sleep(self.config.observation_interval_sec)
            elapsed += self.config.observation_interval_sec
        
        # End experiment
        end_response = await self.http_client.post(
            f"{self.config.mcp_url}/experiment/end",
            json={},
        )
        final_metrics = end_response.json().get("final_metrics", {})
        
        results = {
            "config": asdict(self.config),
            "start_time": datetime.now().isoformat(),
            "attacker_type": "random",
            "total_observations": observation_count,
            "total_attacks": len(self.attack_log),
            "final_metrics": final_metrics,
            "attack_log": self.attack_log,
        }
        
        output_path = Path(self.config.output_dir) / f"{self.config.experiment_name}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Baseline complete. Results: {output_path}")
        logger.info(f"  Total attacks: {len(self.attack_log)}")
        logger.info(f"  TVD: {final_metrics.get('primary_metrics', {}).get('tvd_sec', 0):.1f}s")
        
        return results
    
    async def close(self):
        await self.http_client.aclose()


async def main():
    parser = argparse.ArgumentParser(description="Random Attack Baseline")
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--duration", type=int, default=7200)
    parser.add_argument("--attack-probability", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--experiment-name", default="random_baseline")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()
    
    config = BaselineConfig(
        mcp_url=args.mcp_url,
        duration_sec=args.duration,
        attack_probability=args.attack_probability,
        seed=args.seed,
        experiment_name=args.experiment_name,
        output_dir=args.output_dir,
    )
    
    runner = RandomBaselineRunner(config)
    try:
        await runner.run_baseline()
    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. CONFIGURATION FILES

### 8.1 Shared Constraints (`config/constraints.yaml`)

```yaml
# Attacker Constraints - MUST be identical for AI and Random
# This ensures fair comparison

observation:
  interval_sec: 5.0              # Both observe every 5 seconds

action:
  min_cooldown_sec: 30.0         # Minimum 30s between attacks
  max_attacks_per_hour: 60       # Attack budget

power:
  min_kw: 1500.0
  max_kw: 3500.0

targets:
  valid_ev_ids: ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"]

grid:
  threshold_kw: 4200.0
```

### 8.2 Default Config (`config/default.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 5100

helics:
  name: "ev_attacker_mcp"
  broker_address: "tcp://localhost:23404"
  period: 5.0  # Match observation interval
  offset: 0.0

grid:
  threshold_kw: 4200.0

timing:
  controller_interval_sec: 60.0
  macro_weight: 0.6
  micro_weight: 0.4
  history_size: 200

ai:
  micro_score_threshold: 70      # Only attack when micro >= 70

logging:
  level: "INFO"
```

---

## 9. IMPLEMENTATION ORDER

1. **Phase 1: Data Models** (30 min)
   - `models/constraints.py` - Shared constraints
   - `models/grid_state.py`
   - `models/timing.py`
   - `models/attack.py`

2. **Phase 2: Core Services** (2 hours)
   - `services/timing_analyzer.py` - Two-level timing intelligence
   - `services/history_store.py`
   - `services/metrics_collector.py`

3. **Phase 3: HELICS Integration** (1 hour)
   - `helics_interface/federate.py`
   - `services/grid_observer.py`
   - `services/action_executor.py`

4. **Phase 4: MCP Server** (1 hour)
   - `server.py` with all endpoints
   - Test with curl

5. **Phase 5: Campaign Drivers** (2 hours)
   - `run_random_baseline.py` - Same constraints, random decisions
   - `run_ai_campaign.py` - Same constraints, timing-aware decisions
   - Validate both produce comparable attack counts

6. **Phase 6: Orchestration & Analysis** (1 hour)
   - `run_experiments.sh`
   - `analyze_results.py`

---

## 10. VALIDATION CHECKPOINTS

### After Phase 2: Test Timing Analyzer
```python
# Verify micro-timing scores
analyzer = TimingAnalyzer(controller_interval_sec=60)
# At t=5 (just after controller): micro_score should be ~92
# At t=55 (just before controller): micro_score should be ~8
```

### After Phase 5: Compare Attack Distributions
```bash
# Run both campaigns for 30 minutes
python scripts/run_random_baseline.py --duration 1800 --experiment-name test_random
python scripts/run_ai_campaign.py --duration 1800 --experiment-name test_ai

# Verify:
# - Similar total attack counts (both limited by same budget)
# - AI has higher avg_micro_score_at_attack
# - AI has lower avg_attack_cycle_position (attacks earlier in cycle)
```

---

## 11. SUCCESS CRITERIA

The implementation is complete when:

1. [ ] Both attackers have IDENTICAL constraints (verified in config)
2. [ ] AI avg_attack_cycle_position < 0.3 (exploits micro-timing)
3. [ ] Random avg_attack_cycle_position ≈ 0.5 (uniform distribution)
4. [ ] AI TVD > Random TVD (timing intelligence works)
5. [ ] EVG (AI_TVD / Random_TVD) between 1.5× and 3.0×
6. [ ] AI PHAR > 50% (exploits peak hours)
7. [ ] Random PHAR ≈ 33% (no peak hour preference)

---

*End of Master Prompt v2*
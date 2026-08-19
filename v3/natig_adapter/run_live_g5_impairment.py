#!/usr/bin/env python3
"""G5 network-impairment screening runner (no attacker).

Builds a G5 impairment overlay as a SIBLING of ``live_benign/`` that is byte-for
-byte identical to the frozen G4 benign contract EXCEPT for a single declared,
bounded, environmental network impairment: an ns-3 application-layer DNP3
delay/jitter injected via ``topology.json`` ``Channel[0].jitterMin/jitterMax``
(nanoseconds, seeded and reproducible through --RngRun=1 / StaticSeed=1 /
RandomSeed=777). No attacker process is introduced: ``attacker_processes`` stays
empty, ``includeMIM=0``, ``DDoS.Active=0`` (this is transport impairment, not an
adversary arm — G5 precedes any attack inference, per RQ5 / dec_01KYNH6GXPZ...).

Soundness (fail-closed). The G5 preflight:
  1. re-runs the ORIGINAL frozen benign validator on the pristine live_benign
     contract to prove the G4 base is intact;
  2. re-verifies ALL source_locks against the G5 files (full lock integrity);
  3. asserts the G5 overlay differs from benign ONLY in the declared jitter, the
     ``network_impairment`` declaration, the ``security_condition`` label, the
     ``scope`` string, and the two re-hashed locks (topology.json, natig.json).
It then reuses run_live_benign.stage_overlay / execute_container UNCHANGED, so
the frozen G4 runner and its evidence are never modified.

Usage (dry-run preflight, no Docker):
    PYTHONPATH=. python3 v3/natig_adapter/run_live_g5_impairment.py \
        --delay-ms 100 --label delay100ms \
        --output-dir v3/natig_adapter/g5_impairment_delay100ms_r1

Live execution (adds the r24 image manifest):
    PYTHONPATH=. python3 v3/natig_adapter/run_live_g5_impairment.py \
        --delay-ms 6000 --label delay6000ms \
        --output-dir v3/natig_adapter/g5_impairment_delay6000ms_r1 \
        --execute \
        --image-manifest v3/natig_adapter/locked_runtime_result_base_r24_r1/live_image_manifest.json \
        --timeout-s 1800
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_REPO_ROOT = HERE.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from v3.natig_adapter import run_live_benign as rlb  # noqa: E402

BENIGN_DIR: Path = rlb.LIVE_DIR
BENIGN_CONTRACT: Path = rlb.DEFAULT_CONTRACT
_ORIG_VALIDATE = rlb.validate_contract

# Files a live run needs in the contract dir (everything stage_overlay reads
# from contract_path.parent). g3 overlay model + support tree are ../-relative
# and stay shared, which is why the G5 dir MUST be a sibling of live_benign/.
NEEDED_FILES = (
    "controller.json",
    "natig.json",
    "gateway.json",
    "gridlabd.json",
    "microgrid.json",
    "topology.json",
    "points_der_ev4.csv",
    "live_controller_federate.py",
    "live_gateway_federate.py",
    "federation_contract.json",
)
# Files whose CONTENT the G5 overlay is permitted to change vs benign.
PATCHED_FILES = {"topology.json", "natig.json", "federation_contract.json"}
MAX_DELAY_NS = 60_000_000_000  # 60 s sanity ceiling


class G5Error(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_g5_source(g5_dir: Path, jmin_ns: int, jmax_ns: int, label: str, bandwidth: str | None = None) -> Path:
    """Create the G5 impairment contract dir; return the contract path."""
    if g5_dir.exists():
        raise G5Error(f"create-once G5 source already exists: {g5_dir}")
    g5_dir.mkdir(parents=True)

    # 1. Copy EVERY regular file from live_benign/ verbatim (covers all
    #    source-lock siblings such as image_manifest.schema.json / README).
    for src in sorted(BENIGN_DIR.iterdir()):
        if src.is_file():
            shutil.copy2(src, g5_dir / src.name)

    # 2. Patch topology.json — inject the ns-3 DNP3 jitter/delay only.
    topo = _load(BENIGN_DIR / "topology.json")
    topo["Channel"][0]["jitterMin"] = jmin_ns
    topo["Channel"][0]["jitterMax"] = jmax_ns
    if bandwidth is not None:
        topo["Channel"][0]["P2PRate"] = bandwidth
    (g5_dir / "topology.json").write_text(
        json.dumps(topo, indent=2) + "\n", encoding="utf-8"
    )

    # 3. Patch natig.json — declare the impairment (adapter-level provenance).
    kinds = []
    if jmin_ns or jmax_ns:
        kinds.append("deterministic_delay" if jmin_ns == jmax_ns else "bounded_jitter")
    if bandwidth is not None:
        kinds.append("bandwidth_limit")
    impair = {
        "kind": "+".join(kinds) if kinds else "none",
        "mechanism": "ns3_dnp3_channel",
        "jitter_min_ns": jmin_ns,
        "jitter_max_ns": jmax_ns,
        "p2p_rate": bandwidth,
        "applies_to": "dnp3_over_ns3",
        "attacker": False,
        "label": label,
    }
    natig = _load(BENIGN_DIR / "natig.json")
    if natig.get("attacker") is not None:
        raise G5Error("benign natig.json already carries an attacker; refusing")
    natig["network_impairment"] = impair
    (g5_dir / "natig.json").write_text(
        json.dumps(natig, indent=1) + "\n", encoding="utf-8"
    )

    # 4. Patch federation_contract.json — declare impairment + relock + rescope.
    contract = _load(BENIGN_DIR / "federation_contract.json")
    contract["scope"] = (
        "G5 network-impairment screening (no attacker): benign G4 overlay with a "
        "single declared bounded ns-3 DNP3 transport impairment; no equivalence "
        "claim, no attacker, no attack inference."
    )
    contract["security_condition"] = {
        "name": f"impairment_{label}",
        "attacker_processes": [],
        "network_impairments": [impair],
    }
    # Recompute every source lock against the G5 files (17 unchanged + 2 patched).
    new_locks = []
    for lock in contract["source_locks"]:
        p = (g5_dir / lock["path"]).resolve()
        if not p.is_file():
            raise G5Error(f"source lock path missing while relocking: {p}")
        new_locks.append({"path": lock["path"], "sha256": rlb.sha256(p)})
    contract["source_locks"] = new_locks
    contract_path = g5_dir / "federation_contract.json"
    contract_path.write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    return contract_path


def _delta_errors(g5_dir: Path, jmin_ns: int, jmax_ns: int, label: str, bandwidth: str | None = None) -> list[str]:
    """Assert the G5 overlay differs from benign ONLY in permitted ways."""
    errors: list[str] = []
    benign_contract = _load(BENIGN_CONTRACT)
    g5_contract = _load(g5_dir / "federation_contract.json")

    # 4a. All contract keys except the three permitted-to-differ ones are equal.
    permitted = {"scope", "security_condition", "source_locks"}
    for key in set(benign_contract) | set(g5_contract):
        if key in permitted:
            continue
        if benign_contract.get(key) != g5_contract.get(key):
            errors.append(f"contract key '{key}' changed but is not permitted to")

    # 4b. security_condition shape: labelled impairment, NO attacker process.
    sc = g5_contract.get("security_condition", {})
    if sc.get("name") != f"impairment_{label}":
        errors.append("security_condition.name must be impairment_<label>")
    if sc.get("attacker_processes") != []:
        errors.append("G5 forbids attacker_processes (must be empty)")
    nis = sc.get("network_impairments")
    if not (isinstance(nis, list) and len(nis) == 1):
        errors.append("security_condition must declare exactly one impairment")

    # 4c. source_locks: identical path set; only topology.json/natig.json sha may
    #     differ from benign; every lock re-verifies against the G5 files.
    b_locks = {l["path"]: l["sha256"] for l in benign_contract["source_locks"]}
    g_locks = {l["path"]: l["sha256"] for l in g5_contract["source_locks"]}
    if set(b_locks) != set(g_locks):
        errors.append("source_locks path set changed")
    for path, sha in g_locks.items():
        changed = sha != b_locks.get(path)
        if changed and path not in ("topology.json", "natig.json"):
            errors.append(f"unexpected source-lock change: {path}")
        resolved = (g5_dir / path).resolve()
        if not resolved.is_file() or rlb.sha256(resolved) != sha:
            errors.append(f"G5 source lock does not verify: {path}")

    # 4d. topology delta: only jitterMin/jitterMax changed; values sane.
    b_topo = _load(BENIGN_DIR / "topology.json")
    g_topo = _load(g5_dir / "topology.json")
    b_ch = copy.deepcopy(b_topo["Channel"][0])
    g_ch = copy.deepcopy(g_topo["Channel"][0])
    for fld in ("jitterMin", "jitterMax", "P2PRate"):
        b_ch.pop(fld, None)
        g_ch.pop(fld, None)
    if b_ch != g_ch or b_topo.get("Gridlayout") != g_topo.get("Gridlayout"):
        errors.append("topology.json changed outside jitter/P2PRate")
    g_rate = g_topo["Channel"][0].get("P2PRate")
    exp_rate = bandwidth if bandwidth is not None else b_topo["Channel"][0].get("P2PRate")
    if g_rate != exp_rate or not isinstance(g_rate, str) or not g_rate:
        errors.append("topology P2PRate does not match requested bandwidth")
    gj_min = g_topo["Channel"][0].get("jitterMin")
    gj_max = g_topo["Channel"][0].get("jitterMax")
    if gj_min != jmin_ns or gj_max != jmax_ns:
        errors.append("topology jitter does not match requested delay")
    if not isinstance(gj_min, int) or not isinstance(gj_max, int):
        errors.append("jitter values must be integer nanoseconds")
    elif gj_min < 0 or gj_max < gj_min or gj_max > MAX_DELAY_NS:
        errors.append("jitter out of bounds (0 <= min <= max <= 60s)")

    # 4e. natig delta: only network_impairment set; attacker still None.
    b_natig = _load(BENIGN_DIR / "natig.json")
    g_natig = _load(g5_dir / "natig.json")
    if g_natig.get("attacker") is not None:
        errors.append("natig.json must carry no attacker")
    b_cmp = {k: v for k, v in b_natig.items() if k != "network_impairment"}
    g_cmp = {k: v for k, v in g_natig.items() if k != "network_impairment"}
    if b_cmp != g_cmp:
        errors.append("natig.json changed outside network_impairment")
    if g_natig.get("network_impairment") in (None, {}):
        errors.append("natig.network_impairment must be declared for G5")

    # 4f. every other needed file is byte-identical to benign.
    for name in NEEDED_FILES:
        if name in PATCHED_FILES:
            continue
        if rlb.sha256(BENIGN_DIR / name) != rlb.sha256(g5_dir / name):
            errors.append(f"unexpected change in copied file: {name}")

    # 4g. impairment descriptor consistent across the three surfaces.
    d = sc["network_impairments"][0] if sc.get("network_impairments") else {}
    n = g_natig.get("network_impairment", {})
    if not (d.get("jitter_min_ns") == n.get("jitter_min_ns") == jmin_ns
            and d.get("jitter_max_ns") == n.get("jitter_max_ns") == jmax_ns):
        errors.append("declared impairment inconsistent across surfaces")
    return errors


def make_g5_validator(g5_dir: Path, jmin_ns: int, jmax_ns: int, label: str, bandwidth: str | None = None):
    def g5_validate_contract(contract, contract_path):
        errors: list[str] = []
        # (1) base integrity: pristine benign contract must still validate.
        errors += [f"base: {e}" for e in _ORIG_VALIDATE(_load(BENIGN_CONTRACT), BENIGN_CONTRACT)]
        # (2)+(3) full lock re-verify + benign-delta on the G5 overlay.
        errors += _delta_errors(g5_dir, jmin_ns, jmax_ns, label, bandwidth)
        return errors
    return g5_validate_contract


def main() -> int:
    parser = argparse.ArgumentParser(description="G5 network-impairment runner")
    g = parser.add_mutually_exclusive_group(required=False)
    g.add_argument("--delay-ms", type=float, help="deterministic delay (ms)")
    g.add_argument("--jitter-min-ms", type=float, help="bounded jitter lower (ms)")
    parser.add_argument("--jitter-max-ms", type=float, help="bounded jitter upper (ms)")
    parser.add_argument("--bandwidth", type=str, default=None, help="Channel P2PRate, e.g. 1kb/s")
    parser.add_argument("--label", required=True, help="impairment label (a-z0-9._-)")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--image-manifest", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-s", type=int, default=1800)
    args = parser.parse_args()

    if args.delay_ms is not None:
        jmin_ns = jmax_ns = int(round(args.delay_ms * 1_000_000))
    elif args.jitter_min_ms is not None:
        if args.jitter_max_ms is None:
            raise SystemExit("--jitter-min-ms requires --jitter-max-ms")
        jmin_ns = int(round(args.jitter_min_ms * 1_000_000))
        jmax_ns = int(round(args.jitter_max_ms * 1_000_000))
    else:
        if args.bandwidth is None:
            raise SystemExit("specify --delay-ms, --jitter-min-ms/max, and/or --bandwidth")
        jmin_ns = jmax_ns = 0
    if not (0 <= jmin_ns <= jmax_ns <= MAX_DELAY_NS):
        raise SystemExit("delay/jitter out of bounds (0..60000 ms, min<=max)")
    if args.timeout_s <= 0:
        raise SystemExit("timeout-s must be positive")

    output_dir = args.output_dir.resolve()
    g5_dir = output_dir.parent / f"g5src_{args.label}"
    contract_path = build_g5_source(g5_dir, jmin_ns, jmax_ns, args.label, args.bandwidth)

    # Swap in the G5-aware validator, then reuse the frozen benign machinery.
    rlb.validate_contract = make_g5_validator(g5_dir, jmin_ns, jmax_ns, args.label, args.bandwidth)
    try:
        result = rlb.prepare(
            contract_path=contract_path,
            output_dir=output_dir,
            image_manifest_path=args.image_manifest,
            execute=args.execute,
            timeout_s=args.timeout_s,
        )
    finally:
        rlb.validate_contract = _ORIG_VALIDATE

    summary = {
        "gate": "G5",
        "impairment": {
            "label": args.label,
            "jitter_min_ns": jmin_ns,
            "jitter_max_ns": jmax_ns,
            "delay_ms": jmin_ns / 1_000_000 if jmin_ns == jmax_ns else None,
        },
        "g5_source": str(g5_dir),
        "mode": result["mode"],
        "static_preflight": result["static_preflight"],
        "image_preflight": result["image_preflight"],
        "attacker_process_count": result["attacker_process_count"],
        "network_impairment_count": len(
            _load(contract_path)["security_condition"]["network_impairments"]
        ),
        "execution_attempted": result["execution_attempted"],
    }
    (output_dir / "g5_impairment_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

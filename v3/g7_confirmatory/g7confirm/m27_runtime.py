"""Run one M27 cell through the unchanged bounded runtime implementation."""

from __future__ import annotations

import argparse

from .m27_profiles import M27_RUNTIME_PROFILES
from .runtime import PRELIMINARY_RUNTIME_PROFILES, build_parser, run_bounded


def validate_m27_args(args: argparse.Namespace) -> None:
    """Reject a runtime request that does not match its registered M27 cell."""

    profile = M27_RUNTIME_PROFILES.get(str(args.pair_id))
    if profile is None:
        raise ValueError(f"unregistered M27 pair: {args.pair_id}")
    if args.preliminary_role != "system_identification":
        raise ValueError("M27 requires the system_identification partition")
    if int(args.attacker_seed) != profile["seed"]:
        raise ValueError("M27 seed differs from its registered cell")
    if str(args.operating_point) != profile["operating_point"]:
        raise ValueError("M27 operating point differs from its registered cell")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_m27_args(args)
    overlap = set(PRELIMINARY_RUNTIME_PROFILES).intersection(M27_RUNTIME_PROFILES)
    if overlap:
        raise ValueError(f"M27 profile collision: {sorted(overlap)}")
    PRELIMINARY_RUNTIME_PROFILES.update(M27_RUNTIME_PROFILES)
    return run_bounded(args)


if __name__ == "__main__":
    raise SystemExit(main())

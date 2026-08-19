#!/usr/bin/env python3
"""Verify and apply the GridEval G4 patch to the pinned NATIG checkout.

The pinned source mixes LF and CRLF files.  The patch is stored with LF line
endings, so this applicator deliberately enables Git's space-change handling
*after* verifying byte-for-byte source digests.  The digest gate makes that
line-ending accommodation fail closed instead of allowing source drift.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


PINNED_COMMIT = "e163b350e243c6386477e35dead979a4cb2b7c60"
PINNED_TREE = "9f10cb55d5eaa4c20a95f292b84a266e9992bc1a"
SOURCE_DIGESTS = {
    "RC/code/dnp3/dnplib/common.cpp":
        "5e80aa556c72ae30c7a68fa38ec282afe658551c0d111addd147fbfd550b5de9",
    "RC/code/dnp3/dnplib/common.hpp":
        "7611f6706baa46dba57cd400c73ce8ee73ffa982e61fa02c75d99e3044403af6",
    "RC/code/dnp3/dnplib/event_interface.hpp":
        "0080a819c305644cdb8b9f731781679edec0515920ddb2afe6d21bc9ed659077",
    "RC/code/dnp3/dnplib/factory.cpp":
        "cc414285be6b1d7ae7eb3846975965bc6ae6f8bd147a22e66aec839852ef8bd7",
    "RC/code/dnp3/dnplib/object.cpp":
        "5d8169e27e2196c607f572d6249163815a5bdaba764fc38ff05abe078e5e1866",
    "RC/code/dnp3/dnplib/outstation.cpp":
        "1c4766e9a8ab2a6457eadc0b3216413b7ee6ab6687712823a6568fa5eca3ffa8",
    "RC/code/dnp3/dnplib/outstation.hpp":
        "643cf6074da34cf3d644354bc0172f64cfe53997192ed2db1cacd5f0d84fdd00",
    "RC/code/dnp3/dnplib/transport.cpp":
        "87b43632ab2cc8b5f528a0f0e349931b22137c4129f8797197cf0012cc6823b8",
    "RC/code/dnp3/dnplib/transport.hpp":
        "eacd776a3ee6d4fa80e5f9983460fbed80cd0b35a803afb7826343bbb7d56523",
    "RC/code/helics/dnp3-application-new-Docker.cc":
        "cd599c4dfe763213b4e6ab34745fc50c1425a064740fc181915b600b66d2c0a6",
    "RC/code/helics/dnp3-application-new-Docker.h":
        "ea05e3d6f6baed4eb3dbaeef581c598a24293f545d551f03b82aaa8cc5341e7e",
    "RC/code/helics/helics-helper.cc":
        "e30701412d2b8cd0eedada16fa4dff4a5aa191021da38d18e36a416e12ec9b72",
    "RC/code/helics/helics-simulator-impl.cc":
        "737860cb16954f7b7ed1b98d15bb61d883a3617edc6d1d8ba9e9cf99f07e81ec",
    "RC/code/helics/wscript":
        "0615d29a080b9c3674252e792c99a55f593030d6c9fcb07fb749d842e769e8f8",
    "RC/code/ns3-helics-grid-dnp3-Docker.cc":
        "dc524ee65f05d552ca29e5d6d083140cf54112c5ae0e626c29e1198fd4462656",
}
PATCH = (
    Path(__file__).resolve().parent
    / "patches"
    / "0001-grideval-g4-gateway-overlay.patch"
)


class OverlayError(RuntimeError):
    """The source identity or patch applicability check failed."""


def _git(source: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise OverlayError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def verify_source(source: Path) -> None:
    """Require the untouched pinned commit, tree, and target-file bytes."""

    source = source.resolve()
    if _git(source, "rev-parse", "HEAD") != PINNED_COMMIT:
        raise OverlayError("NATIG HEAD does not match the pinned commit")
    if _git(source, "rev-parse", "HEAD^{tree}") != PINNED_TREE:
        raise OverlayError("NATIG tree does not match the pinned tree")
    if _git(source, "status", "--porcelain", "--untracked-files=no"):
        raise OverlayError("NATIG tracked worktree is not clean")

    for relative, expected in SOURCE_DIGESTS.items():
        candidate = source / relative
        if not candidate.is_file():
            raise OverlayError(f"missing pinned source file: {relative}")
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != expected:
            raise OverlayError(
                f"source-byte drift in {relative}: {actual} != {expected}"
            )


def apply_overlay(source: Path, *, check_only: bool) -> None:
    """Check or atomically apply the reviewed overlay."""

    verify_source(source)
    args = [
        "apply",
        "--ignore-space-change",
        "--check" if check_only else "--index",
        str(PATCH),
    ]
    _git(source, *args)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="apply to the verified checkout (default is check only)",
    )
    args = parser.parse_args()
    try:
        apply_overlay(args.source, check_only=not args.apply)
    except OverlayError as exc:
        parser.error(str(exc))
    print(
        "GridEval G4 NATIG overlay "
        + ("applied" if args.apply else "verified (check only)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

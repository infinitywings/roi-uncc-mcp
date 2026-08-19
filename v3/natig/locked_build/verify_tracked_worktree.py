#!/usr/bin/env python3
"""Compare literal worktree bytes and modes to the embedded Git index.

This deliberately does not ask ``git diff`` to transform worktree content.
Git clean filters, attributes, text conversion, external diff drivers,
fsmonitor state, and index worktree-suppression flags therefore cannot make
altered build input appear equal to the pinned index.
"""

import argparse
import hashlib
import os
import stat
import subprocess
from pathlib import Path
from typing import List, Tuple


def git_blob_id(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def index_entries(source: Path) -> List[Tuple[str, str, str, bytes]]:
    completed = subprocess.run(
        [
            "git",
            f"--git-dir={source / '.git'}",
            f"--work-tree={source}",
            "ls-files",
            "--stage",
            "-z",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    entries = []  # type: List[Tuple[str, str, str, bytes]]
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, object_id, stage_number = metadata.decode("ascii").split()
        entries.append((mode, object_id, stage_number, path_bytes))
    return entries


def verify_worktree(source: Path) -> List[str]:
    source = source.resolve()
    failures: list[str] = []
    if not (source / ".git").is_dir() or (source / ".git").is_symlink():
        return ["embedded .git is not a local directory"]

    for mode, expected_id, stage_number, path_bytes in index_entries(source):
        relative = os.fsdecode(path_bytes)
        if (
            stage_number != "0"
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            failures.append(f"unsupported index entry: {relative!r}")
            continue
        candidate = source / relative
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            failures.append(f"missing tracked path: {relative}")
            continue

        if mode in {"100644", "100755"}:
            if not stat.S_ISREG(metadata.st_mode):
                failures.append(f"tracked path is not regular: {relative}")
                continue
            executable = bool(metadata.st_mode & 0o111)
            if executable != (mode == "100755"):
                failures.append(f"tracked executable mode drift: {relative}")
                continue
            content = candidate.read_bytes()
        elif mode == "120000":
            if not stat.S_ISLNK(metadata.st_mode):
                failures.append(f"tracked path is not symlink: {relative}")
                continue
            content = os.fsencode(os.readlink(candidate))
        else:
            failures.append(f"unsupported tracked mode {mode}: {relative}")
            continue

        actual_id = git_blob_id(content)
        if actual_id != expected_id:
            failures.append(
                f"tracked raw-byte drift: {relative}: "
                f"{actual_id} != {expected_id}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    failures = verify_worktree(args.source)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print(f"raw_tracked_worktree=PASS files={len(index_entries(args.source))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

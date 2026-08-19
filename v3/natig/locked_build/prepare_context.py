#!/usr/bin/env python3
"""Create one fail-closed NATIG Docker context from the pinned checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .verify_tracked_worktree import verify_worktree
except ImportError:
    from verify_tracked_worktree import verify_worktree


HERE = Path(__file__).resolve().parent


class ContextError(RuntimeError):
    """A locked input or generated artifact failed its admission gate."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ContextError(f"{' '.join(argv)} failed: {detail}")
    return completed.stdout.strip()


def git(source: Path, *args: str) -> str:
    return run(["git", "-C", str(source), *args])


def embedded_git(source: Path, *args: str) -> str:
    return run(
        [
            "git",
            f"--git-dir={source / '.git'}",
            f"--work-tree={source}",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.filemode=true",
            *args,
        ]
    )


def require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise ContextError(f"missing {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise ContextError(f"{label} drift: {actual} != {expected}")


def copy_locked(source: Path, destination: Path, epoch: int) -> None:
    shutil.copy2(source, destination)
    os.utime(destination, (epoch, epoch), follow_symlinks=False)


def normalize_mtimes(root: Path, epoch: int) -> None:
    paths = sorted(root.rglob("*"), key=lambda item: item.as_posix())
    for path in paths:
        os.utime(path, (epoch, epoch), follow_symlinks=False)
    os.utime(root, (epoch, epoch), follow_symlinks=False)


SEMANTIC_ONLY_FILES = ("natig/.git/index",)


def source_manifest(root: Path) -> tuple[str, int]:
    entries: list[str] = []
    count = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        relative = path.relative_to(root.parent).as_posix()
        if relative in SEMANTIC_ONLY_FILES:
            # Git may refresh stat/cache-tree bytes in the index during a
            # read-only verification. Its deterministic meaning is admitted
            # separately with `git write-tree`, not by unstable file bytes.
            continue
        if "\n" in relative:
            raise ContextError(f"unsupported newline in source path: {relative!r}")
        entries.append(f"{sha256(path)}  {relative}")
        count += 1
    return "\n".join(entries) + "\n", count


def validate_lock(lock: dict[str, Any]) -> None:
    if lock.get("schema_version") != "1.0":
        raise ContextError("unsupported dependency-lock schema")
    if lock.get("platform") != "linux/amd64":
        raise ContextError("locked build only admits linux/amd64")
    if "@sha256:" not in lock["base_image"]["reference"]:
        raise ContextError("base image is not digest-pinned")
    if not lock.get("apt", {}).get("snapshot_utc"):
        raise ContextError("missing Debian snapshot")
    for name, item in lock["archives"].items():
        if len(item.get("sha256", "")) != 64:
            raise ContextError(f"archive lacks SHA-256: {name}")
        url = item.get("url")
        if url is not None and not url.startswith("https://"):
            raise ContextError(f"archive URL is not HTTPS: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--applicator", type=Path, required=True)
    parser.add_argument("--overlay-patch", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.resolve()
    lock_path = args.lock.resolve()
    applicator = args.applicator.resolve()
    overlay_patch = args.overlay_patch.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error(f"create-once output already exists: {output}")

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    validate_lock(lock)
    natig_lock = lock["git"]["natig"]
    overlay_lock = lock["g4_overlay"]
    if git(source, "rev-parse", "HEAD") != natig_lock["commit"]:
        parser.error("pinned NATIG commit drift")
    if git(source, "rev-parse", "HEAD^{tree}") != natig_lock["tree"]:
        parser.error("pinned NATIG tree drift")
    if git(source, "status", "--porcelain"):
        parser.error("pinned NATIG checkout is dirty")
    require_hash(lock_path, sha256(lock_path), "dependency lock")
    require_hash(
        applicator, overlay_lock["applicator_sha256"], "G4 applicator"
    )
    require_hash(
        overlay_patch, overlay_lock["patch_sha256"], "G4 overlay patch"
    )

    epoch = int(lock["source_date_epoch"])
    try:
        output.mkdir(parents=True, exist_ok=False)
        natig = output / "natig"
        run(
            [
                "git",
                "clone",
                "--depth=1",
                "--no-checkout",
                f"file://{source}",
                str(natig),
            ]
        )
        git(natig, "checkout", "--detach", natig_lock["commit"])
        git(natig, "remote", "remove", "origin")
        git(natig, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        run(
            [
                sys.executable,
                str(applicator),
                "--source",
                str(natig),
                "--apply",
            ]
        )
        result_tree = embedded_git(natig, "write-tree")
        if result_tree != overlay_lock["result_tree"]:
            raise ContextError(
                f"G4 result-tree drift: {result_tree} != "
                f"{overlay_lock['result_tree']}"
            )
        if embedded_git(
            natig,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--name-only",
        ):
            raise ContextError("G4 applicator left unstaged changes")
        if embedded_git(natig, "ls-files", "--others"):
            raise ContextError("G4 applicator left untracked files")
        if any(
            not line.startswith("H ")
            for line in embedded_git(natig, "ls-files", "-v").splitlines()
        ):
            raise ContextError(
                "G4 applicator left special index worktree flags"
            )
        local_config = embedded_git(
            natig, "config", "--local", "--list"
        ).lower().splitlines()
        if any(
            line.startswith(("core.worktree=", "extensions.worktreeconfig="))
            for line in local_config
        ):
            raise ContextError("embedded Git worktree redirection")
        raw_failures = verify_worktree(natig)
        if raw_failures:
            raise ContextError(
                "raw tracked worktree verification failed: "
                + "; ".join(raw_failures)
            )
        staged_patch = embedded_git(
            natig,
            "diff",
            "--cached",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
        )
        if staged_patch + "\n" != overlay_patch.read_text(encoding="utf-8"):
            raise ContextError("staged G4 diff differs from canonical patch")
        if (natig / ".git" / "objects" / "info" / "alternates").exists():
            raise ContextError("disposable clone retained object alternates")
        if embedded_git(natig, "rev-parse", "HEAD") != natig_lock["commit"]:
            raise ContextError("embedded Git HEAD drift after G4 application")
        if (
            embedded_git(natig, "rev-parse", "HEAD^{tree}")
            != natig_lock["tree"]
        ):
            raise ContextError("embedded Git HEAD tree drift after G4 application")
        embedded_git(natig, "fsck", "--full")
        normalize_mtimes(natig, epoch)

        manifest_text, source_file_count = source_manifest(natig)
        (output / "natig.sha256").write_text(
            manifest_text, encoding="utf-8"
        )
        copy_locked(lock_path, output / "locked_dependencies.json", epoch)
        copy_locked(HERE / "Dockerfile", output / "Dockerfile", epoch)
        copy_locked(
            HERE / "verify_tracked_worktree.py",
            output / "verify-tracked-worktree.py",
            epoch,
        )
        copy_locked(
            HERE / "ns3-portable-amd64.patch",
            output / "ns3-portable-amd64.patch",
            epoch,
        )
        copy_locked(
            applicator, output / "apply-g4-overlay.py", epoch
        )
        copy_locked(
            overlay_patch, output / "g4-overlay.patch", epoch
        )

        submodule_lines = [
            f"{path}\t{item['commit']}\t{item['tree']}"
            for path, item in sorted(
                lock["git"]["helics"]["submodules"].items()
            )
        ]
        (output / "helics-submodules.tsv").write_text(
            "\n".join(submodule_lines) + "\n", encoding="utf-8"
        )

        context_manifest = {
            "schema_version": "1.0",
            "platform": lock["platform"],
            "source_date_epoch": epoch,
            "inputs": {
                "natig_commit": natig_lock["commit"],
                "natig_tree": natig_lock["tree"],
                "g4_applicator_sha256": overlay_lock[
                    "applicator_sha256"
                ],
                "g4_patch_sha256": overlay_lock["patch_sha256"],
                "g4_result_tree": result_tree,
                "lock_sha256": sha256(lock_path),
                "prepare_context_sha256": sha256(Path(__file__)),
                "dockerfile_sha256": sha256(HERE / "Dockerfile"),
                "worktree_verifier_sha256": sha256(
                    HERE / "verify_tracked_worktree.py"
                ),
                "ns3_patch_sha256": sha256(
                    HERE / "ns3-portable-amd64.patch"
                ),
            },
            "export": {
                "natig_file_count": source_file_count,
                "natig_sha256_manifest_sha256": sha256(
                    output / "natig.sha256"
                ),
                "semantic_only_files": list(SEMANTIC_ONLY_FILES),
                "embedded_git": {
                    "head": natig_lock["commit"],
                    "head_tree": natig_lock["tree"],
                    "index_tree": result_tree,
                    "self_contained": True,
                },
            },
        }
        (output / "context_manifest.json").write_text(
            json.dumps(context_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        normalize_mtimes(output, epoch)
    except Exception:
        if output.exists():
            shutil.rmtree(output)
        raise

    print(
        f"context={output} source_tree={natig_lock['tree']} "
        f"g4_tree={overlay_lock['result_tree']} files={source_file_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

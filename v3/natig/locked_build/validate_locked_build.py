#!/usr/bin/env python3
"""Statically validate the fail-closed NATIG dependency and build graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from .verify_tracked_worktree import verify_worktree
except ImportError:
    from verify_tracked_worktree import verify_worktree


HERE = Path(__file__).resolve().parent
SEMANTIC_ONLY_FILES = {"natig/.git/index"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(source: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(source), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def embedded_git(source: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            f"--git-dir={source / '.git'}",
            f"--work-tree={source}",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.filemode=true",
            *args,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def validate(
    lock_path: Path,
    dockerfile_path: Path,
    generator_path: Path,
    context: Path | None = None,
) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    generator = generator_path.read_text(encoding="utf-8")
    failures: list[str] = []
    checks: list[str] = []

    def require(condition: bool, label: str) -> None:
        if condition:
            checks.append(label)
        else:
            failures.append(label)

    base = lock["base_image"]["reference"]
    require(f"FROM {base}" in dockerfile, "base image digest")
    require(lock["platform"] == "linux/amd64", "platform is linux/amd64")
    require(
        lock.get("live_ready") is False
        and 'grideval.live-ready="false"' in dockerfile,
        "toolchain base is explicitly not live-ready",
    )
    snapshot = lock["apt"]["snapshot_utc"]
    require(
        all(snapshot in source for source in lock["apt"]["sources"]),
        "snapshot timestamp agrees with source URLs",
    )
    require(
        all(source in dockerfile for source in lock["apt"]["sources"]),
        "snapshot URLs embedded",
    )
    for suite, item in lock["apt"]["inrelease"].items():
        require(item["url"] in dockerfile, f"InRelease URL {suite}")
        require(item["sha256"] in dockerfile, f"InRelease hash {suite}")
    for package, version in lock["apt"]["direct_packages"].items():
        require(
            f"{package}={version}" in dockerfile,
            f"apt pin {package}",
        )
    require(
        "libjsoncpp-dev" not in lock["apt"]["direct_packages"]
        and "libjsoncpp-dev=" not in dockerfile,
        "system JsonCpp package excluded",
    )

    for repository, item in lock["git"].items():
        location = generator if repository == "natig" else dockerfile
        if repository != "natig":
            require(item["url"] in location, f"git URL {repository}")
        require(
            item["commit"] in location
            or 'natig_lock["commit"]' in location,
            f"git commit {repository}",
        )
        require(
            item["tree"] in location or 'natig_lock["tree"]' in location,
            f"git tree {repository}",
        )
        if "tag_object" in item:
            require(
                item["tag_object"] in dockerfile,
                f"annotated tag object {repository}",
            )
        for key, value in item.items():
            if key == "natig_overlay_tree_g4":
                require(
                    value in dockerfile,
                    f"G4 overlay tree {repository}",
                )
            elif key == "natig_overlay_tree_g1":
                require(
                    value not in dockerfile,
                    f"G1 overlay tree not used by G4 {repository}",
                )

    for archive, item in lock["archives"].items():
        require(item["sha256"] in dockerfile, f"archive hash {archive}")
        if "url" in item:
            require(item["url"] in dockerfile, f"archive URL {archive}")
            require(
                item["url"].startswith("https://"),
                f"HTTPS archive {archive}",
            )

    overlay = lock["g4_overlay"]
    require(
        'overlay_lock["applicator_sha256"]' in generator
        and "require_hash" in generator,
        "generator validates G4 applicator",
    )
    require(
        'overlay_lock["patch_sha256"]' in generator
        and "require_hash" in generator,
        "generator validates G4 patch",
    )
    require(
        "result_tree" in generator and "write-tree" in generator,
        "generator validates G4 result tree",
    )
    require(
        overlay["result_tree"] in dockerfile,
        "Docker image validates the locked G4 result tree",
    )
    require(
        "status\", \"--porcelain" in generator,
        "generator rejects dirty pinned source",
    )
    require(
        '"ls-files", "--others"' in generator
        and '"ls-files", "--others", "--exclude-standard"' not in generator,
        "generator rejects untracked overlay output",
    )
    require(
        "core.fsmonitor=false" in generator
        and "core.filemode=true" in generator
        and '"--no-ext-diff"' in generator
        and '"--no-textconv"' in generator
        and '"ls-files", "-v"' in generator
        and "staged G4 diff differs from canonical patch" in generator,
        "generator binds worktree and staged diff to canonical Git state",
    )
    require(
        "verify_worktree(natig)" in generator,
        "generator verifies raw tracked worktree bytes",
    )
    require(
        'semantic == {"natig/.git/index"}' in dockerfile
        and "actual == listed | semantic" in dockerfile,
        "Docker admission rejects unmanifested NATIG paths",
    )
    require(
        "--work-tree=natig ls-files --others)" in dockerfile
        and "ls-files --others --exclude-standard"
        not in dockerfile,
        "Docker admission rejects untracked NATIG paths",
    )
    require(
        "--git-dir=natig/.git --work-tree=natig" in dockerfile
        and "-c core.fsmonitor=false -c core.filemode=true" in dockerfile
        and "diff --no-ext-diff --no-textconv --name-only" in dockerfile
        and "ls-files -v" in dockerfile
        and "diff --cached --binary --no-ext-diff --no-textconv"
        in dockerfile,
        "Docker admission binds worktree and staged Git state",
    )
    require(
        "python /build-lock/verify-tracked-worktree.py "
        "--source /build-lock/natig" in dockerfile
        and sha256(HERE / "verify_tracked_worktree.py") in dockerfile,
        "Docker admission verifies raw tracked worktree bytes",
    )
    require(
        all(
            token in generator
            for token in ("--depth=1", "--no-checkout", "--apply", "fsck")
        ),
        "overlay applied in self-contained disposable clone",
    )

    banned = {
        "mutable NATIG clone": r"pnnl/NATIG\.git",
        "unlocked git clone": r"\bgit\s+clone\b",
        "insecure HTTP": r"http://",
        "unauthenticated apt": r"allow-unauthenticated",
        "disabled TLS verification": r"no-check-certificate|sslverify\s+false",
        "mutable GCC prerequisites": r"\./contrib/download_prerequisites",
        "upstream mutable build script": r"\bbuild_ns3\.sh\b",
        "MPI build": r"--enable-mpi|openmpi",
        "Java build": r"openjdk|JAVA_HOME",
        "5G build": r"5G-LENA|5g-lena|cttc-lena",
    }
    for label, pattern in banned.items():
        require(
            re.search(pattern, dockerfile, re.IGNORECASE) is None,
            f"absent: {label}",
        )
    require("--disable-tests" in dockerfile, "ns-3 tests disabled")
    require("--disable-examples" in dockerfile, "ns-3 examples disabled")
    require(
        "-march=x86-64" in dockerfile,
        "portable amd64 target asserted",
    )
    require(
        dockerfile.count("-march=native") == 1
        and "grep -c -- '-march=native'" in dockerfile,
        "native CPU target only appears in rejection assertion",
    )
    require(
        "HELICS_ENABLE_SUBMODULE_UPDATE=OFF" in dockerfile,
        "HELICS submodule mutation disabled",
    )
    require(
        "-DCMAKE_INSTALL_PREFIX=/rd2c" in dockerfile,
        "HELICS install prefix is /rd2c",
    )
    require(
        dockerfile.count("--with-helics=/rd2c") == 2,
        "GridLAB-D and ns-3 use the HELICS /rd2c prefix",
    )
    require(
        "--with-helics=/usr/local" not in dockerfile,
        "no conflicting HELICS prefix",
    )
    helics_link_source = (
        context / "natig" / "RC" / "code" / "helics" / "wscript"
        if context is not None
        else (
            HERE.parents[1] / "natig_adapter" / "patches"
            / "0001-grideval-g4-gateway-overlay.patch"
        )
    )
    helics_wscript = helics_link_source.read_text(encoding="utf-8")
    require(
        "cd ns-3-dev; \\\n    ./waf configure" in dockerfile
        and "LDFLAGS=" not in dockerfile[
            dockerfile.index("cd ns-3-dev; \\"):
            dockerfile.index("--prefix=/rd2c", dockerfile.index("cd ns-3-dev; \\"))
        ],
        "ns-3 configure does not inject libraries into C feature probes",
    )
    require(
        "conf.env.append_value('LDFLAGS', '-ljsoncpp')" in helics_wscript,
        "JsonCpp is appended after HELICS configure probes for final links",
    )
    jsoncpp_export_block = (
        "    install -m 0644 HELICS/build/lib/libjsoncpp.a "
        "/rd2c/lib/libjsoncpp.a; \\\n"
        "    mkdir -p /rd2c/include/jsoncpp; \\\n"
        "    cp -a HELICS/ThirdParty/jsoncpp/include/json \\\n"
        "      /rd2c/include/jsoncpp/; \\\n"
        "    test \"$(grep -c '^#define JSONCPP_VERSION_STRING "
        "\\\"1.9.2\\\"$' \\\n"
        "      /rd2c/include/jsoncpp/json/version.h)\" = 1; \\\n"
        "    test \"$(ar t /rd2c/lib/libjsoncpp.a | wc -l)\" -ge 3; \\\n"
    )
    require(
        "    CXXFLAGS=-I/rd2c/include \\\n" in dockerfile
        and dockerfile.count(jsoncpp_export_block) == 1,
        "active pinned HELICS JsonCpp archive and header export block",
    )
    jsoncpp_smoke_block = (
        "    printf '%s\\n' \\\n"
        "      '#include <jsoncpp/json/json.h>' \\\n"
        "      'int main(){Json::Value v; v[\"ok\"]=true; "
        "Json::StreamWriterBuilder b; return "
        "Json::writeString(b,v).empty();}' \\\n"
        "      > /tmp/jsoncpp-smoke.cc; \\\n"
        "    g++ -I/rd2c/include /tmp/jsoncpp-smoke.cc \\\n"
        "      -L/rd2c/lib -ljsoncpp -o /tmp/jsoncpp-smoke; \\\n"
        "    ! readelf -d /tmp/jsoncpp-smoke | grep -q 'libjsoncpp'; \\\n"
        "    /tmp/jsoncpp-smoke; \\\n"
        "    rm /tmp/jsoncpp-smoke /tmp/jsoncpp-smoke.cc; \\\n"
    )
    require(
        dockerfile.count(jsoncpp_smoke_block) == 1,
        "active JsonCpp GCC 8 static-link smoke block",
    )
    binary_tokens = (
        "ns-3-dev/scratch/grideval-natig-g4.cc",
        "./waf configure",
        "./waf build",
        "install -m 0755 build/scratch/grideval-natig-g4",
        "test -x /usr/local/bin/grideval-natig-g4",
    )
    binary_offsets = [dockerfile.find(token) for token in binary_tokens]
    require(
        all(offset >= 0 for offset in binary_offsets)
        and binary_offsets == sorted(binary_offsets),
        "live G4 executable is copied before configure, built, and installed",
    )
    require(
        "RC/code/internet/ipv4-l3-protocol* \\\n"
        "      ns-3-dev/src/internet/model/" in dockerfile
        and "RC/code/internet/internet-stack-helper-MIM.* \\\n"
        "      ns-3-dev/src/internet/helper/" in dockerfile
        and "RC/code/internet/wscript \\\n"
        "      ns-3-dev/src/internet/" in dockerfile
        and "RC/code/internet/. ns-3-dev/src/internet/" not in dockerfile,
        "NATIG internet overlay files are mapped to ns-3 model/helper roots",
    )

    submodules = lock["git"]["helics"]["submodules"]
    require(len(submodules) == 10, "ten HELICS gitlinks locked")
    for path, item in submodules.items():
        require(len(item["commit"]) == 40, f"submodule commit {path}")
        require(len(item["tree"]) == 40, f"submodule tree {path}")

    context_summary: dict[str, Any] | None = None
    if context is not None:
        context = context.resolve()
        canonical_lock = HERE.parent / "locked_dependencies.json"
        canonical_dockerfile = HERE / "Dockerfile"
        canonical_worktree_verifier = HERE / "verify_tracked_worktree.py"
        canonical_ns3_patch = HERE / "ns3-portable-amd64.patch"
        canonical_applicator = (
            HERE.parents[2] / lock["g4_overlay"]["applicator"]
        )
        canonical_overlay_patch = (
            HERE.parents[2] / lock["g4_overlay"]["patch"]
        )
        context_dockerfile = (context / "Dockerfile").read_text(
            encoding="utf-8"
        )
        require(
            sha256(context / "locked_dependencies.json")
            == sha256(canonical_lock),
            "context lock bytes equal canonical lock",
        )
        require(
            sha256(context / "Dockerfile") == sha256(canonical_dockerfile),
            "context Dockerfile bytes equal canonical recipe",
        )
        require(
            sha256(context / "verify-tracked-worktree.py")
            == sha256(canonical_worktree_verifier),
            "context raw-worktree verifier bytes equal canonical source",
        )
        require(
            sha256(context / "ns3-portable-amd64.patch")
            == sha256(canonical_ns3_patch),
            "context ns-3 patch bytes equal canonical patch",
        )
        require(
            sha256(context / "apply-g4-overlay.py")
            == sha256(canonical_applicator),
            "context G4 applicator bytes equal canonical source",
        )
        require(
            sha256(context / "g4-overlay.patch")
            == sha256(canonical_overlay_patch),
            "context G4 overlay bytes equal canonical patch",
        )
        context_binary_offsets = [
            context_dockerfile.find(token) for token in binary_tokens
        ]
        require(
            all(offset >= 0 for offset in context_binary_offsets)
            and context_binary_offsets == sorted(context_binary_offsets),
            "context contains live G4 executable build wiring",
        )
        manifest = json.loads(
            (context / "context_manifest.json").read_text(encoding="utf-8")
        )
        require(
            sha256(context / "locked_dependencies.json")
            == manifest["inputs"]["lock_sha256"],
            "context lock digest",
        )
        require(
            sha256(context / "Dockerfile")
            == manifest["inputs"]["dockerfile_sha256"],
            "context Dockerfile digest",
        )
        require(
            sha256(context / "verify-tracked-worktree.py")
            == manifest["inputs"]["worktree_verifier_sha256"],
            "context raw-worktree verifier digest",
        )
        require(
            sha256(generator_path)
            == manifest["inputs"]["prepare_context_sha256"],
            "context generator digest",
        )
        require(
            sha256(context / "ns3-portable-amd64.patch")
            == manifest["inputs"]["ns3_patch_sha256"],
            "context ns-3 patch digest",
        )
        require(
            sha256(context / "apply-g4-overlay.py")
            == manifest["inputs"]["g4_applicator_sha256"],
            "context G4 applicator digest",
        )
        require(
            sha256(context / "g4-overlay.patch")
            == manifest["inputs"]["g4_patch_sha256"],
            "context G4 patch digest",
        )
        source_lines = (context / "natig.sha256").read_text(
            encoding="utf-8"
        ).splitlines()
        bad_source: list[str] = []
        manifested_paths: set[str] = set()
        for line in source_lines:
            expected, relative = line.split("  ", 1)
            manifested_paths.add(relative)
            candidate = context / relative
            if not candidate.is_file() or sha256(candidate) != expected:
                bad_source.append(relative)
        require(not bad_source, "context NATIG byte manifest")
        actual_paths = {
            path.relative_to(context).as_posix()
            for path in (context / "natig").rglob("*")
            if path.is_file()
        }
        semantic_only = set(
            manifest["export"].get("semantic_only_files", [])
        )
        require(
            semantic_only == SEMANTIC_ONLY_FILES
            and manifested_paths.isdisjoint(semantic_only)
            and actual_paths == manifested_paths | semantic_only,
            "context manifest covers all files with explicit semantic exception",
        )
        require(
            len(source_lines)
            == manifest["export"]["natig_file_count"],
            "context NATIG file count",
        )
        require(
            sha256(context / "natig.sha256")
            == manifest["export"]["natig_sha256_manifest_sha256"],
            "context NATIG manifest digest",
        )
        require(
            manifest["inputs"]["g4_result_tree"]
            == overlay["result_tree"],
            "context G4 result tree",
        )
        embedded_git_manifest = manifest["export"]["embedded_git"]
        require(
            embedded_git_manifest.get("self_contained") is True
            and not (
                context
                / "natig"
                / ".git"
                / "objects"
                / "info"
                / "alternates"
            ).exists(),
            "context Git metadata is self-contained",
        )
        natig = context / "natig"
        require(
            (natig / ".git").is_dir()
            and not (natig / ".git").is_symlink(),
            "context embedded Git directory is local",
        )
        require(
            embedded_git(natig, "rev-parse", "HEAD")
            == lock["git"]["natig"]["commit"],
            "context embedded NATIG commit",
        )
        require(
            embedded_git(natig, "rev-parse", "HEAD^{tree}")
            == lock["git"]["natig"]["tree"],
            "context embedded NATIG HEAD tree",
        )
        require(
            embedded_git(natig, "write-tree")
            == overlay["result_tree"],
            "context embedded NATIG index tree",
        )
        require(
            not embedded_git(
                natig,
                "ls-files",
                "--others",
            ),
            "context embedded NATIG has no untracked files",
        )
        require(
            not embedded_git(
                natig,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--name-only",
            ),
            "context embedded NATIG has no unstaged changes",
        )
        require(
            not verify_worktree(natig),
            "context tracked worktree raw bytes equal index",
        )
        require(
            all(
                line.startswith("H ")
                for line in embedded_git(
                    natig, "ls-files", "-v"
                ).splitlines()
            ),
            "context embedded NATIG index has no worktree-suppression flags",
        )
        require(
            not any(
                line.startswith(
                    ("core.worktree=", "extensions.worktreeconfig=")
                )
                for line in embedded_git(
                    natig, "config", "--local", "--list"
                ).lower().splitlines()
            ),
            "context embedded Git has no worktree redirection",
        )
        require(
            embedded_git(
                natig,
                "diff",
                "--cached",
                "--binary",
                "--no-ext-diff",
                "--no-textconv",
            )
            + "\n"
            == (context / "g4-overlay.patch").read_text(encoding="utf-8"),
            "context staged diff equals canonical G4 patch",
        )
        context_summary = {
            "path": str(context),
            "natig_file_count": len(source_lines),
            "bad_source": bad_source,
        }

    return {
        "schema_version": "1.0",
        "lock": str(lock_path.resolve()),
        "dockerfile": str(dockerfile_path.resolve()),
        "generator": str(generator_path.resolve()),
        "context": context_summary,
        "checks_passed": len(checks),
        "failures": failures,
        "valid": not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lock",
        type=Path,
        default=HERE.parent / "locked_dependencies.json",
    )
    parser.add_argument(
        "--dockerfile", type=Path, default=HERE / "Dockerfile"
    )
    parser.add_argument(
        "--generator", type=Path, default=HERE / "prepare_context.py"
    )
    parser.add_argument("--context", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(
        args.lock, args.dockerfile, args.generator, args.context
    )
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(
        f"valid={result['valid']} checks={result['checks_passed']} "
        f"failures={len(result['failures'])}"
    )
    for failure in result["failures"]:
        print(f"FAIL {failure}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

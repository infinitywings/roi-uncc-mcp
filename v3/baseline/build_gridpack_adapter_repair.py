#!/usr/bin/env python3
"""Build a v3-only GridPACK adapter with non-cumulative phase rotation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


SOURCE_FILES = (
    "CMakeLists.txt",
    "gpk-left-fed.cpp",
    "pf_app.cpp",
    "pf_app.hpp",
    "pf_factory.cpp",
    "pf_factory.hpp",
)
ANCHOR = """    // pass S's to GridPACK and get back V's
    app_A.execute(argc, argv, Va, Va_2, Sa, Sa_2);
    app_B.execute(argc, argv, Vb, Vb_2, Sb, Sb_2);
    app_C.execute(argc, argv, Vc, Vc_2, Sc, Sc_2);"""
REPAIR = """    // pass S's to GridPACK and get back V's
    // PFApp B/C do not reliably replace the prior phasor in this adapter.
    // Reset their positive-sequence seeds so the later +/-120 degree
    // rotations are applied once per solve rather than cumulatively.
    Vb = std::complex<double>(1.0,0.0);
    Vc = std::complex<double>(1.0,0.0);
    Vb_2 = std::complex<double>(1.0,0.0);
    Vc_2 = std::complex<double>(1.0,0.0);
    app_A.execute(argc, argv, Va, Va_2, Sa, Sa_2);
    app_B.execute(argc, argv, Vb, Vb_2, Sb, Sb_2);
    app_C.execute(argc, argv, Vc, Vc_2, Sc, Sc_2);"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/workspace"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    source_dir = output_dir / "source"
    build_dir = output_dir / "build"
    source_dir.mkdir()

    upstream = repo / "examples/2bus-13bus"
    for name in SOURCE_FILES:
        shutil.copy2(upstream / name, source_dir / name)
    adapter_path = source_dir / "gpk-left-fed.cpp"
    text = adapter_path.read_text(encoding="utf-8")
    if text.count(ANCHOR) != 1:
        raise RuntimeError("GridPACK adapter repair anchor is not unique")
    text = text.replace(ANCHOR, REPAIR)
    duration_anchor = "double total_interval = 7200.0;"
    if text.count(duration_anchor) != 1:
        raise RuntimeError("GridPACK duration anchor is not unique")
    text = text.replace(duration_anchor, "double total_interval = 240.0;")
    adapter_path.write_text(text, encoding="utf-8")

    configure = subprocess.run(
        ["cmake", "-S", str(source_dir), "-B", str(build_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    (output_dir / "configure.log").write_text(
        configure.stdout, encoding="utf-8"
    )
    if configure.returncode != 0:
        raise RuntimeError("CMake configure failed; see configure.log")
    build = subprocess.run(
        ["cmake", "--build", str(build_dir), "--parallel", "2"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    (output_dir / "build.log").write_text(build.stdout, encoding="utf-8")
    if build.returncode != 0:
        raise RuntimeError("GridPACK adapter build failed; see build.log")

    executable = build_dir / "gpk-left-fed.x"
    manifest = {
        "schema_version": "1.0",
        "repair": (
            "reset B/C positive-sequence seeds before one phase rotation; "
            "bound diagnostic duration to 240 seconds"
        ),
        "builder_sha256": sha256(Path(__file__).resolve()),
        "upstream_source_hashes": {
            name: sha256(upstream / name) for name in SOURCE_FILES
        },
        "patched_source_hashes": {
            name: sha256(source_dir / name) for name in SOURCE_FILES
        },
        "executable": str(executable),
        "executable_sha256": sha256(executable),
        "configure_returncode": configure.returncode,
        "build_returncode": build.returncode,
    }
    (output_dir / "build_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"built={executable} sha256={manifest['executable_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

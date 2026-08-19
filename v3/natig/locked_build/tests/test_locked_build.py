from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v3.natig.locked_build.validate_locked_build import validate
from v3.natig.locked_build.prepare_context import (
    SEMANTIC_ONLY_FILES as GENERATOR_SEMANTIC_ONLY_FILES,
)
from v3.natig.locked_build.validate_locked_build import (
    SEMANTIC_ONLY_FILES as VALIDATOR_SEMANTIC_ONLY_FILES,
)


ROOT = Path(__file__).resolve().parents[4]
LOCKED = ROOT / "v3" / "natig" / "locked_build"
LOCK = ROOT / "v3" / "natig" / "locked_dependencies.json"


def run_validation(dockerfile: Path):
    return validate(
        LOCK,
        dockerfile,
        LOCKED / "prepare_context.py",
    )


def test_current_locked_build_is_valid():
    result = run_validation(LOCKED / "Dockerfile")
    assert result["valid"], result["failures"]


def test_only_git_index_is_admitted_by_semantic_tree_identity():
    assert set(GENERATOR_SEMANTIC_ONLY_FILES) == {
        "natig/.git/index"
    }
    assert VALIDATOR_SEMANTIC_ONLY_FILES == {
        "natig/.git/index"
    }


def test_mutable_base_tag_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        text.replace(
            "python:3.6-slim@sha256:"
            "28028f6c3ce569a6405909ca76e85469"
            "fbb85c9ee93acd2fe5fe13f5e5e2c412",
            "python:3.6-slim",
            1,
        ),
        encoding="utf-8",
    )
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert "base image digest" in result["failures"]


def test_missing_direct_package_pin_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    shutil.copy2(LOCKED / "Dockerfile", dockerfile)
    text = dockerfile.read_text(encoding="utf-8")
    dockerfile.write_text(
        text.replace("autoconf=2.69-14", "autoconf", 1),
        encoding="utf-8",
    )
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert "apt pin autoconf" in result["failures"]


def test_unlocked_git_clone_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        text + "\nRUN git clone https://github.com/pnnl/NATIG.git\n",
        encoding="utf-8",
    )
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert "absent: mutable NATIG clone" in result["failures"]
    assert "absent: unlocked git clone" in result["failures"]


def test_missing_in_container_path_coverage_gate_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        text.replace(
            'assert actual == listed | semantic',
            'assert semantic',
            1,
        ),
        encoding="utf-8",
    )
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert (
        "Docker admission rejects unmanifested NATIG paths"
        in result["failures"]
    )


def test_missing_in_container_untracked_gate_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        text.replace(
            '    test -z "$(git --git-dir=natig/.git '
            '--work-tree=natig ls-files --others)"; \\\n',
            "",
            1,
        ),
        encoding="utf-8",
    )
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert (
        "Docker admission rejects untracked NATIG paths"
        in result["failures"]
    )


def test_self_authenticated_untracked_context_file_is_rejected(tmp_path):
    context = tmp_path / "context"
    subprocess.run(
        [
            sys.executable,
            str(LOCKED / "prepare_context.py"),
            "--source",
            str(ROOT / "v3" / "deps" / "natig-src"),
            "--lock",
            str(LOCK),
            "--applicator",
            str(ROOT / "v3" / "natig_adapter" / "apply_overlay.py"),
            "--overlay-patch",
            str(
                ROOT
                / "v3"
                / "natig_adapter"
                / "patches"
                / "0001-grideval-g4-gateway-overlay.patch"
            ),
            "--output-dir",
            str(context),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    injected = context / "natig" / "hostile-untracked.txt"
    injected.write_text("hostile\n", encoding="utf-8")
    digest = hashlib.sha256(injected.read_bytes()).hexdigest()
    byte_manifest = context / "natig.sha256"
    byte_manifest.write_text(
        byte_manifest.read_text(encoding="utf-8")
        + f"{digest}  natig/hostile-untracked.txt\n",
        encoding="utf-8",
    )
    manifest_path = context / "context_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["export"]["natig_file_count"] += 1
    manifest["export"]["natig_sha256_manifest_sha256"] = hashlib.sha256(
        byte_manifest.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = validate(
        LOCK,
        LOCKED / "Dockerfile",
        LOCKED / "prepare_context.py",
        context,
    )
    assert not result["valid"]
    assert (
        "context embedded NATIG has no untracked files"
        in result["failures"]
    )


def test_self_authenticated_ignored_context_file_is_rejected(tmp_path):
    context = tmp_path / "context"
    subprocess.run(
        [
            sys.executable,
            str(LOCKED / "prepare_context.py"),
            "--source",
            str(ROOT / "v3" / "deps" / "natig-src"),
            "--lock",
            str(LOCK),
            "--applicator",
            str(ROOT / "v3" / "natig_adapter" / "apply_overlay.py"),
            "--overlay-patch",
            str(
                ROOT
                / "v3"
                / "natig_adapter"
                / "patches"
                / "0001-grideval-g4-gateway-overlay.patch"
            ),
            "--output-dir",
            str(context),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    injected = context / "natig" / "hostile-ignored.txt"
    injected.write_text("hostile\n", encoding="utf-8")
    exclude = context / "natig" / ".git" / "info" / "exclude"
    exclude.write_text(
        exclude.read_text(encoding="utf-8") + "hostile-ignored.txt\n",
        encoding="utf-8",
    )
    injected_digest = hashlib.sha256(injected.read_bytes()).hexdigest()
    exclude_digest = hashlib.sha256(exclude.read_bytes()).hexdigest()
    byte_manifest = context / "natig.sha256"
    lines = byte_manifest.read_text(encoding="utf-8").splitlines()
    lines = [
        (
            f"{exclude_digest}  natig/.git/info/exclude"
            if line.endswith("  natig/.git/info/exclude")
            else line
        )
        for line in lines
    ]
    lines.append(f"{injected_digest}  natig/hostile-ignored.txt")
    byte_manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_path = context / "context_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["export"]["natig_file_count"] += 1
    manifest["export"]["natig_sha256_manifest_sha256"] = hashlib.sha256(
        byte_manifest.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = validate(
        LOCK,
        LOCKED / "Dockerfile",
        LOCKED / "prepare_context.py",
        context,
    )
    assert not result["valid"]
    assert (
        "context embedded NATIG has no untracked files"
        in result["failures"]
    )


def test_self_authenticated_tracked_context_mutation_is_rejected(tmp_path):
    context = tmp_path / "context"
    subprocess.run(
        [
            sys.executable,
            str(LOCKED / "prepare_context.py"),
            "--source",
            str(ROOT / "v3" / "deps" / "natig-src"),
            "--lock",
            str(LOCK),
            "--applicator",
            str(ROOT / "v3" / "natig_adapter" / "apply_overlay.py"),
            "--overlay-patch",
            str(
                ROOT
                / "v3"
                / "natig_adapter"
                / "patches"
                / "0001-grideval-g4-gateway-overlay.patch"
            ),
            "--output-dir",
            str(context),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    mutated = context / "natig" / "README.md"
    mutated.write_text(
        mutated.read_text(encoding="utf-8") + "hostile tracked mutation\n",
        encoding="utf-8",
    )
    attributes = context / "natig" / ".git" / "info" / "attributes"
    attributes.write_text(
        "README.md filter=attack\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(context / "natig"),
            "config",
            "filter.attack.clean",
            "sed '/hostile tracked mutation/d'",
        ],
        check=True,
    )
    assert (
        subprocess.run(
            [
                "git",
                f"--git-dir={context / 'natig' / '.git'}",
                f"--work-tree={context / 'natig'}",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.filemode=true",
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--name-only",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        == ""
    )
    mutated_digest = hashlib.sha256(mutated.read_bytes()).hexdigest()
    config = context / "natig" / ".git" / "config"
    config_digest = hashlib.sha256(config.read_bytes()).hexdigest()
    attributes_digest = hashlib.sha256(attributes.read_bytes()).hexdigest()
    byte_manifest = context / "natig.sha256"
    lines = byte_manifest.read_text(encoding="utf-8").splitlines()
    lines = [
        (
            f"{mutated_digest}  natig/README.md"
            if line.endswith("  natig/README.md")
            else f"{config_digest}  natig/.git/config"
            if line.endswith("  natig/.git/config")
            else line
        )
        for line in lines
    ]
    lines.append(
        f"{attributes_digest}  natig/.git/info/attributes"
    )
    byte_manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_path = context / "context_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["export"]["natig_file_count"] += 1
    manifest["export"]["natig_sha256_manifest_sha256"] = hashlib.sha256(
        byte_manifest.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = validate(
        LOCK,
        LOCKED / "Dockerfile",
        LOCKED / "prepare_context.py",
        context,
    )
    assert not result["valid"]
    assert (
        "context tracked worktree raw bytes equal index"
        in result["failures"]
    )


def test_pip_receives_the_canonical_helics_apps_wheel_filename():
    dockerfile = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    wheel = (
        "helics_apps-2.7.1-py2.py3-none-manylinux_2_12_x86_64"
        ".manylinux2010_x86_64.whl"
    )
    assert f"python -m pip install --no-deps /tmp/{wheel}" in dockerfile
    assert "--output /tmp/helics_apps.whl" not in dockerfile


def test_live_g4_executable_is_compiled_and_installed():
    dockerfile = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    assert (
        "ns-3-dev/scratch/grideval-natig-g4.cc" in dockerfile
    )
    assert (
        "install -m 0755 build/scratch/grideval-natig-g4 "
        "\\\n      /usr/local/bin/grideval-natig-g4"
    ) in dockerfile
    assert "test -x /usr/local/bin/grideval-natig-g4" in dockerfile
    assert "cd ns-3-dev; \\\n    ./waf configure" in dockerfile
    assert "LDFLAGS='-L/rd2c/lib -ljsoncpp'" not in dockerfile
    helics_wscript = (
        ROOT / "v3" / "deps" / "natig-src"
        / "RC" / "code" / "helics" / "wscript"
    ).read_text(encoding="utf-8")
    assert "conf.env.append_value('LDFLAGS', '-ljsoncpp')" not in helics_wscript
    assert (
        "conf.env.append_value('LDFLAGS', '-ljsoncpp')"
        in (
            ROOT / "v3" / "natig_adapter" / "patches"
            / "0001-grideval-g4-gateway-overlay.patch"
        ).read_text(encoding="utf-8")
    )
    assert (
        "RC/code/internet/ipv4-l3-protocol* \\\n"
        "      ns-3-dev/src/internet/model/"
    ) in dockerfile
    assert (
        "RC/code/internet/internet-stack-helper-MIM.* \\\n"
        "      ns-3-dev/src/internet/helper/"
    ) in dockerfile
    assert "RC/code/internet/. ns-3-dev/src/internet/" not in dockerfile


def test_jsoncpp_uses_pinned_helics_static_archive_and_matching_headers():
    dockerfile = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    lock = (ROOT / "v3" / "natig" / "locked_dependencies.json").read_text(
        encoding="utf-8"
    )
    assert "libjsoncpp-dev" not in lock
    assert "libjsoncpp-dev=" not in dockerfile
    assert "CXXFLAGS=-I/rd2c/include" in dockerfile
    assert (
        "HELICS/build/lib/libjsoncpp.a /rd2c/lib/libjsoncpp.a"
        in dockerfile
    )
    assert "HELICS/ThirdParty/jsoncpp/include/json" in dockerfile
    assert 'JSONCPP_VERSION_STRING \\"1.9.2\\"' in dockerfile
    assert "g++ -I/rd2c/include /tmp/jsoncpp-smoke.cc" in dockerfile
    assert (
        "! readelf -d /tmp/jsoncpp-smoke | grep -q 'libjsoncpp'"
        in dockerfile
    )


def test_missing_pinned_jsoncpp_export_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        text.replace(
            "install -m 0644 HELICS/build/lib/libjsoncpp.a "
            "/rd2c/lib/libjsoncpp.a; \\\n",
            "",
            1,
        ),
        encoding="utf-8",
    )
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert (
        "active pinned HELICS JsonCpp archive and header export block"
        in result["failures"]
    )


def test_token_only_jsoncpp_export_decoy_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    active = (
        "    install -m 0644 HELICS/build/lib/libjsoncpp.a "
        "/rd2c/lib/libjsoncpp.a; \\\n"
    )
    decoy = (
        "    printf '%s\\n' 'install -m 0644 "
        "HELICS/build/lib/libjsoncpp.a /rd2c/lib/libjsoncpp.a'; \\\n"
    )
    dockerfile.write_text(text.replace(active, decoy, 1), encoding="utf-8")
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert (
        "active pinned HELICS JsonCpp archive and header export block"
        in result["failures"]
    )


def test_token_only_jsoncpp_smoke_decoy_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    active = (
        "    ! readelf -d /tmp/jsoncpp-smoke | "
        "grep -q 'libjsoncpp'; \\\n"
    )
    decoy = (
        "    printf '%s\\n' \"! readelf -d /tmp/jsoncpp-smoke | "
        "grep -q 'libjsoncpp'\"; \\\n"
    )
    dockerfile.write_text(text.replace(active, decoy, 1), encoding="utf-8")
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert (
        "active JsonCpp GCC 8 static-link smoke block"
        in result["failures"]
    )


def test_missing_live_executable_wiring_is_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    text = (LOCKED / "Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        text.replace(
            "install -m 0755 build/scratch/grideval-natig-g4 "
            "\\\n      /usr/local/bin/grideval-natig-g4; \\\n",
            "",
            1,
        ),
        encoding="utf-8",
    )
    result = run_validation(dockerfile)
    assert not result["valid"]
    assert (
        "live G4 executable is copied before configure, built, and installed"
        in result["failures"]
    )

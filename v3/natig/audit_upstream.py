#!/usr/bin/env python3
"""Create a deterministic provenance and reproducibility audit for NATIG."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


FILES = (
    "Dockerfile",
    "build_ns3.sh",
    "build_helics.sh",
    "RC/code/run.sh",
    "integration/control/run.sh",
    "integration/control/killall.sh",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(source: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=source,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def finding(
    finding_id: str,
    severity: str,
    path: str,
    pattern: str,
    text: str,
    consequence: str,
) -> dict[str, Any]:
    matches = [
        {"line": index, "text": line.strip()}
        for index, line in enumerate(text.splitlines(), start=1)
        if re.search(pattern, line)
    ]
    return {
        "id": finding_id,
        "severity": severity,
        "path": path,
        "pattern": pattern,
        "matches": matches,
        "present": bool(matches),
        "consequence": consequence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()

    texts = {
        relative: (source / relative).read_text(encoding="utf-8")
        for relative in FILES
    }
    dockerfile = texts["Dockerfile"]
    build_ns3 = texts["build_ns3.sh"]
    build_helics = texts["build_helics.sh"]
    effective_run_script = texts["RC/code/run.sh"]

    findings = [
        finding(
            "U01",
            "critical",
            "Dockerfile",
            r"git clone https://github\.com/pnnl/NATIG\.git\s*$",
            dockerfile,
            "The image does not consume the audited checkout; it clones moving NATIG HEAD.",
        ),
        finding(
            "U02",
            "high",
            "Dockerfile",
            r"^FROM python:3\.6-slim",
            dockerfile,
            "The historical base tag is mutable and Python 3.6 is end-of-life.",
        ),
        finding(
            "U03",
            "high",
            "Dockerfile",
            r"--allow-unauthenticated|--no-check-certificate|http://",
            dockerfile,
            "Dependency transport or package authentication is disabled.",
        ),
        finding(
            "U04",
            "high",
            "Dockerfile",
            r"git clone https://github\.com/nsnam/ns-3-dev-git\.git",
            dockerfile,
            "The Dockerfile initially clones an unpinned ns-3 repository.",
        ),
        finding(
            "U05",
            "high",
            "build_ns3.sh",
            r"git clone https://github\.com/nsnam/ns-3-dev-git\.git",
            build_ns3,
            "The build script reclones ns-3 before checking out a tag.",
        ),
        finding(
            "U06",
            "medium",
            "build_helics.sh",
            r"git clone .*HELICS-v2\.x-waf",
            build_helics,
            "The ns-3 HELICS tag is cloned without asserting commit 11e91ab.",
        ),
        finding(
            "U07",
            "medium",
            "Dockerfile",
            r"openjdk-11-jdk|JAVA_HOME /usr/lib/jvm/java-8",
            dockerfile,
            "The installed Java major version and JAVA_HOME disagree.",
        ),
        finding(
            "U08",
            "medium",
            "Dockerfile",
            r"cp -r RC/code/run\.sh .*integration/control",
            dockerfile,
            "The image overwrites integration/control/run.sh with RC/code/run.sh.",
        ),
        finding(
            "U09",
            "high",
            "RC/code/run.sh",
            r'^if \[\[ "\$3" == "RC" \]\]',
            effective_run_script,
            "The effective launcher waits only when its third argument is RC.",
        ),
        finding(
            "U10",
            "high",
            "RC/code/run.sh",
            r"^exit 0",
            effective_run_script,
            "The effective launcher returns success independently of child outcomes.",
        ),
    ]

    result = {
        "schema_version": "1.0",
        "source": {
            "path": str(source),
            "commit": git(source, "rev-parse", "HEAD"),
            "tree": git(source, "rev-parse", "HEAD^{tree}"),
            "dirty": bool(git(source, "status", "--short")),
        },
        "files": {
            relative: {"sha256": sha256(source / relative)}
            for relative in FILES
        },
        "findings": findings,
        "summary": {
            "finding_count": len(findings),
            "present_count": sum(item["present"] for item in findings),
            "critical_count": sum(
                item["present"] and item["severity"] == "critical"
                for item in findings
            ),
            "high_count": sum(
                item["present"] and item["severity"] == "high"
                for item in findings
            ),
            "upstream_build_can_prove_pinned_reproducibility": False,
            "launcher_exit_can_prove_simulation_success": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"present={result['summary']['present_count']}/{len(findings)} "
        f"critical={result['summary']['critical_count']} "
        f"high={result['summary']['high_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

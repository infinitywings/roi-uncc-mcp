from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from v3.natig_adapter.apply_overlay import (
    PATCH,
    PINNED_COMMIT,
    PINNED_TREE,
    SOURCE_DIGESTS,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
PINNED_SOURCE = REPO_ROOT / "v3" / "deps" / "natig-src"
APPLICATOR = REPO_ROOT / "v3" / "natig_adapter" / "apply_overlay.py"


def _run(*args: str | Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(arg) for arg in args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode:
        raise AssertionError(
            f"command failed ({completed.returncode}):\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return completed


@pytest.fixture()
def fresh_source(tmp_path: Path) -> Path:
    destination = tmp_path / "natig-src"
    _run(
        "git",
        "clone",
        "--quiet",
        "--no-hardlinks",
        PINNED_SOURCE,
        destination,
    )
    return destination


def test_manifest_is_exactly_the_pinned_clean_source():
    assert _run("git", "-C", PINNED_SOURCE, "rev-parse", "HEAD").stdout.strip() == (
        PINNED_COMMIT
    )
    assert _run(
        "git", "-C", PINNED_SOURCE, "rev-parse", "HEAD^{tree}"
    ).stdout.strip() == PINNED_TREE
    assert _run(
        "git", "-C", PINNED_SOURCE, "status", "--porcelain"
    ).stdout == ""
    for relative, expected in SOURCE_DIGESTS.items():
        assert hashlib.sha256((PINNED_SOURCE / relative).read_bytes()).hexdigest() == (
            expected
        )


def test_applicator_checks_then_applies_to_fresh_pinned_clone(fresh_source: Path):
    checked = _run(sys.executable, APPLICATOR, "--source", fresh_source)
    assert "verified (check only)" in checked.stdout
    assert _run(
        "git", "-C", fresh_source, "status", "--porcelain"
    ).stdout == ""

    applied = _run(
        sys.executable,
        APPLICATOR,
        "--source",
        fresh_source,
        "--apply",
    )
    assert "overlay applied" in applied.stdout
    changed = set(
        _run(
            "git", "-C", fresh_source, "diff", "--cached", "--name-only"
        ).stdout.splitlines()
    )
    assert changed == set(SOURCE_DIGESTS)
    _run("git", "-C", fresh_source, "diff", "--cached", "--check")

    outstation = (
        fresh_source / "RC/code/dnp3/dnplib/outstation.cpp"
    ).read_text(errors="strict")
    outstation_header = (
        fresh_source / "RC/code/dnp3/dnplib/outstation.hpp"
    ).read_text(errors="strict")
    transport = (
        fresh_source / "RC/code/dnp3/dnplib/transport.cpp"
    ).read_text(errors="strict")
    transport_header = (
        fresh_source / "RC/code/dnp3/dnplib/transport.hpp"
    ).read_text(errors="strict")
    event_interface = (
        fresh_source / "RC/code/dnp3/dnplib/event_interface.hpp"
    ).read_text(errors="strict")
    factory = (
        fresh_source / "RC/code/dnp3/dnplib/factory.cpp"
    ).read_text(errors="strict")
    application = (
        fresh_source / "RC/code/helics/dnp3-application-new-Docker.cc"
    ).read_text(errors="strict")
    helper = (
        fresh_source / "RC/code/helics/helics-helper.cc"
    ).read_text(errors="strict")
    simulator = (
        fresh_source / "RC/code/helics/helics-simulator-impl.cc"
    ).read_text(errors="strict")
    main = (
        fresh_source / "RC/code/ns3-helics-grid-dnp3-Docker.cc"
    ).read_text(errors="strict")
    common = (
        fresh_source / "RC/code/dnp3/dnplib/common.cpp"
    ).read_text(errors="strict")
    objects = (
        fresh_source / "RC/code/dnp3/dnplib/object.cpp"
    ).read_text(errors="strict")
    assert "#include <cstring>" in common
    assert common.count("std::memcpy") == 2
    for function, width, initialized in (
        ("removeUINT8", 1, "uint8_t val = data[0];"),
        ("removeUINT16", 2, "uint16_t val = 0;"),
        ("removeUINT24", 3, "uint32_t val = 0;"),
        ("removeUINT32", 4, "uint32_t val = 0;"),
        ("removeUINT48", 6, "uint64_t val = 0;"),
    ):
        body = common.split(
            f"{function}(Bytes& data) noexcept(true)", 1
        )[1].split("\n}", 1)[0]
        assert f"if(data.size() < {width}) {{" in body
        assert "return 0;" in body
        assert initialized in body
        assert "//throw" not in body
    assert common.count("static_cast<uint16_t>(data[") == 2
    assert common.count("static_cast<uint32_t>(data[") == 7
    assert common.count("static_cast<uint64_t>(data[") == 6
    assert "flag = removeUINT8(data);" in objects
    assert "value = removeFloat(data);" in objects
    assert "request = static_cast<float>(removeINT32(data));" in objects
    assert 'publishCallback("gateway/der_ev4"' in outstation
    assert "command->index > 1" in outstation
    assert "g4AoSelectCount != rawCount" in outstation
    assert "responseObject.encode(txFragment);" in outstation
    assert "command->encode(txFragment);" in outstation
    assert "g4OutstationAddr(outstationConfig.addr)" in outstation
    assert (
        '<< "\\"outstation_address\\":" << g4OutstationAddr'
        in outstation
    )
    assert "DnpAddr_t               g4OutstationAddr;" in outstation_header
    assert '#if 0\nvoid Outstation::controlLegacyGldMapper' in outstation
    assert "virtual void changeFloatPoint" in event_interface
    assert "db_p->changeFloatPoint" in factory
    assert 'msg->dest = "gateway/der_ev4"' in application
    assert "Rejected non-GridEval or malformed DER_EV4 telemetry" in application
    assert "payload.size() != 4" in application
    assert "DispatchG4Control" in application
    assert "DispatchEndpoint" in application
    assert "delivery + 1e-9 < now" in application
    assert "EmitG4TelemetryIfComplete" in application
    assert "#include <iomanip>" in application
    assert "#include <limits>" in application
    assert (
        "std::setprecision(std::numeric_limits<double>::max_digits10)"
        in application
    )
    assert (
        'std::to_string(root["analog"][i].asDouble())'
        not in application
    )
    assert (
        "static const DnpAddr_t USE_LOCAL_DATALINK_ADDRESS = 0xffff;"
        in transport_header
    )
    assert (
        "DnpAddr_t srcAddr=USE_LOCAL_DATALINK_ADDRESS"
        in transport_header
    )
    assert transport.count(
        "if(srcAddr == USE_LOCAL_DATALINK_ADDRESS)"
    ) == 2
    assert "if(srcAddr == -1)" not in transport
    assert 'name("g4_natig_der_ev4")' in helper
    assert 'registerEndpoint ("fout")' not in helper
    assert "helics_federate->getMessage()" not in simulator
    assert "for (int pollTime = pollPeriod;" in main
    assert "Seconds(pollTime) + MilliSeconds(1)" in main
    assert "StationDeviceAddress\", UintegerValue(4)" in main
    assert "MilliSeconds(3005)" not in main
    assert "#if 0\nvoid\nDnp3ApplicationNew::DoMessageLegacyGld" in application


def test_applicator_fails_closed_on_one_byte_source_drift(fresh_source: Path):
    target = fresh_source / "RC/code/dnp3/dnplib/common.cpp"
    target.write_bytes(target.read_bytes() + b"\n")
    rejected = _run(
        sys.executable,
        APPLICATOR,
        "--source",
        fresh_source,
        check=False,
    )
    assert rejected.returncode != 0
    assert (
        "tracked worktree is not clean" in rejected.stderr
        or "source-byte drift" in rejected.stderr
    )


def test_patch_is_v3_owned_and_does_not_touch_build_recipe():
    text = PATCH.read_text()
    assert "Dockerfile" not in {
        line.removeprefix("+++ b/").removeprefix("--- a/")
        for line in text.splitlines()
        if line.startswith(("+++ ", "--- "))
    }
    assert "g4AoSelectValid" in text
    assert "+#include <cstring>" in text
    assert text.count("+    std::memcpy") == 2
    assert text.count("+        return 0;") == 5
    assert "+    uint8_t val = data[0];" in text
    assert text.count("+    uint32_t val = 0;") == 2
    assert "+    uint16_t val = 0;" in text
    assert "+    uint64_t val = 0;" in text
    added_lines = "\n".join(
        line[1:] for line in text.splitlines() if line.startswith("+")
    )
    compiled_control = added_lines.split(
        "#if 0\nvoid Outstation::controlLegacyGldMapper", 1
    )[0]
    assert "status == 95" not in compiled_control
    assert "command->status != Bit32AnalogOutput::ACCEPTED" in compiled_control
    assert 'msg->dest = "gateway/der_ev4"' in text
    assert (
        "+                  << std::setprecision("
        "std::numeric_limits<double>::max_digits10)"
        in text
    )

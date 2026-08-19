from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

sys.modules.setdefault("helics", SimpleNamespace())

from v3.natig_adapter.live_benign.live_gateway_federate import (
    NOMINAL_VOLTAGE_V,
    normalize_helics_complex,
    telemetry_wire,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ((3.0, 4.0), complex(3.0, 4.0)),
        ([3, -4], complex(3.0, -4.0)),
        (complex(-1.0, 2.5), complex(-1.0, 2.5)),
    ],
)
def test_helics_complex_normalizes_pinned_tuple_api(raw, expected):
    assert normalize_helics_complex(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        3.0,
        (1.0,),
        (1.0, 2.0, 3.0),
        (True, 0.0),
        ("1.0", 0.0),
        (float("nan"), 0.0),
        (0.0, float("inf")),
    ],
)
def test_helics_complex_rejects_malformed_or_nonfinite_values(raw):
    with pytest.raises((TypeError, ValueError)):
        normalize_helics_complex(raw)


def test_live_telemetry_uses_observed_terminal_voltage():
    output = SimpleNamespace(
        p_out_kw=10.0,
        q_out_kvar=-2.0,
        soc=0.61,
        status="Continuous Operation",
    )
    frame = telemetry_wire(
        output,
        command_accepted=True,
        terminal_voltage_v=NOMINAL_VOLTAGE_V * 1.0125,
    )
    assert frame == {
        "schema_version": "grideval-g4-telemetry-0.1",
        "target": "DER_EV4_BESS",
        "analog": [10.0, -2.0, pytest.approx(1.0125), 0.61],
        "binary": [True, True],
    }

"""Physical operating-point actuation for the IEEE-123 feeder runtime."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class OperatingPoint:
    id: str
    condition_class: str
    start_time: str
    rationale: str

    def stop_time(self, duration_s: int) -> str:
        start = datetime.strptime(self.start_time, TIMESTAMP_FORMAT)
        return (start + timedelta(seconds=int(duration_s))).strftime(TIMESTAMP_FORMAT)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# These clock positions preserve the prior RKA guidance (Hour 4 low, Hour 7
# medium, Hour 14 ceiling) and add two responsive high-load shoulders.  All are
# evaluated against the same one-minute feeder load-shape player.
OPERATING_POINTS: dict[str, OperatingPoint] = {
    "responsive_night": OperatingPoint(
        "responsive_night", "responsive", "2013-08-28 04:00:00",
        "low-load pre-dawn point",
    ),
    "responsive_morning": OperatingPoint(
        "responsive_morning", "responsive", "2013-08-28 07:00:00",
        "medium-load morning ramp point",
    ),
    "responsive_midday": OperatingPoint(
        "responsive_midday", "responsive", "2013-08-28 12:00:00",
        "high-load rising shoulder",
    ),
    "responsive_evening": OperatingPoint(
        "responsive_evening", "responsive", "2013-08-28 18:00:00",
        "high-load falling shoulder",
    ),
    "voltage_ceiling": OperatingPoint(
        "voltage_ceiling", "falsification", "2013-08-28 14:00:00",
        "near-peak feeder-load ceiling/negative-control point",
    ),
}


def get_operating_point(point_id: str) -> OperatingPoint:
    try:
        return OPERATING_POINTS[point_id]
    except KeyError as exc:
        raise ValueError(f"unknown operating point: {point_id!r}") from exc


def load_shape_value_at(player_path: Path, start_time: str) -> float:
    """Return the one-minute player value at an exact clock position."""
    start = datetime.strptime(start_time, TIMESTAMP_FORMAT)
    if start.date().isoformat() != "2013-08-28":
        raise ValueError("operating point falls outside the frozen player date")
    minute = start.hour * 60 + start.minute
    lines = player_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1440:
        raise ValueError(f"expected 1440 one-minute load-shape rows, found {len(lines)}")
    try:
        return float(lines[minute].split(",", 1)[1].strip())
    except (IndexError, ValueError) as exc:
        raise ValueError(f"invalid load-shape row at minute {minute}") from exc


def actuate_glm_clock(glm_text: str, *, point_id: str, duration_s: int,
                      player_path: Path) -> tuple[str, dict[str, Any]]:
    """Replace the generated GLM clock exactly once and return provenance."""
    if int(duration_s) <= 0:
        raise ValueError("duration_s must be positive")
    point = get_operating_point(point_id)
    start = point.start_time
    stop = point.stop_time(int(duration_s))
    text, start_count = re.subn(
        r"starttime\s+'[^']+';[^\n]*",
        f"starttime '{start}';  // G7 operating_point={point.id}",
        glm_text,
        count=1,
    )
    text, stop_count = re.subn(
        r"stoptime\s+'[^']+';[^\n]*",
        f"stoptime '{stop}';  // G7 duration_s={int(duration_s)}",
        text,
        count=1,
    )
    if start_count != 1 or stop_count != 1:
        raise RuntimeError(
            f"GLM clock actuation was not unique (start={start_count}, stop={stop_count})"
        )
    player_bytes = player_path.read_bytes()
    metadata = {
        "schema_version": "grideval-g7-operating-point/v1",
        **point.to_dict(),
        "stop_time": stop,
        "duration_s": int(duration_s),
        "load_shape_value": load_shape_value_at(player_path, start),
        "load_shape_player": str(player_path),
        "load_shape_player_sha256": hashlib.sha256(player_bytes).hexdigest(),
        "actuated_glm_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    return text, metadata

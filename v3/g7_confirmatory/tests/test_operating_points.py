from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from g7confirm.operating_points import (
    OPERATING_POINTS,
    actuate_glm_clock,
    load_shape_value_at,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE_GLM = ROOT / "examples" / "2bus-13bus" / "1c_IEEE_123_feeder.glm"
LOAD_PLAYER = ROOT / "examples" / "2bus-13bus" / "include" / "players" / "load_shape_player.player"


class OperatingPointTests(unittest.TestCase):
    def test_all_points_actuate_distinct_glm_bytes(self):
        source = SOURCE_GLM.read_text(encoding="utf-8")
        results = {
            point_id: actuate_glm_clock(
                source, point_id=point_id, duration_s=10, player_path=LOAD_PLAYER
            )
            for point_id in OPERATING_POINTS
        }
        hashes = {metadata["actuated_glm_sha256"] for _, metadata in results.values()}
        self.assertEqual(len(hashes), len(OPERATING_POINTS))
        for point_id, (glm, metadata) in results.items():
            self.assertIn(f"operating_point={point_id}", glm)
            self.assertEqual(metadata["duration_s"], 10)

    def test_declared_points_reach_materially_different_feeder_loads(self):
        values = {
            point_id: load_shape_value_at(LOAD_PLAYER, point.start_time)
            for point_id, point in OPERATING_POINTS.items()
        }
        self.assertLess(values["responsive_night"], 0.25)
        self.assertGreater(values["voltage_ceiling"], 0.9)
        self.assertGreater(max(values.values()) - min(values.values()), 0.7)

    def test_invalid_player_length_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short.player"
            path.write_text("2013-08-28 00:00:00, 1.0\n")
            with self.assertRaisesRegex(ValueError, "1440"):
                load_shape_value_at(path, "2013-08-28 04:00:00")


if __name__ == "__main__":
    unittest.main()

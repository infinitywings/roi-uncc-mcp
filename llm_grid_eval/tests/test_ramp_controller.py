"""Unit tests for RampController.

These tests can run without the helics dependency by loading the module directly.
Run with: python -m pytest llm_grid_eval/tests/test_ramp_controller.py -v
Or standalone: python llm_grid_eval/tests/test_ramp_controller.py
"""

import sys
from pathlib import Path
import types

# Create mock modules to avoid helics dependency in services/__init__.py
class _MockModule:
    pass

# Ensure mock modules exist before importing the actual module
_mock_modules = [
    'llm_grid_eval',
    'llm_grid_eval.services',
    'llm_grid_eval.services.ramp_controller',
    'llm_grid_eval.helics_interface',
    'llm_grid_eval.helics_interface.federate',
]
for _name in _mock_modules:
    if _name not in sys.modules:
        sys.modules[_name] = _MockModule()

# Load ramp_controller.py directly with proper module registration
_module_path = Path(__file__).parent.parent / "src" / "llm_grid_eval" / "services" / "ramp_controller.py"
_ramp_module = types.ModuleType('llm_grid_eval.services.ramp_controller')
_ramp_module.__file__ = str(_module_path)
sys.modules['llm_grid_eval.services.ramp_controller'] = _ramp_module
exec(compile(_module_path.read_text(), str(_module_path), 'exec'), _ramp_module.__dict__)

RampController = _ramp_module.RampController
EVRampState = _ramp_module.EVRampState

# pytest import
try:
    import pytest
except ImportError:
    pytest = None


class TestEVRampState:
    """Tests for EVRampState dataclass."""

    def test_needs_update_true(self):
        state = EVRampState(current_kw=100.0, target_kw=200.0)
        assert state.needs_update() is True

    def test_needs_update_false_exact(self):
        state = EVRampState(current_kw=100.0, target_kw=100.0)
        assert state.needs_update() is False

    def test_needs_update_false_within_tolerance(self):
        state = EVRampState(current_kw=100.0, target_kw=100.05)
        assert state.needs_update() is False


class TestRampController:
    """Tests for RampController."""

    def test_init_default_powers(self):
        """Default initial powers should match DEFAULT_INITIAL_POWERS."""
        rc = RampController()
        assert rc.get_current("EV1") == 220.0
        assert rc.get_current("EV2") == 200.0
        assert rc.get_current("EV3") == 200.0
        assert rc.get_current("EV4") == 220.0
        assert rc.get_current("EV5") == 200.0
        assert rc.get_current("EV6") == 200.0

    def test_init_custom_powers(self):
        """Custom initial powers should be used."""
        rc = RampController(initial_powers={"EV1": 500.0, "EV2": 300.0})
        assert rc.get_current("EV1") == 500.0
        assert rc.get_current("EV2") == 300.0
        assert rc.get_current("EV3") == 0.0  # Not in custom dict

    def test_set_target(self):
        """set_target should update target but not current."""
        rc = RampController()
        rc.set_target("EV3", 1000.0)
        assert rc.get_target("EV3") == 1000.0
        assert rc.get_current("EV3") == 200.0  # Not changed yet

    def test_set_target_new_ev(self):
        """Setting target for unknown EV should create new state."""
        rc = RampController(initial_powers={})
        rc.set_target("EV_NEW", 500.0)
        assert rc.get_target("EV_NEW") == 500.0
        assert rc.get_current("EV_NEW") == 0.0

    def test_get_current_unknown_ev(self):
        """Getting current for unknown EV should return 0."""
        rc = RampController()
        assert rc.get_current("UNKNOWN") == 0.0

    def test_get_target_unknown_ev(self):
        """Getting target for unknown EV should return 0."""
        rc = RampController()
        assert rc.get_target("UNKNOWN") == 0.0

    def test_ramp_single_step_reaches_target(self):
        """Small power change should reach target in one step."""
        rc = RampController(ramp_rate_kw_per_sec=100.0)
        rc.set_target("EV3", 700.0)  # 500 kW increase from default 200

        updates = rc.update(dt_sec=5.0)  # Max 500 kW change

        assert "EV3" in updates
        assert rc.get_current("EV3") == 700.0  # Reached target

    def test_ramp_single_step_partial(self):
        """Large power change should be capped at max rate."""
        rc = RampController(ramp_rate_kw_per_sec=100.0)
        rc.set_target("EV3", 1200.0)  # 1000 kW increase from default 200

        updates = rc.update(dt_sec=5.0)  # Max 500 kW change

        assert "EV3" in updates
        assert rc.get_current("EV3") == 700.0  # Only moved 500 kW

    def test_ramp_multiple_steps(self):
        """Large power change requires multiple steps."""
        rc = RampController(ramp_rate_kw_per_sec=100.0)
        rc.set_target("EV3", 2200.0)  # 2000 kW increase = 4 steps

        for i in range(4):
            rc.update(dt_sec=5.0)
            expected = 200.0 + (i + 1) * 500.0
            assert abs(rc.get_current("EV3") - expected) < 1.0

        assert abs(rc.get_current("EV3") - 2200.0) < 1.0

    def test_ramp_down(self):
        """Power should ramp down toward target."""
        rc = RampController(ramp_rate_kw_per_sec=100.0)
        # Set high starting power
        rc._ev_states["EV3"].current_kw = 1000.0
        rc._ev_states["EV3"].target_kw = 1000.0

        rc.set_target("EV3", 0.0)
        rc.update(dt_sec=5.0)
        assert rc.get_current("EV3") == 500.0

        rc.update(dt_sec=5.0)
        assert rc.get_current("EV3") == 0.0

    def test_no_update_at_target(self):
        """No updates returned when all EVs are at target."""
        rc = RampController()
        updates = rc.update()
        assert len(updates) == 0

    def test_ramp_status(self):
        """get_ramp_status should return correct info."""
        rc = RampController()
        rc.set_target("EV3", 1000.0)

        status = rc.get_ramp_status()
        assert status["EV3"]["ramping"] is True
        assert status["EV3"]["remaining_kw"] == 800.0
        assert status["EV3"]["current_kw"] == 200.0
        assert status["EV3"]["target_kw"] == 1000.0
        assert status["EV3"]["estimated_time_sec"] == 8.0  # 800 kW / 100 kW/s

    def test_is_any_ramping(self):
        """is_any_ramping should detect ramping state."""
        rc = RampController()
        assert rc.is_any_ramping() is False

        rc.set_target("EV3", 1000.0)
        assert rc.is_any_ramping() is True

        # Ramp to target
        for _ in range(10):
            rc.update(dt_sec=5.0)
        assert rc.is_any_ramping() is False

    def test_get_all_current_powers(self):
        """get_all_current_powers should return all current values."""
        rc = RampController()
        powers = rc.get_all_current_powers()
        assert len(powers) == 6
        assert powers["EV1"] == 220.0
        assert powers["EV3"] == 200.0

    def test_reset(self):
        """reset should restore initial state."""
        rc = RampController()
        rc.set_target("EV3", 2000.0)
        rc.update(dt_sec=5.0)

        rc.reset()

        assert rc.get_current("EV3") == 200.0
        assert rc.get_target("EV3") == 200.0

    def test_reset_custom_powers(self):
        """reset with custom powers should use those values."""
        rc = RampController()
        rc.reset(initial_powers={"EV1": 100.0})

        assert rc.get_current("EV1") == 100.0
        assert rc.get_current("EV2") == 0.0  # Not in custom dict

    def test_update_default_interval(self):
        """update() without dt_sec should use default interval."""
        rc = RampController(ramp_rate_kw_per_sec=100.0, update_interval_sec=5.0)
        rc.set_target("EV3", 700.0)

        updates = rc.update()  # Uses default 5.0s

        assert rc.get_current("EV3") == 700.0

    def test_multiple_evs_ramping(self):
        """Multiple EVs can ramp simultaneously."""
        rc = RampController(ramp_rate_kw_per_sec=100.0)
        rc.set_target("EV1", 720.0)
        rc.set_target("EV3", 700.0)

        updates = rc.update(dt_sec=5.0)

        assert "EV1" in updates
        assert "EV3" in updates
        assert rc.get_current("EV1") == 720.0  # Reached target
        assert rc.get_current("EV3") == 700.0  # Reached target

    def test_infinite_ramp_rate(self):
        """Infinite ramp rate should change immediately."""
        rc = RampController(ramp_rate_kw_per_sec=float("inf"))
        rc.set_target("EV3", 5000.0)

        updates = rc.update(dt_sec=5.0)

        assert rc.get_current("EV3") == 5000.0


# Standalone test runner for environments without pytest
if __name__ == "__main__":
    import traceback

    def run_tests():
        """Run all tests without pytest."""
        test_classes = [TestEVRampState, TestRampController]
        passed = 0
        failed = 0

        for cls in test_classes:
            instance = cls()
            for name in dir(instance):
                if name.startswith("test_"):
                    try:
                        getattr(instance, name)()
                        print(f"  PASS: {cls.__name__}.{name}")
                        passed += 1
                    except AssertionError as e:
                        print(f"  FAIL: {cls.__name__}.{name}")
                        traceback.print_exc()
                        failed += 1
                    except Exception as e:
                        print(f"  ERROR: {cls.__name__}.{name}: {e}")
                        traceback.print_exc()
                        failed += 1

        print(f"\n{passed} passed, {failed} failed")
        return failed == 0

    print("Running RampController tests...\n")
    success = run_tests()
    sys.exit(0 if success else 1)

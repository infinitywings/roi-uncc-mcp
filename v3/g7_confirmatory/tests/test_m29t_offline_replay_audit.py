from __future__ import annotations

from pathlib import Path

from g7confirm import m29t_offline_replay_audit as audit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "m29s_factorial_attempt4"
REPLAY = ROOT / "artifacts" / "m29t_offline_replay_attempt1" / "replay_receipt.json"


def test_independent_recomputation_matches_replay() -> None:
    issues, summary = audit.audit(SOURCE, REPLAY)
    assert issues == []
    groups = {
        (row["split"], row["interface"]): row
        for row in summary["by_split_interface"]
    }
    assert groups[("development", "flat")]["O2_canonical_arrays"]["all_slot_exact"] == 46
    assert groups[("held_out", "flat")]["O2_canonical_arrays"]["all_slot_exact"] == 45
    assert groups[("development", "staged")]["O3_tool_ledger"]["all_slot_exact"] == 32
    assert groups[("held_out", "staged")]["O3_tool_ledger"]["all_slot_exact"] == 32
    assert groups[("development", "staged")]["O5_tool_ledger_projection"]["all_slot_exact"] == 21
    assert groups[("held_out", "staged")]["O5_tool_ledger_projection"]["all_slot_exact"] == 20
    assert summary["single_wrong_slot_bottlenecks_after_o5"]["strategy_id"] == 69


def test_audit_receipt_is_zero_call_and_scope_sealed() -> None:
    receipt = audit.build_audit(SOURCE, REPLAY)
    assert receipt["status"] == "passed"
    assert receipt["issues"] == []
    assert receipt["new_model_calls"] == 0
    assert receipt["m29b_authorized"] is False
    assert receipt["final_evaluation_authorized"] is False
    assert receipt["independent_imports_replay_implementation"] is False

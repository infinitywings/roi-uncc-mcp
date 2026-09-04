from __future__ import annotations

import json
from pathlib import Path

import pytest

from g7confirm import m29t_offline_replay as replay


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "m29s_factorial_attempt4"


def _visible() -> dict:
    return {
        "visible_evidence": {
            "condition_id": "m29s_development_example_left",
            "records": [
                {
                    "record_id": "m29s_ev_example_superseded",
                    "status": "superseded",
                    "authority": "advisory",
                },
                {
                    "record_id": "m29s_ev_example_active",
                    "status": "active",
                    "authority": "operator",
                },
                {
                    "record_id": "m29s_ev_example_expired",
                    "status": "expired",
                    "authority": "planning",
                },
            ],
        },
        "corpus_passages": [],
    }


def test_parse_saved_json_rejects_duplicate_keys() -> None:
    with pytest.raises(replay.M29TReplayError, match="duplicate JSON key"):
        replay.parse_saved_json('{"a": 1, "a": 2}')


def test_expected_ledger_uses_only_active_authority() -> None:
    ledger = replay.expected_ledger(_visible())
    assert ledger["authority_order"] == ["operator"]
    assert ledger["active_evidence_ids"] == ["m29s_ev_example_active"]
    assert ledger["superseded_evidence_ids"] == ["m29s_ev_example_superseded"]
    assert ledger["expired_evidence_ids"] == ["m29s_ev_example_expired"]


def test_projection_uses_submitted_values_and_evidence_only() -> None:
    slots = {
        slot: {"value": f"submitted-{slot}", "supporting_evidence_ids": [f"ev-{slot}"]}
        for slot in replay.SLOT_KEYS
    }
    draft = {
        "semantic_slots": {"slots": slots},
        "strategy_program": {"compiler_id": "saved", "strategy_id": "old"},
    }
    repaired = replay.repair_projection(draft)
    assert repaired is not None
    assert repaired["strategy_program"]["strategy_id"] == "submitted-strategy_id"
    assert repaired["strategy_program"]["compiler_id"] == "saved"
    assert repaired["strategy_program"]["required_evidence_ids"] == sorted(
        f"ev-{slot}" for slot in replay.SLOT_KEYS
    )


def test_canonical_arrays_change_only_registered_unordered_slots() -> None:
    assert replay._semantic(["b", "a"], "allowed_targets", True) == ["a", "b"]
    assert replay._semantic(["b", "a"], "forbidden_windows", True) == ["a", "b"]
    assert replay._semantic(["b", "a"], "strategy_id", True) == ["b", "a"]


def test_full_replay_is_zero_call_and_complete() -> None:
    receipt = replay.build_replay(SOURCE)
    assert receipt["classification"] == "PRELIMINARY_ONLY"
    assert receipt["replayed_llm_cell_count"] == 320
    assert receipt["new_model_calls"] == 0
    assert receipt["new_embedding_calls"] == 0
    assert receipt["maximum_cumulative_model_calls"] == 816
    assert receipt["remaining_authorized_model_calls"] == 184
    assert receipt["m29b_authorized"] is False
    assert receipt["final_evaluation_authorized"] is False
    assert len(receipt["cells"]) == 320
    json.dumps(receipt, allow_nan=False)

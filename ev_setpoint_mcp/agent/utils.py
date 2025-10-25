"""Utility helpers for logging and JSON parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def ensure_json_object(text: str) -> Dict[str, object]:
    """Parse a JSON object from LLM output."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract JSON object substring
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise ValueError("No JSON object found") from None
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object at top level")
    return parsed


def log_json_line(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")

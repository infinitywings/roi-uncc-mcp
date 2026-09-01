"""Leakage audit and rendering for the clean confirmatory prompt."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


class PromptAuditError(ValueError):
    """Raised when prompt material contains forbidden information."""


_FORBIDDEN_STATIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("benign alarm horizon", re.compile(r"benign.{0,20}(self[- ]?alarm|alarm)", re.I)),
    ("explicit alarm horizon", re.compile(r"alarm.{0,24}(around|near|~|at)\s*(window\s*)?\d+", re.I)),
    ("empirical alpha threshold", re.compile(r"(?:threshold|best|optimal).{0,24}(?:alpha|amplitude).{0,8}0\.(?:05|15)", re.I)),
    ("empirical alpha ranking", re.compile(r"(?:alpha|amplitude).{0,8}0\.(?:05|15).{0,24}(?:best|optimal|threshold)", re.I)),
    ("legacy outcome", re.compile(r"0\.(?:080149|020697)")),
    ("post-result frequency heuristic", re.compile(r"many\s+small|small\s+frequent|do\s+not\s+stack", re.I)),
    ("empirical noise disclosure", re.compile(r"noise\s+(?:sd|standard deviation)\s*[:=~]?\s*0\.00[125]", re.I)),
)


def load_prompt(path: str | Path) -> dict[str, Any]:
    prompt = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(prompt, dict):
        raise PromptAuditError("prompt file must contain an object")
    required = {"prompt_id", "condition", "system", "user_template", "empty_history",
                "response_contract"}
    missing = required.difference(prompt)
    if missing:
        raise PromptAuditError(f"prompt missing required fields: {sorted(missing)}")
    audit_static_prompt(prompt)
    return prompt


def audit_text(text: str) -> list[str]:
    return [label for label, pattern in _FORBIDDEN_STATIC_PATTERNS if pattern.search(text)]


def audit_static_prompt(prompt: dict[str, Any]) -> None:
    static_text = "\n".join(str(prompt[key]) for key in
                            ("system", "user_template", "empty_history"))
    findings = audit_text(static_text)
    if findings:
        raise PromptAuditError("forbidden static prompt disclosure(s): " + ", ".join(findings))
    if prompt.get("condition") != "confirmatory_uninformed":
        raise PromptAuditError("prompt condition must be confirmatory_uninformed")
    contract = prompt.get("response_contract", {})
    if contract.get("additional_properties") is not False:
        raise PromptAuditError("response contract must reject additional properties")


def validate_development_history(history: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = {"proposal_index", "amplitude_fraction", "period_windows",
               "paired_harm_before_alarm", "first_alarm_window", "status", "partition"}
    cleaned: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            raise PromptAuditError("history entries must be objects")
        extras = set(item).difference(allowed)
        if extras:
            raise PromptAuditError(f"history contains unapproved fields: {sorted(extras)}")
        if item.get("partition") != "development":
            raise PromptAuditError("only development-partition outcomes may enter the prompt")
        cleaned.append(dict(item))
    return cleaned


def render_messages(prompt: dict[str, Any], *, amplitudes: list[float], periods: list[int],
                    window_cap: int, energy_cap: float,
                    history: Iterable[dict[str, Any]] = ()) -> list[dict[str, str]]:
    audit_static_prompt(prompt)
    clean_history = validate_development_history(history)
    history_text = (json.dumps(clean_history, sort_keys=True, ensure_ascii=False)
                    if clean_history else prompt["empty_history"])
    user = prompt["user_template"].format(
        amplitudes=json.dumps(amplitudes),
        periods=json.dumps(periods),
        window_cap=window_cap,
        energy_cap=energy_cap,
        history=history_text,
    )
    return [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": user},
    ]


def prompt_sha256(prompt: dict[str, Any]) -> str:
    encoded = json.dumps(prompt, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


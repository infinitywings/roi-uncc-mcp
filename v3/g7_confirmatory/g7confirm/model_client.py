"""Strict client for one bounded OpenAI-compatible schedule proposal."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


class ModelClientError(RuntimeError):
    """Fail-closed model discovery, transport, or response error."""


@dataclass(frozen=True)
class Proposal:
    amplitude_fraction: float
    period_windows: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("G7_LLM_API_KEY")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request_json(url: str, *, timeout_s: float,
                 payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Perform one bounded JSON request for an explicitly gated model smoke."""

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=_headers(),
                                     method="GET" if payload is None else "POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ModelClientError(f"model request failed closed: {type(exc).__name__}: {exc}") from exc
    if not isinstance(body, dict):
        raise ModelClientError("model endpoint returned a non-object response")
    return body


def discover_model(base_url: str, model_id: str, timeout_s: float) -> dict[str, Any]:
    body = request_json(base_url.rstrip("/") + "/models", timeout_s=timeout_s)
    models = body.get("data")
    if not isinstance(models, list):
        raise ModelClientError("/models response is missing data[]")
    match = next((item for item in models if isinstance(item, dict) and item.get("id") == model_id), None)
    if match is None:
        advertised = [item.get("id") for item in models if isinstance(item, dict)]
        raise ModelClientError(f"model_id_mismatch: expected {model_id!r}, advertised={advertised!r}")
    return match


def _extract_objects(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects


def parse_proposal(content: str, amplitudes: list[float], periods: list[int]) -> Proposal:
    objects = _extract_objects(content.strip())
    required = {"amplitude_fraction", "period_windows", "rationale"}
    candidates = [item for item in objects if set(item) == required]
    if not candidates:
        raise ModelClientError("no exact-contract proposal JSON object found")
    item = candidates[-1]
    try:
        amplitude = float(item["amplitude_fraction"])
        period_float = float(item["period_windows"])
    except (TypeError, ValueError) as exc:
        raise ModelClientError("proposal values are not numeric") from exc
    if not any(abs(amplitude - float(value)) <= 1e-12 for value in amplitudes):
        raise ModelClientError(f"proposal amplitude {amplitude} is outside the candidate set")
    if not period_float.is_integer() or int(period_float) not in set(map(int, periods)):
        raise ModelClientError(f"proposal period {item['period_windows']!r} is outside the candidate set")
    rationale = item["rationale"]
    if not isinstance(rationale, str):
        raise ModelClientError(
            f"proposal rationale must be a string, got {type(rationale).__name__}"
        )
    if not rationale.strip():
        raise ModelClientError("proposal rationale is empty")
    if len(rationale) > 1000:
        raise ModelClientError(f"proposal rationale is too long ({len(rationale)} characters)")
    return Proposal(amplitude, int(period_float), rationale.strip())


def proposal_response_format(amplitudes: list[float], periods: list[int]) -> dict[str, Any]:
    """Build the strict guided-decoding contract sent to the vLLM endpoint."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "g7_schedule_proposal",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "amplitude_fraction": {
                        "type": "number",
                        "enum": list(map(float, amplitudes)),
                    },
                    "period_windows": {
                        "type": "integer",
                        "enum": list(map(int, periods)),
                    },
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1000,
                    },
                },
                "required": ["amplitude_fraction", "period_windows", "rationale"],
                "additionalProperties": False,
            },
        },
    }


def request_proposal(*, base_url: str, model_id: str, messages: list[dict[str, str]],
                     amplitudes: list[float], periods: list[int], temperature: float,
                     max_tokens: int, timeout_s: float, seed: int = 8101) -> dict[str, Any]:
    model_record = discover_model(base_url, model_id, timeout_s)
    payload = {
        "model": model_id,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "seed": int(seed),
        "stream": False,
        # vLLM guided decoding constrains field types and candidate membership;
        # parse_proposal still independently validates the returned bytes.
        "response_format": proposal_response_format(amplitudes, periods),
        # Qwen thinking is useful for open-ended work but can consume the entire
        # bounded smoke allowance before emitting final content. vLLM forwards
        # this to the Qwen chat template; the confirmatory proposal remains a
        # direct, auditable JSON decision.
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": messages,
    }
    body = request_json(base_url.rstrip("/") + "/chat/completions",
                        timeout_s=timeout_s, payload=payload)
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelClientError("completion response is missing choices[0].message") from exc
    content = message.get("content") or ""
    if not isinstance(content, str) or not content.strip():
        finish_reason = None
        try:
            finish_reason = body["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError):
            pass
        safe_fields = sorted(str(key) for key in message)
        raise ModelClientError(
            "completion returned no final proposal content "
            f"(finish_reason={finish_reason!r}, message_fields={safe_fields!r})"
        )
    proposal = parse_proposal(content, amplitudes, periods)
    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                                 ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "model_record": {
            key: model_record.get(key)
            for key in ("id", "owned_by", "root", "max_model_len")
            if key in model_record
        },
        "request_sha256": request_hash,
        "proposal": proposal.to_dict(),
        "raw_content": content,
        "finish_reason": body["choices"][0].get("finish_reason"),
        "usage": body.get("usage"),
    }

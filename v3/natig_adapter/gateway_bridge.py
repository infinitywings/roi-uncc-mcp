"""Deterministic DNP3-object to semantic-gateway bridge for GridEval G4.

DNP3 G41V1 carries a point index, signed count, and status; it does not carry
the GridEval semantic envelope.  This bridge is therefore an explicit trust
boundary.  A configured master/outstation binding supplies identity, while a
monotonic local transaction number supplies message identity and sequence.
SELECT stores the reconstructed envelope and OPERATE must present the exact
same station, point, and object body before the envelope is passed onward.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from v3.cyber_gateway import CyberGateway
from v3.natig_adapter.dnp3_codec import (
    Dnp3CodecError,
    Group41v1Command,
    decode_group41v1,
)


@dataclass(frozen=True)
class AdapterBinding:
    """Static identity assigned to one authenticated DNP3 association."""

    master_address: int = 1
    outstation_address: int = 4
    source: str = "ev_controller_v3"
    target: str = "DER_EV4_BESS"


class Dnp3GatewayBridge:
    """Reconstruct semantic commands from a fixed DNP3 association.

    This class does not authenticate a network connection.  The caller that
    owns the DNP3 session must instantiate one bridge per authenticated
    master/outstation association and pass the observed addresses on every
    call.  The synthesized event time is the outstation receipt time, not an
    untransported controller timestamp.
    """

    def __init__(
        self,
        gateway: CyberGateway,
        *,
        binding: AdapterBinding = AdapterBinding(),
    ) -> None:
        self.gateway = gateway
        self.binding = binding
        self._transaction_sequence = 0
        self._selected: dict[tuple[int, int], dict[str, Any]] = {}

    def process_group41v1(
        self,
        payload: bytes | bytearray | memoryview,
        *,
        point_index: int,
        operation: str,
        receive_time_s: float,
        master_address: int,
        outstation_address: int,
    ) -> dict[str, Any]:
        """Validate one G41V1 SELECT/OPERATE and forward it to the gateway."""

        if operation not in {"select", "operate"}:
            return self._adapter_reject("unsupported_operation")
        if master_address != self.binding.master_address:
            return self._adapter_reject("wrong_master_address")
        if outstation_address != self.binding.outstation_address:
            return self._adapter_reject("wrong_outstation_address")
        if (
            not isinstance(receive_time_s, (int, float))
            or isinstance(receive_time_s, bool)
            or not math.isfinite(float(receive_time_s))
            or receive_time_s < 0
        ):
            return self._adapter_reject("invalid_receive_time")

        try:
            decoded = decode_group41v1(
                payload,
                point_index=point_index,
                point_map=self.gateway.point_map,
            )
        except Dnp3CodecError as exc:
            return self._adapter_reject("invalid_dnp3_object", detail=str(exc))

        key = (outstation_address, decoded.point_index)
        body_digest = hashlib.sha256(bytes(payload)).hexdigest()
        if operation == "select":
            return self._select(
                key=key,
                decoded=decoded,
                body_digest=body_digest,
                receive_time_s=float(receive_time_s),
            )
        return self._operate(
            key=key,
            decoded=decoded,
            body_digest=body_digest,
            receive_time_s=float(receive_time_s),
        )

    def _select(
        self,
        *,
        key: tuple[int, int],
        decoded: Group41v1Command,
        body_digest: str,
        receive_time_s: float,
    ) -> dict[str, Any]:
        self._transaction_sequence += 1
        transaction = self._transaction_sequence
        timeout_s = float(
            self.gateway.point_map["select_before_operate"]["timeout_s"]
        )
        message = {
            "schema_version": "0.1",
            "kind": "command",
            "message_id": (
                f"dnp3-o{self.binding.outstation_address}-"
                f"t{transaction:08d}-ao{decoded.point_index}-"
                f"{body_digest[:16]}"
            ),
            "event_time_s": receive_time_s,
            "source": self.binding.source,
            "target": self.binding.target,
            "sequence": transaction,
            "type": decoded.command_type,
            "payload": {
                "value": decoded.value,
                "unit": decoded.unit,
                "valid_until_s": receive_time_s + timeout_s,
                "quality": ["online"],
            },
        }
        gateway_result = self.gateway.ingest(
            message,
            operation="select",
            receive_time_s=receive_time_s,
        )
        if gateway_result["gateway_decision"] != "selected":
            return {
                "adapter_decision": "rejected",
                "reason": "gateway_rejected_select",
                "gateway_result": gateway_result,
            }
        self._selected[key] = {
            "body_digest": body_digest,
            "message": message,
        }
        return {
            "adapter_decision": "selected",
            "reason": "dnp3_select_forwarded",
            "transaction_sequence": transaction,
            "semantic_message": deepcopy(message),
            "gateway_result": gateway_result,
        }

    def _operate(
        self,
        *,
        key: tuple[int, int],
        decoded: Group41v1Command,
        body_digest: str,
        receive_time_s: float,
    ) -> dict[str, Any]:
        selected = self._selected.get(key)
        if selected is None:
            return self._adapter_reject("adapter_select_required")
        if selected["body_digest"] != body_digest:
            return self._adapter_reject("adapter_select_mismatch")
        message = selected["message"]
        gateway_result = self.gateway.ingest(
            message,
            operation="operate",
            receive_time_s=receive_time_s,
        )
        del self._selected[key]
        if gateway_result["gateway_decision"] != "accepted":
            return {
                "adapter_decision": "rejected",
                "reason": "gateway_rejected_operate",
                "semantic_message": deepcopy(message),
                "gateway_result": gateway_result,
            }
        return {
            "adapter_decision": "accepted",
            "reason": "dnp3_operate_forwarded",
            "transaction_sequence": message["sequence"],
            "semantic_message": deepcopy(message),
            "gateway_result": gateway_result,
        }

    @staticmethod
    def _adapter_reject(reason: str, *, detail: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "adapter_decision": "rejected",
            "reason": reason,
        }
        if detail is not None:
            result["detail"] = detail
        return result


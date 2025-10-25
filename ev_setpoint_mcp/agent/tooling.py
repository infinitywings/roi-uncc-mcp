"""Tool registry and MCP client wrappers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import requests


class MCPClient:
    """Simple HTTP client for MCP primitives."""

    def __init__(self, primitive_url: str, timeout: int = 30):
        self.primitive_url = primitive_url
        self.timeout = timeout

    def call(self, method: str, params: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        payload = {"method": method, "params": params or {}}
        resp = requests.post(self.primitive_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise RuntimeError(f"Primitive {method} failed: {data}")
        return data.get("result", {})


@dataclass
class Tool:
    name: str
    description: str
    method: str
    schema: Dict[str, object]
    executor: Callable[[MCPClient, Dict[str, object]], Dict[str, object]]


def _execute_mcp(client: MCPClient, method: str, params: Dict[str, object]) -> Dict[str, object]:
    return client.call(method, params)


def _with_bounds(min_kw: float, max_kw: float, params: Dict[str, object]) -> Dict[str, object]:
    real_kw = float(params.get("real_kw", 0.0))
    if real_kw < min_kw or real_kw > max_kw:
        raise ValueError(f"real_kw must be between {min_kw} and {max_kw}")
    params["real_kw"] = real_kw
    params.setdefault("reactive_kvar", 0.0)
    return params


class ToolRegistry:
    """Holds available tools and provides execution helpers."""

    def __init__(self, client: MCPClient):
        self.client = client
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_default_tools(self) -> None:
        self.register(
            Tool(
                name="discover_topology",
                description="Retrieve static feeder topology and EV station metadata.",
                method="discover_topology",
                schema={"type": "object", "properties": {}, "additionalProperties": False},
                executor=lambda client, params: _execute_mcp(client, "discover_topology", params),
            )
        )
        self.register(
            Tool(
                name="monitor_protection_systems",
                description="Check protection relays and feeder load limits.",
                method="monitor_protection_systems",
                schema={"type": "object", "properties": {}, "additionalProperties": False},
                executor=lambda client, params: _execute_mcp(client, "monitor_protection_systems", params),
            )
        )
        self.register(
            Tool(
                name="analyze_power_flow",
                description="Request aggregate power-flow analysis from MCP.",
                method="analyze_power_flow",
                schema={"type": "object", "properties": {}, "additionalProperties": False},
                executor=lambda client, params: _execute_mcp(client, "analyze_power_flow", params),
            )
        )
        self.register(
            Tool(
                name="set_ev_capacity",
                description="Issue EV capacity command (real_kw within [-500, 4000]).",
                method="set_ev_capacity",
                schema={
                    "type": "object",
                    "properties": {
                        "ev_id": {"type": "string"},
                        "real_kw": {"type": "number"},
                        "reactive_kvar": {"type": "number"},
                    },
                    "required": ["ev_id", "real_kw"],
                    "additionalProperties": True,
                },
                executor=lambda client, params: _execute_mcp(
                    client, "set_ev_capacity", _with_bounds(-500.0, 4000.0, params)
                ),
            )
        )

    def describe_tools(self, names: Optional[List[str]] = None) -> List[Dict[str, str]]:
        use_names = names or list(self._tools.keys())
        specs = []
        for name in use_names:
            tool = self._tools.get(name)
            if not tool:
                continue
            specs.append({"name": tool.name, "description": tool.description, "schema": json.dumps(tool.schema)})
        return specs

    def execute(self, name: str, params: Dict[str, object]) -> Dict[str, object]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool '{name}'")
        tool = self._tools[name]
        return tool.executor(self.client, params)

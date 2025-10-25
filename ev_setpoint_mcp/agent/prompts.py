"""Prompt templates for the MCP agent."""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Dict, List


DEFAULT_SYSTEM_PROMPT = dedent(
    """\
    You are an adversarial research agent operating against a simulated power distribution grid.
    The grid is an IEEE 13-bus feeder running in a HELICS-based co-simulation. Your mission is to
    study vulnerabilities, gather intelligence, and execute strategic EV setpoint attacks while
    respecting research safety guidelines. Treat all tooling as simulated; never imply real-world impact.
    """
)


class PromptBuilder:
    """Builds prompts that expose memory, telemetry, and tool metadata."""

    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.system_prompt = system_prompt

    @staticmethod
    def format_tools(tool_specs: List[Dict[str, str]]) -> str:
        lines = []
        for spec in tool_specs:
            line = f"- {spec['name']}: {spec['description']}"
            lines.append(line)
        return "\n".join(lines)

    def build_messages(
        self,
        memory_summary: str,
        observation: Dict[str, object],
        tool_specs: List[Dict[str, str]],
        instructions: str,
    ):
        observation_json = json.dumps(observation, ensure_ascii=False, indent=2)
        tools_text = self.format_tools(tool_specs)
        user_content = dedent(
            f"""\
            ## Recent History
            {memory_summary}

            ## Current Observation
            {observation_json}

            ## Available Tools
            {tools_text}

            ## Instructions
            {instructions}

            Respond with a JSON object containing an "actions" array where each entry has:
              - "tool": name from the tool list above
              - "params": JSON object with parameters for that tool
            Optionally include "commentary" explaining the rationale.
            """
        )
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

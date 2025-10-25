#!/usr/bin/env bash

set -euo pipefail

PRIMITIVE_URL=${AGENT_PRIMITIVE_URL:-http://ev-mcp:5100/primitive}
LOG_DIR=${AGENT_LOG_DIR:-/workspace/examples/2bus-13bus/logs}
mkdir -p "${LOG_DIR}"

python /app/ev_setpoint_mcp/tools/run_agent.py \
  --server "${PRIMITIVE_URL}" \
  --llm-base "${LLM_API_BASE:-http://ccil1s26m8hj6lws:8000/v1}" \
  --model "${LLM_MODEL:-openai/gpt-oss-120b}" \
  --interval "${AI_AGENT_INTERVAL:-5}" \
  --action-delay "${AI_AGENT_ACTION_DELAY:-1}" \
  --steps "${AI_AGENT_STEPS:-0}" \
  --wait "${AI_AGENT_WAIT:-120}" \
  --duration-seconds "${AI_AGENT_DURATION:-86400}" \
  --log "${LOG_DIR}/ai_campaign.log" \
  --llm-log "${LOG_DIR}/llm_interactions.jsonl" \
  --tools "${AI_AGENT_TOOLS:-discover_topology monitor_protection_systems analyze_power_flow set_ev_capacity}" \
  ${AI_AGENT_INSTRUCTIONS:+--instructions "${AI_AGENT_INSTRUCTIONS}"}

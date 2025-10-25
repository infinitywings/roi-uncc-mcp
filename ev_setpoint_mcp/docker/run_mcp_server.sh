#!/usr/bin/env bash

set -euo pipefail

CONFIG_PATH=${MCP_CONFIG_PATH:-/app/ev_setpoint_mcp/config/ev_mcp_local.yaml}
LOG_PATH=${MCP_LOG_PATH:-/workspace/examples/2bus-13bus/logs/attacker.log}

mkdir -p "$(dirname "${LOG_PATH}")"

python /app/ev_setpoint_mcp/run_server.py --config "${CONFIG_PATH}" >"${LOG_PATH}" 2>&1

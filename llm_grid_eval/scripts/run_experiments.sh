#!/usr/bin/env bash

set -euo pipefail

MCP_URL="${MCP_URL:-http://localhost:5100}"
OUT_DIR="${OUT_DIR:-results}"
DURATION_SEC="${DURATION_SEC:-1800}"

echo "[1/3] Validating server..."
python3 llm_grid_eval/scripts/validate_setup.py --mcp-url "${MCP_URL}"

echo "[2/3] Running random baseline..."
python3 llm_grid_eval/scripts/run_random_baseline.py \
  --mcp-url "${MCP_URL}" \
  --duration "${DURATION_SEC}" \
  --experiment-name "random_${DURATION_SEC}s" \
  --output-dir "${OUT_DIR}"

echo "[3/3] Running AI campaign..."
python3 llm_grid_eval/scripts/run_ai_campaign.py \
  --mcp-url "${MCP_URL}" \
  --duration "${DURATION_SEC}" \
  --experiment-name "ai_${DURATION_SEC}s" \
  --output-dir "${OUT_DIR}"

echo "Done. Results in ${OUT_DIR}/"


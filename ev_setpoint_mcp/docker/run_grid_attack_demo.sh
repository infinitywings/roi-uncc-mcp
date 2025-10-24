#!/usr/bin/env bash

set -euo pipefail

WORKDIR=/workspace/examples/2bus-13bus
LOG_DIR="${WORKDIR}/logs"
BROKER_PORT=23404
BROKER_ADDR="tcp://localhost:${BROKER_PORT}"

mkdir -p "${LOG_DIR}"

cd "${WORKDIR}"

# Verify existing build cache matches current workspace; rebuild if it does not.
if [ -f build/CMakeCache.txt ]; then
  if ! grep -q "/workspace/examples/2bus-13bus" build/CMakeCache.txt >/dev/null 2>&1; then
    echo "[setup] Detected stale GridPACK build cache, rebuilding..."
    rm -rf build
  fi
fi

if [ ! -x build/gpk-left-fed.x ]; then
  echo "[setup] Building GridPACK federate..."
  mkdir -p build
  pushd build >/dev/null
  cmake ..
  make -j"$(nproc)"
  popd >/dev/null
fi

cleanup() {
  echo "[teardown] Stopping all federates..."
  pkill -P $$ || true
}
trap cleanup EXIT

echo "[startup] Launching HELICS broker on ${BROKER_ADDR}"
helics_broker -f5 --port="${BROKER_PORT}" --loglevel=warning --local \
  >"${LOG_DIR}/broker.log" 2>&1 &

sleep 2

echo "[startup] Launching GridLAB-D feeders"
HELICS_BROKER="${BROKER_ADDR}" gridlabd 1c_IEEE_123_feeder.glm \
  >"${LOG_DIR}/gld1.log" 2>&1 &
HELICS_BROKER="${BROKER_ADDR}" gridlabd 1c_IEEE_123_feeder_2.glm \
  >"${LOG_DIR}/gld2.log" 2>&1 &

echo "[startup] Launching EV controller"
HELICS_BROKER="${BROKER_ADDR}" python 1bc_EV_Controller.py -c 1c \
  >"${LOG_DIR}/controller.log" 2>&1 &

echo "[startup] Launching GridPACK federate"
HELICS_BROKER="${BROKER_ADDR}" ./build/gpk-left-fed.x \
  >"${LOG_DIR}/gridpack.log" 2>&1 &

echo "[startup] Launching EV attacker MCP"
HELICS_BROKER="${BROKER_ADDR}" \
HELICS_BROKER_ADDRESS="${BROKER_ADDR}" \
python /app/ev_setpoint_mcp/run_server.py --config /app/ev_setpoint_mcp/config/ev_mcp_local.yaml \
  >"${LOG_DIR}/attacker.log" 2>&1 &

if [ "${RUN_AI_CAMPAIGN:-1}" != "0" ]; then
  echo "[startup] Scheduling AI campaign (steps=${AI_CAMPAIGN_STEPS:-0}, interval=${AI_CAMPAIGN_INTERVAL:-60}s, duration=${AI_CAMPAIGN_DURATION:-86400}s)"
  LLM_API_BASE=${LLM_API_BASE:-http://ccil1s26m8hj6lws:8000/v1}
  LLM_MODEL=${LLM_MODEL:-openai/gpt-oss-120b}
  python /app/ev_setpoint_mcp/tools/run_ai_campaign.py \
    --server http://localhost:5100/primitive \
    --llm-base "${LLM_API_BASE}" \
    --model "${LLM_MODEL}" \
    --steps "${AI_CAMPAIGN_STEPS:-0}" \
    --interval "${AI_CAMPAIGN_INTERVAL:-60}" \
    --wait "${AI_CAMPAIGN_WAIT:-120}" \
    --duration-seconds "${AI_CAMPAIGN_DURATION:-86400}" \
    --log "${LOG_DIR}/ai_campaign.log" \
    --llm-log "${LOG_DIR}/llm_interactions.jsonl" &
fi

echo "[startup] All federates launched. Streams available in ${LOG_DIR}."
echo "[runtime] Press Ctrl+C to stop."

wait

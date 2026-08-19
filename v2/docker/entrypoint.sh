#!/usr/bin/env bash
# LLM-GridEval v2 — Federation entrypoint
#
# Manual federate launch (proven pattern from successful inline test).
# Key insight: all processes must run in the same shell (no exec).

set -uo pipefail

SIM_DIR="/app/examples/2bus-13bus"
BROKER_PORT="${BROKER_PORT:-23404}"
BROKER_ADDR="tcp://localhost:${BROKER_PORT}"

# --- GridLAB-D unit file fix (idempotent) ----------------------------------
UNITFILE=/usr/local/gridlabd/share/unitfile.txt
if [ -f "${UNITFILE}" ] && ! grep -q '^utility' "${UNITFILE}" 2>/dev/null; then
    echo "utility = 1.0;" >> "${UNITFILE}"
    echo "[setup] Added 'utility' unit to GridLAB-D unitfile"
fi

# --- Build GridPACK federate if needed -------------------------------------
cd "${SIM_DIR}"
if [ -f build/CMakeCache.txt ]; then
    grep -q "${SIM_DIR}" build/CMakeCache.txt 2>/dev/null || { echo "[setup] Stale build"; rm -rf build; }
fi
if [ ! -x build/gpk-left-fed.x ]; then
    echo "[setup] Building GridPACK..."
    mkdir -p build && cd build && cmake .. && make -j"$(nproc)" && cd "${SIM_DIR}"
    echo "[setup] GridPACK build complete"
fi

# --- Cleanup on exit -------------------------------------------------------
cleanup() {
    echo "[teardown] Stopping all federates..."
    kill 0 2>/dev/null
    wait 2>/dev/null
}
trap cleanup EXIT INT TERM

# --- Start broker ----------------------------------------------------------
echo "[startup] HELICS broker on port ${BROKER_PORT}"
helics_broker -f5 --port="${BROKER_PORT}" &
sleep 3

# --- Start federates -------------------------------------------------------
cd "${SIM_DIR}"

echo "[startup] GridLAB-D Feeder A"
HELICS_BROKER="${BROKER_ADDR}" gridlabd 1c_IEEE_123_feeder.glm &
sleep 1

echo "[startup] GridLAB-D Feeder B"
HELICS_BROKER="${BROKER_ADDR}" gridlabd 1c_IEEE_123_feeder_2.glm &
sleep 1

echo "[startup] GridPACK"
HELICS_BROKER="${BROKER_ADDR}" ./build/gpk-left-fed.x &
sleep 1

echo "[startup] Controller v2"
cd /app/v2/controller
HELICS_BROKER="${BROKER_ADDR}" python ev_controller_v2.py --config v2_control.json \
    --interval "${CTRL_INTERVAL_SEC:-10}" --seed "${CTRL_SEED:-42}" \
    --duration "${SIM_DURATION_SEC:-86400}" &
sleep 1

echo "[startup] MCP Server"
cd /app/llm_grid_eval
HELICS_BROKER="${BROKER_ADDR}" \
HELICS_BROKER_ADDRESS="${BROKER_ADDR}" \
PYTHONPATH=/app/llm_grid_eval/src \
    python -m llm_grid_eval.server --config /app/v2/configs/server.yaml &

echo "============================================="
echo "  LLM-GridEval v2 Federation Running"
echo "  MCP: http://localhost:5100/health"
echo "============================================="

# Wait for ALL children — keeps shell alive as parent
wait

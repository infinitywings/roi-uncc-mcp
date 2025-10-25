#!/usr/bin/env bash

set -euo pipefail

WORKDIR=/workspace/examples/2bus-13bus
LOG_DIR="${WORKDIR}/logs"
BROKER_PORT=${HELICS_BROKER_PORT:-23404}
BROKER_HOST=${HELICS_BROKER_HOST:-0.0.0.0}
BROKER_BIND="tcp://${BROKER_HOST}:${BROKER_PORT}"

mkdir -p "${LOG_DIR}"
cd "${WORKDIR}"

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
  echo "[teardown] Stopping simulation stack..."
  pkill -P $$ || true
}
trap cleanup EXIT

echo "[startup] Launching HELICS broker on ${BROKER_BIND}"
helics_broker -f5 --port="${BROKER_PORT}" --loglevel=warning \
  >"${LOG_DIR}/broker.log" 2>&1 &

sleep 2

echo "[startup] Launching GridLAB-D feeders"
HELICS_BROKER="tcp://127.0.0.1:${BROKER_PORT}" gridlabd 1c_IEEE_123_feeder.glm \
  >"${LOG_DIR}/gld1.log" 2>&1 &
HELICS_BROKER="tcp://127.0.0.1:${BROKER_PORT}" gridlabd 1c_IEEE_123_feeder_2.glm \
  >"${LOG_DIR}/gld2.log" 2>&1 &

echo "[startup] Launching EV controller"
HELICS_BROKER="tcp://127.0.0.1:${BROKER_PORT}" python 1bc_EV_Controller.py -c 1c \
  >"${LOG_DIR}/controller.log" 2>&1 &

echo "[startup] Launching GridPACK federate"
HELICS_BROKER="tcp://127.0.0.1:${BROKER_PORT}" ./build/gpk-left-fed.x \
  >"${LOG_DIR}/gridpack.log" 2>&1 &

echo "[startup] Simulation stack running. Broker reachable at ${BROKER_BIND}"
echo "[runtime] Press Ctrl+C to stop."

wait

#!/bin/bash
set -euo pipefail

RD2C=/rd2c
CONTROL=${RD2C}/integration/control
NS3=${RD2C}/ns-3-dev
PRESET=${RD2C}/PUSH/NATIG/RC/code/3G-conf-123
POINTS=${RD2C}/PUSH/NATIG/RC/code/points-123
MODEL=ns3-helics-grid-dnp3

export RD2C
export PATH="${RD2C}/bin:/usr/local/bin:/usr/bin:/bin"
export LD_LIBRARY_PATH="${RD2C}/lib:${RD2C}/lib64:/usr/local/lib:/usr/local/lib64"
export GLPATH="${RD2C}/lib/gridlabd:${RD2C}/share/gridlabd"
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

cp "${POINTS}"/* "${CONTROL}/config/"
cp "${PRESET}"/*.json "${CONTROL}/config/"
cp "${PRESET}"/*.glm "${CONTROL}/"
cp "${CONTROL}/${MODEL}.cc" "${NS3}/scratch/${MODEL}.cc"

broker_pid=
gridlabd_pid=
ns3_pid=
cleanup() {
    for pid in "${ns3_pid}" "${gridlabd_pid}" "${broker_pid}"; do
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
        fi
    done
}
trap cleanup EXIT INT TERM

cd "${CONTROL}" || exit 90
helics_broker \
    --slowresponding \
    --federates=2 \
    --port=9000 \
    --loglevel=1 \
    > "${CONTROL}/output/helics_broker.log" 2>&1 &
broker_pid=$!

gridlabd \
    -D OUT_FOLDER="${CONTROL}/output" \
    "${CONTROL}/IEEE_123_Dynamic.glm" \
    > "${CONTROL}/output/gridlabd.log" 2>&1 &
gridlabd_pid=$!

cd "${NS3}" || exit 91
./waf --run \
    "scratch/${MODEL} --helicsConfig=${CONTROL}/config/gridlabd_config.json --microGridConfig=${CONTROL}/config/grid.json --topologyConfig=${CONTROL}/config/topology.json --pointFileDir=${CONTROL}/config/ --pcapFileDir=${CONTROL}/output/" \
    > "${CONTROL}/output/${MODEL}.log" 2>&1 &
ns3_pid=$!

set +e
wait "${ns3_pid}"
ns3_rc=$?
wait "${gridlabd_pid}"
gridlabd_rc=$?
wait "${broker_pid}"
broker_rc=$?
set -e
trap - EXIT INT TERM

printf 'federate_status ns3=%s gridlabd=%s broker=%s\n' \
    "${ns3_rc}" "${gridlabd_rc}" "${broker_rc}"

if [[ "${ns3_rc}" -ne 0 || "${gridlabd_rc}" -ne 0 || "${broker_rc}" -ne 0 ]]; then
    exit 92
fi

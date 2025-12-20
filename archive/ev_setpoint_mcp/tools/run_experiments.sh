#!/usr/bin/env bash
# Orchestrate baseline, random, and AI attackers across controller intervals.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_BASE="${PROJECT_ROOT}/experiment_logs"
RESULTS_BASE="${PROJECT_ROOT}/experiment_results"

DURATION_SEC="${DURATION_SEC:-7200}"
REPLICATES="${REPLICATES:-3}"
CONTROLLER_INTERVALS="30 60 120"

mkdir -p "$LOG_BASE" "$RESULTS_BASE"

run_experiment() {
    local attacker_type="$1"
    local controller_interval="$2"
    local replicate="$3"

    local exp_name="${attacker_type}_ctrl${controller_interval}_rep${replicate}"
    local log_dir="${LOG_BASE}/${exp_name}"
    local results_dir="${RESULTS_BASE}/${exp_name}"

    mkdir -p "$log_dir" "$results_dir"
    echo "[$(date)] Starting ${exp_name}"

    export CONTROLLER_INTERVAL_SEC="$controller_interval"
    cd "$PROJECT_ROOT"
    docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up -d --build
    sleep 30

    case "$attacker_type" in
        baseline)
            sleep "$((DURATION_SEC / 10))"
            ;;
        random)
            python3 "${SCRIPT_DIR}/run_random_baseline.py" \
                --server http://localhost:5100/primitive \
                --duration-seconds "$DURATION_SEC" \
                --interval 10 \
                --seed "$replicate" \
                --experiment-name "$exp_name" \
                --log "${log_dir}/campaign.log" \
                --results "${results_dir}/results.json"
            ;;
        ai)
            python3 "${SCRIPT_DIR}/run_ai_campaign_v2.py" \
                --server http://localhost:5100/primitive \
                --duration-seconds "$DURATION_SEC" \
                --interval 10 \
                --controller-interval "$controller_interval" \
                --experiment-name "$exp_name" \
                --log "${log_dir}/campaign.log" \
                --llm-log "${log_dir}/llm_interactions.jsonl" \
                --results "${results_dir}/results.json"
            ;;
    esac

    cp -r "${PROJECT_ROOT}/examples/2bus-13bus/logs/"* "$log_dir/" 2>/dev/null || true
    docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml down
    echo "[$(date)] Completed ${exp_name}"
}

for interval in $CONTROLLER_INTERVALS; do
    for rep in $(seq 1 "$REPLICATES"); do
        run_experiment "baseline" "$interval" "$rep"
        run_experiment "random" "$interval" "$rep"
        run_experiment "ai" "$interval" "$rep"
    done
done

python3 "${SCRIPT_DIR}/analyze_results.py" \
    --results-dir "$RESULTS_BASE" \
    --output "${RESULTS_BASE}/summary.json"

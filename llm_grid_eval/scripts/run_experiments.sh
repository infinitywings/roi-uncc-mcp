#!/usr/bin/env bash
#
# LLM-GridEval Experiment Runner
#
# Runs the full 2×2×3 mixed factorial design:
#   - Attacker Type: {baseline, random, ai}
#   - Controller Interval: {60s, 120s}
#   - Replicate/Seed: {1, 2, 3}
#
# Total: 18 experimental runs
#
# Usage:
#   ./run_experiments.sh                    # Run all 18 experiments
#   ./run_experiments.sh --quick            # Quick validation (30 min runs)
#   ./run_experiments.sh --attacker ai      # Run only AI experiments
#   ./run_experiments.sh --interval 60      # Run only 60s controller interval
#

set -euo pipefail

# Configuration
MCP_URL="${MCP_URL:-http://localhost:5100}"
OUT_DIR="${OUT_DIR:-results}"
DURATION_SEC="${DURATION_SEC:-7200}"  # 2 hours per experiment

# Parse arguments
ATTACKER_FILTER=""
INTERVAL_FILTER=""
QUICK_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            DURATION_SEC=1800  # 30 minutes for quick validation
            shift
            ;;
        --attacker)
            ATTACKER_FILTER="$2"
            shift 2
            ;;
        --interval)
            INTERVAL_FILTER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Experiment matrix
ATTACKERS=("baseline" "random" "ai")
INTERVALS=(60 120)
SEEDS=(1 2 3)

# Logging
LOG_DIR="${OUT_DIR}/logs"
mkdir -p "${LOG_DIR}"
MASTER_LOG="${LOG_DIR}/experiment_run_$(date +%Y%m%d_%H%M%S).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${MASTER_LOG}"
}

run_experiment() {
    local attacker="$1"
    local interval="$2"
    local seed="$3"
    local exp_name="${attacker}_${interval}s_r${seed}"
    local log_file="${LOG_DIR}/${exp_name}.log"

    log "Starting: ${exp_name} (duration=${DURATION_SEC}s)"

    case "${attacker}" in
        baseline)
            python3 llm_grid_eval/scripts/run_baseline.py \
                --mcp-url "${MCP_URL}" \
                --duration "${DURATION_SEC}" \
                --experiment-name "${exp_name}" \
                --output-dir "${OUT_DIR}" \
                2>&1 | tee "${log_file}"
            ;;
        random)
            python3 llm_grid_eval/scripts/run_random_baseline.py \
                --mcp-url "${MCP_URL}" \
                --duration "${DURATION_SEC}" \
                --seed "${seed}" \
                --experiment-name "${exp_name}" \
                --output-dir "${OUT_DIR}" \
                2>&1 | tee "${log_file}"
            ;;
        ai)
            python3 llm_grid_eval/scripts/run_ai_campaign.py \
                --mcp-url "${MCP_URL}" \
                --duration "${DURATION_SEC}" \
                --controller-interval "${interval}" \
                --seed "${seed}" \
                --experiment-name "${exp_name}" \
                --output-dir "${OUT_DIR}" \
                2>&1 | tee "${log_file}"
            ;;
    esac

    local status=$?
    if [[ ${status} -eq 0 ]]; then
        log "Completed: ${exp_name}"
    else
        log "FAILED: ${exp_name} (exit code ${status})"
    fi
    return ${status}
}

# Pre-flight check
log "=========================================="
log "LLM-GridEval Experiment Runner"
log "=========================================="
log "MCP URL: ${MCP_URL}"
log "Output directory: ${OUT_DIR}"
log "Duration per experiment: ${DURATION_SEC}s"
log "Quick mode: ${QUICK_MODE}"
log ""

# Validate server
log "Validating MCP server..."
if ! python3 llm_grid_eval/scripts/validate_setup.py --mcp-url "${MCP_URL}" 2>&1 | tee -a "${MASTER_LOG}"; then
    log "ERROR: Server validation failed. Aborting."
    exit 1
fi
log "Server validation passed."
log ""

# Count experiments to run
total_experiments=0
for attacker in "${ATTACKERS[@]}"; do
    [[ -n "${ATTACKER_FILTER}" && "${attacker}" != "${ATTACKER_FILTER}" ]] && continue
    for interval in "${INTERVALS[@]}"; do
        [[ -n "${INTERVAL_FILTER}" && "${interval}" != "${INTERVAL_FILTER}" ]] && continue
        for seed in "${SEEDS[@]}"; do
            ((total_experiments++))
        done
    done
done

log "Experiments to run: ${total_experiments}"
log ""

# Run experiments
completed=0
failed=0

for attacker in "${ATTACKERS[@]}"; do
    [[ -n "${ATTACKER_FILTER}" && "${attacker}" != "${ATTACKER_FILTER}" ]] && continue

    for interval in "${INTERVALS[@]}"; do
        [[ -n "${INTERVAL_FILTER}" && "${interval}" != "${INTERVAL_FILTER}" ]] && continue

        # NOTE: Controller interval is an EXTERNAL parameter set in the GridLAB-D
        # controller (1bc_EV_Controller.py). The --controller-interval flag in
        # run_ai_campaign.py only affects the timing ANALYSIS, not the actual
        # controller behavior.
        #
        # To run experiments with different controller intervals, you must:
        # 1. Stop the simulation
        # 2. Modify the controller configuration or use CONTROLLER_INTERVAL_SEC env var
        # 3. Restart the simulation
        # 4. Run the experiment
        #
        # For automated multi-interval experiments, coordinate with the simulation
        # orchestration layer.

        for seed in "${SEEDS[@]}"; do
            exp_name="${attacker}_${interval}s_r${seed}"
            log "----------------------------------------"
            log "Experiment $((completed + failed + 1))/${total_experiments}: ${exp_name}"
            log "----------------------------------------"

            if run_experiment "${attacker}" "${interval}" "${seed}"; then
                ((completed++))
            else
                ((failed++))
            fi

            # Brief pause between experiments
            sleep 5
        done
    done
done

# Summary
log ""
log "=========================================="
log "Experiment Run Complete"
log "=========================================="
log "Total experiments: ${total_experiments}"
log "Completed: ${completed}"
log "Failed: ${failed}"
log "Results in: ${OUT_DIR}/"
log "Logs in: ${LOG_DIR}/"

if [[ ${failed} -gt 0 ]]; then
    log "WARNING: Some experiments failed. Check logs for details."
    exit 1
fi

# Run analysis if all experiments completed
if [[ ${completed} -eq ${total_experiments} && ${total_experiments} -gt 1 ]]; then
    log ""
    log "Running analysis..."
    python3 llm_grid_eval/scripts/analyze_results.py --results-dir "${OUT_DIR}" 2>&1 | tee -a "${MASTER_LOG}" || true
fi

log "Done."

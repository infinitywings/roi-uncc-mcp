#!/usr/bin/env bash
# LLM-GridEval v2 — Parallel Experiment Campaign
#
# Runs 45 experiments across 3 Docker containers (one per operating point).
# Each container handles 15 experiments (3 variants × 5 seeds), restarting
# the federation between each run.
#
# Usage:
#   bash v2/run_campaign.sh
#   bash v2/run_campaign.sh --variant random   # only random
#   bash v2/run_campaign.sh --op hr7           # only Hour 7

set -uo pipefail

LLM_URL="http://cci-siscluster1.charlotte.edu:8000/v1"
LLM_MODEL="cyankiwi/Qwen3.5-122B-A10B-AWQ-4bit"
COMPOSE_PARALLEL="v2/docker/docker-compose-parallel.yml"
COMPOSE_SINGLE="v2/docker/docker-compose.yml"
OUT_BASE="v2/results/campaign"

# Operating point → MCP port mapping
declare -A OP_PORTS=( ["hr4"]=5101 ["hr7"]=5102 ["hr14"]=5103 )
declare -A OP_LABELS=( ["hr4"]="Hour 4 (low load)" ["hr7"]="Hour 7 (medium)" ["hr14"]="Hour 14 (high load)" )

SEEDS=(1 2 3 4 5)
VARIANTS=(random ai_v1 ai_v2)
OPS=(hr4 hr7 hr14)

# Parse args
FILTER_VARIANT=""
FILTER_OP=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --variant) FILTER_VARIANT="$2"; shift 2 ;;
        --op) FILTER_OP="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

LLM_ARGS="--llm-url $LLM_URL --llm-model $LLM_MODEL"

# --------------------------------------------------------------------------
# Run experiments for one operating point (called in parallel per OP)
# --------------------------------------------------------------------------
run_op() {
    local OP="$1"
    local PORT="${OP_PORTS[$OP]}"
    local MCP="http://localhost:${PORT}"
    local OP_OUT="${OUT_BASE}/${OP}"
    local LOG="${OUT_BASE}/${OP}_run.log"

    mkdir -p "$OP_OUT"

    echo "[${OP}] Starting experiments on port ${PORT}" | tee "$LOG"

    for VARIANT in "${VARIANTS[@]}"; do
        [[ -n "$FILTER_VARIANT" && "$VARIANT" != "$FILTER_VARIANT" ]] && continue

        for SEED in "${SEEDS[@]}"; do
            local NAME="${VARIANT}_${OP}_s${SEED}"
            local SCRIPT

            case "$VARIANT" in
                random) SCRIPT="v2/attackers/random_baseline.py" ;;
                ai_v1)  SCRIPT="v2/attackers/ai_v1_timing.py" ;;
                ai_v2)  SCRIPT="v2/attackers/ai_v2_strategy.py" ;;
            esac

            # Check if result already exists (skip re-runs)
            if [ -f "${OP_OUT}/${NAME}.json" ]; then
                echo "[${OP}] SKIP ${NAME} (already exists)" | tee -a "$LOG"
                continue
            fi

            echo "[${OP}] --- ${NAME} ---" | tee -a "$LOG"

            # Restart this container only (stop/start the specific service)
            docker compose -f "$COMPOSE_PARALLEL" stop "$OP" >/dev/null 2>&1
            docker compose -f "$COMPOSE_PARALLEL" start "$OP" >/dev/null 2>&1

            # Wait for health
            local READY=0
            for i in $(seq 1 60); do
                if curl -s --connect-timeout 3 "${MCP}/health" >/dev/null 2>&1; then
                    READY=1
                    break
                fi
                sleep 5
            done

            if [ "$READY" -eq 0 ]; then
                echo "[${OP}] FAIL ${NAME} — federation not ready" | tee -a "$LOG"
                continue
            fi

            # Build extra args for AI variants
            local EXTRA=""
            if [[ "$VARIANT" == ai_v1 || "$VARIANT" == ai_v2 ]]; then
                EXTRA="$LLM_ARGS"
            fi

            # Run
            python3 "$SCRIPT" \
                --mcp-url "$MCP" \
                --duration 300 \
                --seed "$SEED" \
                --experiment-name "$NAME" \
                --output-dir "$OP_OUT" \
                $EXTRA 2>&1 | grep -E "Starting|ATTACK|Campaign|TVD|ERROR" | tee -a "$LOG"

            if [ $? -eq 0 ]; then
                echo "[${OP}] ✓ ${NAME}" | tee -a "$LOG"
            else
                echo "[${OP}] ✗ ${NAME} FAILED" | tee -a "$LOG"
            fi
        done
    done

    echo "[${OP}] DONE — $(ls ${OP_OUT}/*.json 2>/dev/null | wc -l) results" | tee -a "$LOG"
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
mkdir -p "$OUT_BASE"

echo "============================================="
echo "  LLM-GridEval v2 — Parallel Campaign"
echo "  3 containers × 15 experiments each = 45 total"
echo "  Output: ${OUT_BASE}/"
echo "============================================="

# Start all 3 containers
echo "Starting 3 federation containers..."
docker compose -f "$COMPOSE_PARALLEL" up -d 2>&1 | grep -v "^$"

# Wait for all 3 to be healthy
echo "Waiting for all federations to be healthy..."
for OP in "${OPS[@]}"; do
    [[ -n "$FILTER_OP" && "$OP" != "$FILTER_OP" ]] && continue
    PORT="${OP_PORTS[$OP]}"
    for i in $(seq 1 60); do
        if curl -s --connect-timeout 3 "http://localhost:${PORT}/health" >/dev/null 2>&1; then
            echo "  ${OP} (port ${PORT}): healthy"
            break
        fi
        sleep 5
    done
done

# Run each operating point in parallel (background subshells)
PIDS=()
for OP in "${OPS[@]}"; do
    [[ -n "$FILTER_OP" && "$OP" != "$FILTER_OP" ]] && continue
    run_op "$OP" &
    PIDS+=($!)
    echo "Launched ${OP} experiments (PID ${PIDS[-1]})"
done

# Wait for all to finish
echo "Waiting for all experiments to complete..."
for PID in "${PIDS[@]}"; do
    wait "$PID"
done

echo ""
echo "============================================="
echo "  Campaign Complete"
echo "============================================="

# Count results
TOTAL=0
for OP in "${OPS[@]}"; do
    COUNT=$(ls ${OUT_BASE}/${OP}/*.json 2>/dev/null | wc -l)
    echo "  ${OP}: ${COUNT} results"
    TOTAL=$((TOTAL + COUNT))
done
echo "  Total: ${TOTAL} / 45"

# Run analysis
echo ""
echo "Running analysis..."
python3 v2/analysis/analyze_v2.py --results-dir "$OUT_BASE" 2>&1

# Cleanup
docker compose -f "$COMPOSE_PARALLEL" down >/dev/null 2>&1
echo "Containers stopped."

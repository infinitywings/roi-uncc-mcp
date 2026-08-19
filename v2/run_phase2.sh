#!/usr/bin/env bash
# Run all 9 Phase 2 experiments, restarting the federation between each.
# This works around the HELICS time-sync deadlock after ~430s of sim time.

set -uo pipefail

MCP="http://localhost:5100"
OUT="v2/results/phase2"
LLM_URL="http://cci-siscluster1.charlotte.edu:8000/v1"
LLM_MODEL="cyankiwi/Qwen3.5-122B-A10B-AWQ-4bit"
COMPOSE="v2/docker/docker-compose.yml"

mkdir -p "$OUT"

run_experiment() {
    local SCRIPT="$1"
    local NAME="$2"
    local SEED="$3"
    local EXTRA_ARGS="${4:-}"

    echo ""
    echo "============================================="
    echo "  Experiment: $NAME (seed=$SEED)"
    echo "============================================="

    # Restart federation
    docker compose -f "$COMPOSE" down >/dev/null 2>&1
    docker compose -f "$COMPOSE" up -d >/dev/null 2>&1

    # Wait for health
    for i in $(seq 1 60); do
        if curl -s --connect-timeout 3 "$MCP/health" >/dev/null 2>&1; then
            echo "  Federation ready (attempt $i)"
            break
        fi
        sleep 5
    done

    # Run attacker
    python3 "$SCRIPT" \
        --mcp-url "$MCP" \
        --duration 300 \
        --seed "$SEED" \
        --experiment-name "$NAME" \
        --output-dir "$OUT" \
        $EXTRA_ARGS 2>&1 | grep -E "Starting|ATTACK|Campaign|TVD|ERROR|error"

    local RC=$?
    if [ $RC -eq 0 ]; then
        echo "  ✓ $NAME completed"
    else
        echo "  ✗ $NAME FAILED (exit $RC)"
    fi
}

LLM_ARGS="--llm-url $LLM_URL --llm-model $LLM_MODEL"

echo "=== Phase 2: 9 experiments ==="

for SEED in 1 2 3; do
    run_experiment "v2/attackers/random_baseline.py" "random_5m_s${SEED}" "$SEED"
done

for SEED in 1 2 3; do
    run_experiment "v2/attackers/ai_v1_timing.py" "ai_v1_5m_s${SEED}" "$SEED" "$LLM_ARGS"
done

for SEED in 1 2 3; do
    run_experiment "v2/attackers/ai_v2_strategy.py" "ai_v2_5m_s${SEED}" "$SEED" "$LLM_ARGS"
done

echo ""
echo "=== Phase 2 Complete ==="
echo "Results:"
ls -la "$OUT"/*.json 2>/dev/null | wc -l
echo "files in $OUT/"

# Analyze
python3 v2/analysis/analyze_v2.py --results-dir "$OUT" 2>&1

# Stop federation
docker compose -f "$COMPOSE" down >/dev/null 2>&1

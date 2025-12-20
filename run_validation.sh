#!/usr/bin/env bash
#
# LLM-GridEval Validation Runner
#
# This script runs inside the Docker container to validate the experiment setup.
# It runs short (15-min) random and AI campaigns and compares results.
#
# Usage (from host):
#   docker run -it --rm -p 5100:5100 -v $(pwd):/app roi-img:latest bash /app/run_validation.sh
#
# Or inside container:
#   bash /app/run_validation.sh
#

set -euo pipefail

cd /app

echo "=============================================="
echo "LLM-GridEval Validation Run"
echo "=============================================="
echo ""

# Configuration
MCP_URL="http://localhost:5100"
DURATION=900  # 15 minutes
OUT_DIR="validation_results"
mkdir -p "${OUT_DIR}"

# Step 1: Wait for MCP server to be ready
echo "[1/5] Waiting for MCP server..."
for i in {1..30}; do
    if curl -s "${MCP_URL}/health" > /dev/null 2>&1; then
        echo "  MCP server is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ERROR: MCP server not responding after 30 seconds"
        echo "  Make sure the HELICS co-simulation is running"
        exit 1
    fi
    sleep 1
    echo -n "."
done
echo ""

# Step 2: Check server health
echo "[2/5] Checking server configuration..."
curl -s "${MCP_URL}/health" | python3 -m json.tool
echo ""
curl -s "${MCP_URL}/constraints" | python3 -m json.tool
echo ""

# Step 3: Run random baseline
echo "[3/5] Running random baseline (${DURATION}s)..."
echo "  Start time: $(date)"
python3 llm_grid_eval/scripts/run_random_baseline.py \
    --mcp-url "${MCP_URL}" \
    --duration "${DURATION}" \
    --seed 42 \
    --experiment-name validation_random \
    --output-dir "${OUT_DIR}" 2>&1 | tee "${OUT_DIR}/validation_random.log"
echo "  End time: $(date)"
echo ""

# Brief pause
sleep 5

# Step 4: Run AI campaign
echo "[4/5] Running AI campaign (${DURATION}s)..."
echo "  Start time: $(date)"
python3 llm_grid_eval/scripts/run_ai_campaign.py \
    --mcp-url "${MCP_URL}" \
    --duration "${DURATION}" \
    --controller-interval 30 \
    --seed 42 \
    --experiment-name validation_ai \
    --output-dir "${OUT_DIR}" 2>&1 | tee "${OUT_DIR}/validation_ai.log"
echo "  End time: $(date)"
echo ""

# Step 5: Compare results
echo "[5/5] Analyzing results..."
echo ""
python3 llm_grid_eval/scripts/analyze_results.py \
    --ai "${OUT_DIR}/validation_ai.json" \
    --random "${OUT_DIR}/validation_random.json"

echo ""
echo "=============================================="
echo "Validation Complete!"
echo "=============================================="
echo "Results saved to: ${OUT_DIR}/"
echo ""
echo "Key files:"
echo "  - ${OUT_DIR}/validation_random.json"
echo "  - ${OUT_DIR}/validation_ai.json"
echo "  - ${OUT_DIR}/validation_random.log"
echo "  - ${OUT_DIR}/validation_ai.log"
echo ""

# Quick summary
echo "Quick Summary:"
python3 -c "
import json
from pathlib import Path

ai = json.loads(Path('${OUT_DIR}/validation_ai.json').read_text())
rnd = json.loads(Path('${OUT_DIR}/validation_random.json').read_text())

ai_m = ai.get('final_metrics', {}).get('primary_metrics', {})
rnd_m = rnd.get('final_metrics', {}).get('primary_metrics', {})

ai_tvd = ai_m.get('tvd_sec', 0)
rnd_tvd = rnd_m.get('tvd_sec', 0)
evg = ai_tvd / rnd_tvd if rnd_tvd > 0 else float('inf')

print(f'  Random: TVD={rnd_tvd:.1f}s, attacks={rnd_m.get(\"total_attacks\", 0)}')
print(f'  AI:     TVD={ai_tvd:.1f}s, attacks={ai_m.get(\"total_attacks\", 0)}')
print(f'  EVG:    {evg:.2f}x')
print()
if evg > 1.0:
    print('  ✓ PASS: AI outperformed random baseline')
else:
    print('  ✗ FAIL: AI did not outperform random (check logs)')
"

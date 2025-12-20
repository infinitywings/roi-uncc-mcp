#!/usr/bin/env bash
# Start co-simulation with LLM-GridEval MCP server
# This script installs dependencies and runs the HELICS federation

set -e

echo "=== Installing LLM-GridEval dependencies ==="
pip install --quiet fastapi uvicorn pyyaml httpx openai

echo "=== Starting HELICS co-simulation ==="
cd /app/examples/2bus-13bus
exec helics run --path=gpk-gld-cosim-with-mcp.json

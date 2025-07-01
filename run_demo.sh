#!/bin/bash

# AI-Assisted Grid Penetration Testing Demo Launcher
# ROI UNCC MCP Project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to check running containers
check_running_containers() {
    local running_containers=$(docker ps --filter "name=roi-uncc\|helics-broker\|gridpack-federate\|gridlabd-federate\|mcp-server" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null)
    
    if [[ -n "$running_containers" && "$running_containers" != "NAMES STATUS" ]]; then
        print_warning "Found running containers from previous session:"
        echo "$running_containers"
        print_warning "Consider using --clean flag to clean up before starting"
        return 1
    fi
    return 0
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --config FILE      Configuration file path (default: config/demo_config.yaml)"
    echo "  --mode MODE        Demo mode: ai, random, or comparison"
    echo "  --duration SECS    Attack campaign duration in seconds"
    echo "  --trials NUM       Number of trials for comparison mode"
    echo "  --grid-model MODEL Grid simulation model"
    echo "                     Options: 2bus-13bus, IEEE-39bus, IEEE-118bus"
    echo "  --attack-prompt    Custom attack prompt for AI"
    echo "  --ai-model MODEL   AI model name"
    echo "  --ai-base-url URL  AI API base URL"
    echo "  --ai-api-key KEY   AI API key (optional, uses API.txt if not provided)"
    echo "  --docker          Run in Docker containers (recommended)"
    echo "  --local           Run with local installation"
    echo "  --build           Build Docker images before running"
    echo "  --clean           Clean up existing containers before starting"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Run comparison demo with Docker"
    echo "  $0 --local                      # Run with local installation"
    echo "  $0 --mode ai --duration 120     # Run AI-only demo for 2 minutes"
    echo "  $0 --mode comparison --trials 5 # Run comparison with 5 trials"
    echo "  $0 --docker --build            # Build and run with Docker"
    echo "  $0 --config config/examples/openai_config.yaml # Use OpenAI configuration"
    echo "  $0 --config config/examples/ollama_config.yaml # Use Ollama configuration"
    echo "  $0 --grid-model IEEE-39bus      # Use IEEE 39-bus system"
    echo "  $0 --attack-prompt 'Focus on voltage stability' # Custom attack strategy"
    echo "  $0 --ai-model gpt-4 --ai-base-url https://api.openai.com/v1 --ai-api-key sk-... # Use OpenAI"
    echo ""
    echo "Note: Docker mode is recommended and uses your existing ROI UNCC containers"
}

# Default values
CONFIG_FILE=""
MODE=""
DURATION=""
TRIALS=""
GRID_MODEL=""
ATTACK_PROMPT=""
AI_MODEL=""
AI_BASE_URL=""
AI_API_KEY=""
USE_DOCKER=true  # Default to Docker mode
USE_LOCAL=false
BUILD_DOCKER=false
CLEAN_FIRST=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --trials)
            TRIALS="$2"
            shift 2
            ;;
        --grid-model)
            GRID_MODEL="$2"
            shift 2
            ;;
        --attack-prompt)
            ATTACK_PROMPT="$2"
            shift 2
            ;;
        --ai-model)
            AI_MODEL="$2"
            shift 2
            ;;
        --ai-base-url)
            AI_BASE_URL="$2"
            shift 2
            ;;
        --ai-api-key)
            AI_API_KEY="$2"
            shift 2
            ;;
        --docker)
            USE_DOCKER=true
            USE_LOCAL=false
            shift
            ;;
        --local)
            USE_DOCKER=false
            USE_LOCAL=true
            shift
            ;;
        --build)
            BUILD_DOCKER=true
            shift
            ;;
        --clean)
            CLEAN_FIRST=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate mode
if [[ "$MODE" != "ai" && "$MODE" != "random" && "$MODE" != "comparison" ]]; then
    print_error "Invalid mode: $MODE. Must be ai, random, or comparison"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_status "Starting AI-Assisted Grid Penetration Testing Demo"
if [[ -n "$CONFIG_FILE" ]]; then
    print_status "Configuration: $CONFIG_FILE"
fi
if [[ -n "$MODE" ]]; then
    print_status "Mode: $MODE"
fi
if [[ -n "$DURATION" ]]; then
    print_status "Duration: ${DURATION}s"
fi
if [[ -n "$TRIALS" ]]; then
    print_status "Trials: $TRIALS"
fi
if [[ -n "$GRID_MODEL" ]]; then
    print_status "Grid Model: $GRID_MODEL"
fi
if [[ -n "$ATTACK_PROMPT" ]]; then
    print_status "Attack Prompt: $ATTACK_PROMPT"
fi
if [[ -n "$AI_MODEL" ]]; then
    print_status "AI Model: $AI_MODEL"
fi
if [[ -n "$AI_BASE_URL" ]]; then
    print_status "AI Base URL: $AI_BASE_URL"
fi

# Check if running with Docker
if [[ "$USE_DOCKER" == "true" ]]; then
    print_status "Running demo with Docker containers (recommended)"
    
    # Check for running containers
    if ! check_running_containers && [[ "$CLEAN_FIRST" != "true" ]]; then
        echo
        read -p "Do you want to clean up existing containers? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            CLEAN_FIRST=true
        fi
    fi
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not available. Falling back to local mode."
        USE_DOCKER=false
        USE_LOCAL=true
    fi
    
    if [[ "$USE_DOCKER" == "true" ]]; then
        # Check for base container
        if ! docker images -q roi-uncc-img:latest | grep -q .; then
            print_error "Base container 'roi-uncc-img:latest' not found"
            print_error "Please build it first: cd containers/docker && docker build -t roi-uncc-img:latest ."
            exit 1
        fi
        
        # Clean existing containers if requested
        if [[ "$CLEAN_FIRST" == "true" ]]; then
            print_status "Cleaning up existing containers..."
            docker compose -f docker-compose.demo.yml down -v 2>/dev/null || true
        fi
        
        # Run containerized demo
        print_status "Using containerized demo launcher..."
        CMD="python3 demo_docker.py"
        if [[ -n "$CONFIG_FILE" ]]; then
            CMD="$CMD --config \"$CONFIG_FILE\""
        fi
        if [[ -n "$MODE" ]]; then
            CMD="$CMD --mode \"$MODE\""
        fi
        if [[ -n "$DURATION" ]]; then
            CMD="$CMD --duration \"$DURATION\""
        fi
        if [[ -n "$TRIALS" ]]; then
            CMD="$CMD --trials \"$TRIALS\""
        fi
        if [[ -n "$GRID_MODEL" ]]; then
            CMD="$CMD --grid-model \"$GRID_MODEL\""
        fi
        if [[ -n "$ATTACK_PROMPT" ]]; then
            CMD="$CMD --attack-prompt \"$ATTACK_PROMPT\""
        fi
        if [[ -n "$AI_MODEL" ]]; then
            CMD="$CMD --ai-model \"$AI_MODEL\""
        fi
        if [[ -n "$AI_BASE_URL" ]]; then
            CMD="$CMD --ai-base-url \"$AI_BASE_URL\""
        fi
        if [[ -n "$AI_API_KEY" ]]; then
            CMD="$CMD --ai-api-key \"$AI_API_KEY\""
        fi
        eval $CMD
        
        if [[ $? -eq 0 ]]; then
            print_success "Containerized demo completed successfully"
        else
            print_error "Containerized demo failed"
            exit 1
        fi
    fi
fi

# Run with native Python if not using Docker
if [[ "$USE_LOCAL" == "true" ]]; then
    print_status "Running demo with local installation"
    print_warning "Note: Local mode requires manual setup of HELICS, GridLAB-D, and GridPACK"
    
    # Check dependencies
    print_status "Checking dependencies..."
    
    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not found"
        exit 1
    fi
    
    # Check if HELICS is available
    if ! command -v helics_broker &> /dev/null; then
        print_error "HELICS is required but not found. Please install HELICS first."
        exit 1
    fi
    
    # Check if GridLAB-D is available
    if ! command -v gridlabd &> /dev/null; then
        print_error "GridLAB-D is required but not found. Please install GridLAB-D first."
        exit 1
    fi
    
    # Check if 2bus-13bus example is built
    if [[ ! -f "examples/2bus-13bus/build/gpk-left-fed.x" ]]; then
        print_warning "GridPACK federate not found. Attempting to build..."
        
        cd examples/2bus-13bus
        if [[ -f "build.sh" ]]; then
            chmod +x build.sh
            ./build.sh
        else
            print_error "GridPACK federate not built and no build script found"
            print_error "Please build the GridPACK federate in examples/2bus-13bus/"
            exit 1
        fi
        cd "$SCRIPT_DIR"
    fi
    
    # Install Python requirements
    print_status "Installing Python requirements..."
    pip3 install -r mcp-server/requirements.txt
    
    # Run the demo
    print_status "Launching demo..."
    CMD="python3 demo_launcher.py"
    if [[ -n "$CONFIG_FILE" ]]; then
        CMD="$CMD --config \"$CONFIG_FILE\""
    fi
    if [[ -n "$MODE" ]]; then
        CMD="$CMD --mode \"$MODE\""
    fi
    if [[ -n "$DURATION" ]]; then
        CMD="$CMD --duration \"$DURATION\""
    fi
    if [[ -n "$TRIALS" ]]; then
        CMD="$CMD --trials \"$TRIALS\""
    fi
    if [[ -n "$GRID_MODEL" ]]; then
        CMD="$CMD --grid-model \"$GRID_MODEL\""
    fi
    if [[ -n "$ATTACK_PROMPT" ]]; then
        CMD="$CMD --attack-prompt \"$ATTACK_PROMPT\""
    fi
    if [[ -n "$AI_MODEL" ]]; then
        CMD="$CMD --ai-model \"$AI_MODEL\""
    fi
    if [[ -n "$AI_BASE_URL" ]]; then
        CMD="$CMD --ai-base-url \"$AI_BASE_URL\""
    fi
    if [[ -n "$AI_API_KEY" ]]; then
        CMD="$CMD --ai-api-key \"$AI_API_KEY\""
    fi
    eval $CMD
fi

# Check results
RESULTS_DIR="demo_results"
if [[ -d "$RESULTS_DIR" ]]; then
    print_success "Demo completed successfully!"
    print_status "Results available in: $RESULTS_DIR"
    
    # List result files
    echo ""
    echo "Generated files:"
    ls -la "$RESULTS_DIR"
    
    # Show latest comparison results if available
    LATEST_COMPARISON=$(ls -t "$RESULTS_DIR"/comparison_*.json 2>/dev/null | head -n1)
    if [[ -n "$LATEST_COMPARISON" ]]; then
        echo ""
        print_status "Latest comparison results:"
        python3 -c "
import json
try:
    with open('$LATEST_COMPARISON', 'r') as f:
        data = json.load(f)
    metrics = data.get('comparison_metrics', {})
    print(f'AI mean effectiveness: {metrics.get(\"ai_mean\", 0):.2f}')
    print(f'Random mean effectiveness: {metrics.get(\"random_mean\", 0):.2f}')
    print(f'AI improvement ratio: {metrics.get(\"improvement_ratio\", 0):.2f}x')
    print(f'AI success rate: {metrics.get(\"ai_success_rate\", 0):.2f}')
    print(f'Random success rate: {metrics.get(\"random_success_rate\", 0):.2f}')
except Exception as e:
    print(f'Error reading results: {e}')
"
    fi
else
    print_warning "No results directory found"
fi

echo ""
print_success "Demo launcher finished"
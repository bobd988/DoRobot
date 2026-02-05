#!/bin/bash
#
# VR X5 Robot Data Collection Launcher
#
# This script starts both DORA dataflow and CLI with proper ordering:
# 1. Cleans up stale ZeroMQ socket files
# 2. Starts DORA dataflow in background
# 3. Waits for ZeroMQ sockets to be ready
# 4. Starts CLI in foreground
# 5. Handles cleanup on exit
#
# Usage:
#   bash scripts/run_vr_x5.sh [options]
#
# Options are passed directly to the CLI (main.py)

set -e

# Version
VERSION="1.0.0"

# Configuration
CONDA_ENV="${CONDA_ENV:-dorobot}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DORA_DIR="$PROJECT_ROOT/operating_platform/teleop_vr"

# ZeroMQ socket paths (must match zeromq_sender.py)
SOCKET_IMAGE="/tmp/dora-zeromq-vr-x5-image"
SOCKET_JOINT="/tmp/dora-zeromq-vr-x5-joint"
SOCKET_VR="/tmp/dora-zeromq-vr-x5-vr"
SOCKET_TIMEOUT="${SOCKET_TIMEOUT:-30}"
DORA_INIT_DELAY="${DORA_INIT_DELAY:-5}"
DORA_PID=""
DORA_GRAPH_NAME=""

# Cloud Mode Configuration
# CLOUD modes:
#   0 = Local only (encode locally, no upload)
#   1 = Cloud raw (upload raw images to cloud for encoding)
#   2 = Edge (rsync raw images to edge server)
#   3 = Cloud encoded (encode locally, upload encoded to cloud)
#   4 = Local raw (skip encoding, save raw images locally only)
CLOUD="${CLOUD:-0}"

# Edge Server Configuration (only used when CLOUD=2)
EDGE_SERVER_HOST="${EDGE_SERVER_HOST:-127.0.0.1}"
EDGE_SERVER_USER="${EDGE_SERVER_USER:-dorobot}"
EDGE_SERVER_PASSWORD="${EDGE_SERVER_PASSWORD:-}"
EDGE_SERVER_PORT="${EDGE_SERVER_PORT:-22}"
EDGE_SERVER_PATH="${EDGE_SERVER_PATH:-/uploaded_data}"

# API Server Configuration (for cloud training)
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
API_USERNAME="${API_USERNAME:-}"
API_PASSWORD="${API_PASSWORD:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Initialize conda for this shell
init_conda() {
    # Find conda installation
    if [ -n "$CONDA_EXE" ]; then
        CONDA_BASE="$(dirname "$(dirname "$CONDA_EXE")")"
    elif [ -d "$HOME/miniconda3" ]; then
        CONDA_BASE="$HOME/miniconda3"
    elif [ -d "$HOME/anaconda3" ]; then
        CONDA_BASE="$HOME/anaconda3"
    elif [ -d "/opt/conda" ]; then
        CONDA_BASE="/opt/conda"
    else
        log_error "Cannot find conda installation. Please ensure conda is installed."
        exit 1
    fi

    # Source conda.sh to enable conda activate
    if [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
        source "$CONDA_BASE/etc/profile.d/conda.sh"
    else
        log_error "Cannot find conda.sh at $CONDA_BASE/etc/profile.d/conda.sh"
        exit 1
    fi
}

# Activate the conda environment
activate_env() {
    local env_name="$1"

    # Check if we're already in the target environment
    if [ "$CONDA_DEFAULT_ENV" = "$env_name" ]; then
        log_info "Already in conda environment: $env_name"
        return 0
    fi

    # Check if environment exists (more flexible pattern)
    if ! conda env list | grep -qE "^${env_name}[[:space:]]|[[:space:]]${env_name}[[:space:]]"; then
        log_error "Conda environment '$env_name' does not exist."
        log_error "Please run: bash scripts/setup_env.sh"
        exit 1
    fi

    conda activate "$env_name"
    log_info "Activated conda environment: $env_name"
}

# Cleanup function - called on exit
cleanup() {
    log_step "Cleaning up resources..."

    # Step 1: Stop DORA dataflow
    if [ -n "$DORA_GRAPH_NAME" ]; then
        log_info "Stopping DORA dataflow: $DORA_GRAPH_NAME"
        dora stop "$DORA_GRAPH_NAME" 2>/dev/null || true
        log_info "Waiting for DORA nodes to release devices (3s)..."
        sleep 3
    fi

    # Step 2: Send SIGTERM to processes FIRST and wait for cleanup
    log_info "Signaling VR X5 processes to release resources..."
    pkill -SIGTERM -f "camera_opencv/main.py" 2>/dev/null || true
    pkill -SIGTERM -f "robot_driver_arx_x5.py" 2>/dev/null || true
    pkill -SIGTERM -f "vr_ws_in.py" 2>/dev/null || true
    pkill -SIGTERM -f "zeromq_sender.py" 2>/dev/null || true

    # Wait for processes to handle SIGTERM
    log_info "Waiting for device release (2s)..."
    sleep 2

    # Step 3: Destroy DORA graph
    if [ -n "$DORA_GRAPH_NAME" ]; then
        log_info "Destroying DORA graph: $DORA_GRAPH_NAME"
        dora destroy "$DORA_GRAPH_NAME" 2>/dev/null || true
        sleep 1
    fi

    # Step 4: Kill DORA coordinator process if still running
    if [ -n "$DORA_PID" ] && kill -0 "$DORA_PID" 2>/dev/null; then
        log_info "Stopping DORA process (PID: $DORA_PID)"
        kill -SIGTERM "$DORA_PID" 2>/dev/null || true

        # Wait up to 5 seconds for graceful shutdown
        local wait_count=0
        while kill -0 "$DORA_PID" 2>/dev/null && [ $wait_count -lt 10 ]; do
            sleep 0.5
            wait_count=$((wait_count + 1))
        done

        # Force kill ONLY if still alive after timeout
        if kill -0 "$DORA_PID" 2>/dev/null; then
            log_warn "Force killing DORA process (timeout)..."
            kill -9 "$DORA_PID" 2>/dev/null || true
        fi
        wait "$DORA_PID" 2>/dev/null || true
    fi

    # Step 5: Final cleanup of any remaining processes
    if pgrep -f "camera_opencv/main.py" > /dev/null 2>&1; then
        log_warn "Force killing remaining camera processes..."
        pkill -9 -f "camera_opencv/main.py" 2>/dev/null || true
        sleep 0.5
    fi

    if pgrep -f "robot_driver_arx_x5.py" > /dev/null 2>&1; then
        log_warn "Force killing remaining robot driver processes..."
        pkill -9 -f "robot_driver_arx_x5.py" 2>/dev/null || true
        sleep 0.5
    fi

    # Step 6: Clean up socket files
    rm -f "$SOCKET_IMAGE" "$SOCKET_JOINT" "$SOCKET_VR" 2>/dev/null || true

    log_info "Cleanup complete"
}

# Set up trap for cleanup
trap cleanup EXIT INT TERM

# Clean up stale processes and socket files
cleanup_stale_sockets() {
    log_step "Checking for stale processes and socket files..."

    local found_stale=0

    # Kill stale processes
    if pgrep -f "camera_opencv/main.py" > /dev/null 2>&1; then
        log_warn "Found stale camera processes, sending SIGTERM..."
        pkill -SIGTERM -f "camera_opencv/main.py" 2>/dev/null || true
        found_stale=1
    fi

    if pgrep -f "robot_driver_arx_x5.py" > /dev/null 2>&1; then
        log_warn "Found stale robot driver processes, sending SIGTERM..."
        pkill -SIGTERM -f "robot_driver_arx_x5.py" 2>/dev/null || true
        found_stale=1
    fi

    if pgrep -f "vr_ws_in.py" > /dev/null 2>&1; then
        log_warn "Found stale VR input processes, sending SIGTERM..."
        pkill -SIGTERM -f "vr_ws_in.py" 2>/dev/null || true
        found_stale=1
    fi

    # Wait for graceful cleanup
    if [ $found_stale -eq 1 ]; then
        log_info "Waiting for stale processes to release devices (3s)..."
        sleep 3

        # Force kill any remaining
        pkill -9 -f "camera_opencv/main.py" 2>/dev/null || true
        pkill -9 -f "robot_driver_arx_x5.py" 2>/dev/null || true
        pkill -9 -f "vr_ws_in.py" 2>/dev/null || true
        sleep 1
    fi

    # Kill stale DORA processes
    if pgrep -f "dora-coordinator" > /dev/null 2>&1; then
        log_warn "Found stale DORA coordinator, killing..."
        pkill -SIGTERM -f "dora-coordinator" 2>/dev/null || true
        sleep 2
        pkill -9 -f "dora-coordinator" 2>/dev/null || true
        sleep 1
    fi

    # Remove stale socket files
    rm -f "$SOCKET_IMAGE" "$SOCKET_JOINT" "$SOCKET_VR" 2>/dev/null || true
}

# Wait for ZeroMQ sockets to be created
wait_for_sockets() {
    log_step "Waiting for ZeroMQ sockets to be ready..."

    local elapsed=0
    local poll_interval=0.5

    while [ $elapsed -lt $SOCKET_TIMEOUT ]; do
        # Check if all socket files exist
        if [ -S "$SOCKET_IMAGE" ] && [ -S "$SOCKET_JOINT" ] && [ -S "$SOCKET_VR" ]; then
            log_info "ZeroMQ sockets ready!"
            return 0
        fi

        # Show progress
        printf "\r  Waiting... %ds / %ds" $elapsed $SOCKET_TIMEOUT

        sleep $poll_interval
        elapsed=$((elapsed + 1))
    done

    echo ""
    log_error "Timeout waiting for ZeroMQ sockets after ${SOCKET_TIMEOUT}s"
    log_error "  Expected: $SOCKET_IMAGE"
    log_error "  Expected: $SOCKET_JOINT"
    log_error "  Expected: $SOCKET_VR"
    return 1
}

# Start DORA dataflow
start_dora() {
    log_step "Starting DORA dataflow..."

    # Check if dora command is available
    if ! command -v dora &> /dev/null; then
        log_error "'dora' command not found. Please ensure dora-rs is installed in the '$CONDA_ENV' environment."
        exit 1
    fi

    # Check if dataflow file exists
    local dataflow_file="$DORA_DIR/dora_vr_x5_record.yml"
    if [ ! -f "$dataflow_file" ]; then
        log_error "Dataflow file not found: $dataflow_file"
        exit 1
    fi

    # Start DORA in background
    cd "$DORA_DIR"

    log_info "Running: dora run dora_vr_x5_record.yml"
    dora run dora_vr_x5_record.yml &
    DORA_PID=$!

    # Give DORA a moment to initialize
    sleep 2

    # Check if DORA is still running
    if ! kill -0 "$DORA_PID" 2>/dev/null; then
        log_error "DORA failed to start"
        exit 1
    fi

    log_info "DORA started (PID: $DORA_PID)"

    # Try to get the graph name for cleaner shutdown
    DORA_GRAPH_NAME=$(dora list 2>/dev/null | grep -oP 'dora_vr_x5_record[^\s]*' | head -1) || true

    cd "$PROJECT_ROOT"
}

# Start CLI
start_cli() {
    log_step "Starting CLI..."

    # Default parameters
    local repo_id="${REPO_ID:-vr-x5-dataset}"
    local single_task="${SINGLE_TASK:-VR遥操ARX-X5机械臂}"

    log_info "Running main.py with parameters:"
    log_info "  repo_id: $repo_id"
    log_info "  single_task: $single_task"
    log_info "  cloud_offload: $CLOUD"

    # Export environment variables
    export EDGE_SERVER_HOST
    export EDGE_SERVER_USER
    export EDGE_SERVER_PASSWORD
    export EDGE_SERVER_PORT
    export EDGE_SERVER_PATH
    export API_BASE_URL
    export API_USERNAME
    export API_PASSWORD

    # Build command arguments
    local cmd_args=(
        --robot.type=vr_x5
        --record.repo_id="$repo_id"
        --record.single_task="$single_task"
        --record.cloud_offload=$CLOUD
    )

    # Start CLI in foreground (blocks until exit)
    python "$PROJECT_ROOT/operating_platform/core/main.py" \
        "${cmd_args[@]}" \
        "$@"
}

# Print usage
print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "VR X5 Robot Data Collection Launcher"
    echo ""
    echo "Environment Variables:"
    echo "  CONDA_ENV           Conda environment name (default: dorobot)"
    echo "  REPO_ID             Dataset repository ID (default: vr-x5-dataset)"
    echo "  SINGLE_TASK         Task description (default: 'VR遥操ARX-X5机械臂')"
    echo "  CLOUD               Offload mode (default: 0):"
    echo "                        0 = Local only (encode videos locally, no upload)"
    echo "                        1 = Cloud raw (upload raw images to cloud)"
    echo "                        2 = Edge mode (rsync to edge server)"
    echo "                        3 = Cloud encoded (encode locally, upload to cloud)"
    echo "                        4 = Local raw (skip encoding, save raw locally)"
    echo ""
    echo "Examples:"
    echo "  $0                              # Default: local mode"
    echo "  REPO_ID=my-dataset $0           # Custom dataset name"
    echo "  CLOUD=2 $0                      # Edge mode"
    echo ""
    echo "Controls:"
    echo "  's'     - Save episode and start new one"
    echo "  'n'     - Proceed after environment reset"
    echo "  'e'     - Stop recording and exit"
    echo "  Ctrl+C  - Emergency stop"
}

# Main entry point
main() {
    # Handle help flag
    if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        print_usage
        exit 0
    fi

    echo ""
    echo "=========================================="
    echo "  VR X5 Robot Data Collection Launcher"
    echo "  Version: $VERSION"
    echo "=========================================="
    echo ""

    # Step 0: Initialize and activate conda environment
    log_step "Initializing conda environment..."
    init_conda
    activate_env "$CONDA_ENV"

    # Step 1: Clean up stale sockets
    cleanup_stale_sockets

    # Step 2: Start DORA
    start_dora

    # Step 3: Wait for sockets
    if ! wait_for_sockets; then
        log_error "Failed to initialize. Check DORA logs for errors."
        exit 1
    fi

    # Step 3.5: Wait for DORA to fully initialize
    log_step "Waiting ${DORA_INIT_DELAY}s for DORA nodes to fully initialize..."
    for i in $(seq $DORA_INIT_DELAY -1 1); do
        printf "\r  Initializing... %ds remaining" $i
        sleep 1
    done
    echo ""

    echo ""
    log_info "All systems ready!"
    echo ""
    echo "=========================================="
    echo "  Controls:"
    echo "    's'     - Save episode and start new one"
    echo "    'n'     - Proceed after environment reset"
    echo "    'e'     - Stop recording and exit"
    echo "    Ctrl+C  - Emergency stop"
    echo "=========================================="
    echo ""

    # Step 4: Start CLI (blocks until exit)
    start_cli "$@"

    log_info "Recording session ended"
}

# Run main
main "$@"

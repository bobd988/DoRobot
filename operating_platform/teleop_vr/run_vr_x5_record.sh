#!/bin/bash
#
# VR遥操ARX-X5数据录制启动脚本
# 功能：VR控制ARX-X5 + 奥比中光相机 + DoRobot格式数据保存
#

set -e

VERSION="1.0.0"

# ========== 配置 ==========
CONDA_ENV="${CONDA_ENV:-dorobot}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 数据保存配置
REPO_ID="${REPO_ID:-vr-x5-dataset}"
SINGLE_TASK="${SINGLE_TASK:-VR遥操ARX-X5机械臂}"

# DORA相关
DORA_PID=""
DORA_GRAPH_NAME=""
DORA_INIT_DELAY=5

# ZeroMQ socket配置
SOCKET_IMAGE="/tmp/dora-zeromq-vr-x5-image"
SOCKET_JOINT="/tmp/dora-zeromq-vr-x5-joint"
SOCKET_VR="/tmp/dora-zeromq-vr-x5-vr"
SOCKET_TIMEOUT=30

# ========== 颜色 ==========
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ========== 日志函数 ==========
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

# ========== 清理函数 ==========
cleanup() {
    log_step "Cleaning up..."

    # 停止DORA
    if [ -n "$DORA_GRAPH_NAME" ]; then
        log_info "Stopping DORA dataflow: $DORA_GRAPH_NAME"
        dora stop "$DORA_GRAPH_NAME" 2>/dev/null || true
        sleep 1
        dora destroy "$DORA_GRAPH_NAME" 2>/dev/null || true
    fi

    # 停止DORA进程
    if [ -n "$DORA_PID" ] && kill -0 "$DORA_PID" 2>/dev/null; then
        log_info "Stopping DORA process (PID: $DORA_PID)"
        kill -SIGTERM "$DORA_PID" 2>/dev/null || true
        sleep 1
    fi

    # 强制清理所有相关Python进程
    log_info "Killing all VR recording processes..."

    # 列出所有需要清理的进程
    local processes=(
        "arm_to_jointcmd_ik.py"
        "command_mux.py"
        "data_recorder.py"
        "vr_ws_in.py"
        "robot_driver_arx_x5.py"
        "camera_opencv/main.py"
        "tick.py"
        "vr_monitor.py"
        "zeromq_sender.py"
    )

    # 先尝试优雅关闭（SIGTERM）
    for proc in "${processes[@]}"; do
        if pgrep -f "$proc" > /dev/null 2>&1; then
            pkill -SIGTERM -f "$proc" 2>/dev/null || true
        fi
    done

    # 等待进程退出
    sleep 2

    # 强制杀死仍在运行的进程（SIGKILL）
    for proc in "${processes[@]}"; do
        if pgrep -f "$proc" > /dev/null 2>&1; then
            log_warn "Force killing: $proc"
            pkill -9 -f "$proc" 2>/dev/null || true
        fi
    done

    # 清理DORA相关进程
    pkill -9 -f "dora_vr_x5_record.yml" 2>/dev/null || true

    # 清理摄像头显示进程
    pkill -9 -f "camera_viewer.py" 2>/dev/null || true

    # 清理ZeroMQ socket文件
    rm -f "$SOCKET_IMAGE" "$SOCKET_JOINT" "$SOCKET_VR" 2>/dev/null || true

    # 最后验证
    sleep 1
    local remaining=$(ps aux | grep -E "(arm_to_jointcmd|command_mux|data_recorder|vr_ws_in|robot_driver)" | grep -v grep | wc -l)
    if [ "$remaining" -gt 0 ]; then
        log_warn "Warning: $remaining processes still running"
    else
        log_info "All processes cleaned up successfully"
    fi

    log_info "Cleanup complete"
}

trap cleanup EXIT INT TERM

# ========== 清理旧socket ==========
cleanup_stale() {
    log_step "Cleaning stale processes..."

    # 列出所有需要清理的进程
    local processes=(
        "dora_vr_x5_record.yml"
        "arm_to_jointcmd_ik.py"
        "command_mux.py"
        "data_recorder.py"
        "vr_ws_in.py"
        "robot_driver_arx_x5.py"
        "camera_opencv/main.py"
        "tick.py"
        "vr_monitor.py"
        "zeromq_sender.py"
    )

    local found_stale=false

    # 检查是否有旧进程
    for proc in "${processes[@]}"; do
        if pgrep -f "$proc" > /dev/null 2>&1; then
            found_stale=true
            break
        fi
    done

    if [ "$found_stale" = true ]; then
        log_warn "Found stale processes, killing..."

        # 先尝试优雅关闭（SIGTERM）
        for proc in "${processes[@]}"; do
            pkill -SIGTERM -f "$proc" 2>/dev/null || true
        done

        sleep 2

        # 强制杀死仍在运行的进程（SIGKILL）
        for proc in "${processes[@]}"; do
            if pgrep -f "$proc" > /dev/null 2>&1; then
                pkill -9 -f "$proc" 2>/dev/null || true
            fi
        done

        sleep 1
        log_info "Stale processes cleaned"
    else
        log_info "No stale processes found"
    fi
}

# ========== 等待socket就绪 ==========
wait_for_sockets() {
    log_step "Waiting for ZeroMQ sockets..."

    local elapsed=0
    while [ $elapsed -lt $SOCKET_TIMEOUT ]; do
        if [ -S "$SOCKET_IMAGE" ] && [ -S "$SOCKET_JOINT" ] && [ -S "$SOCKET_VR" ]; then
            log_info "ZeroMQ sockets ready!"
            return 0
        fi

        printf "\r  Waiting... %ds / %ds" $elapsed $SOCKET_TIMEOUT
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo ""
    log_error "Timeout waiting for ZeroMQ sockets after ${SOCKET_TIMEOUT}s"
    log_error "  Expected: $SOCKET_IMAGE"
    log_error "  Expected: $SOCKET_JOINT"
    log_error "  Expected: $SOCKET_VR"
    return 1
}

# ========== 启动DORA ==========
start_dora() {
    log_step "Starting DORA dataflow..."

    # 检查dora命令
    if ! command -v dora &> /dev/null; then
        log_error "'dora' command not found"
        log_error "Please ensure dora-rs is installed in the '$CONDA_ENV' environment"
        exit 1
    fi

    # 检查配置文件
    local dataflow_file="$SCRIPT_DIR/dora_vr_x5_record.yml"
    if [ ! -f "$dataflow_file" ]; then
        log_error "Dataflow file not found: $dataflow_file"
        exit 1
    fi

    # 启动DORA
    cd "$SCRIPT_DIR"
    log_info "Running: dora run dora_vr_x5_record.yml"
    dora run dora_vr_x5_record.yml &
    DORA_PID=$!

    sleep 2

    # 检查DORA是否运行
    if ! kill -0 "$DORA_PID" 2>/dev/null; then
        log_error "DORA failed to start"
        exit 1
    fi

    log_info "DORA started (PID: $DORA_PID)"

    # 获取graph名称
    DORA_GRAPH_NAME=$(dora list 2>/dev/null | grep -oP 'dora_vr_x5_record[^\s]*' | head -1) || true

    cd "$PROJECT_ROOT"
}

# ========== 启动摄像头显示 ==========
start_camera_viewer() {
    log_step "Starting camera viewer..."

    # 导出socket路径
    export SOCKET_IMAGE
    export SOCKET_JOINT
    export SOCKET_VR

    # 在后台启动摄像头显示（使用dorobot虚拟环境）
    cd "$SCRIPT_DIR"
    /home/dora/miniconda3/envs/dorobot/bin/python3 camera_viewer.py &
    CAMERA_VIEWER_PID=$!

    log_info "Camera viewer started (PID: $CAMERA_VIEWER_PID)"
    cd "$PROJECT_ROOT"
}

# ========== 启动CLI ==========
start_cli() {
    log_step "Data recording started..."

    log_info "Recording parameters:"
    log_info "  repo_id: $REPO_ID"
    log_info "  single_task: $SINGLE_TASK"

    echo ""
    log_info "System is running. Data will be saved automatically."
    log_info "Press Ctrl+C to stop."
    echo ""

    # 等待用户中断
    wait
}

# ========== 打印使用说明 ==========
print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "VR遥操ARX-X5数据录制系统"
    echo ""
    echo "Environment Variables:"
    echo "  CONDA_ENV           Conda environment name (default: dorobot)"
    echo "  REPO_ID             Dataset repository ID (default: vr-x5-dataset)"
    echo "  SINGLE_TASK         Task description (default: 'VR遥操ARX-X5机械臂')"
    echo "  CLOUD               Cloud offload mode (default: 0)"
    echo "                        0 = Local only (encode locally, no upload)"
    echo "                        1 = Cloud raw (upload raw images to cloud)"
    echo "                        2 = Edge mode (rsync to edge server)"
    echo "                        3 = Cloud encoded (encode locally, upload to cloud)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Default: local mode"
    echo "  REPO_ID=my-dataset $0                 # Custom dataset name"
    echo "  SINGLE_TASK=\"抓取苹果\" $0            # Custom task description"
    echo "  CLOUD=2 $0                            # Edge mode"
    echo ""
    echo "Controls:"
    echo "  'n'     - Save episode and start new one"
    echo "  'e'     - Stop recording and exit"
    echo "  Ctrl+C  - Emergency stop"
}

# ========== 主函数 ==========
main() {
    # 处理帮助参数
    if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        print_usage
        exit 0
    fi

    echo ""
    echo "=========================================="
    echo "  VR遥操ARX-X5数据录制系统"
    echo "  Version: $VERSION"
    echo "=========================================="
    echo ""

    # 激活conda环境
    log_step "Initializing conda environment..."

    # 直接使用miniconda3（dorobot环境在这里）
    CONDA_BASE="$HOME/miniconda3"

    if [ ! -d "$CONDA_BASE" ]; then
        log_error "Cannot find miniconda3 at $CONDA_BASE"
        exit 1
    fi

    # 激活conda
    if [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
        source "$CONDA_BASE/etc/profile.d/conda.sh"
    else
        log_error "Cannot find conda.sh"
        exit 1
    fi

    # 检查环境是否存在
    if ! conda env list | grep -q "${CONDA_ENV}"; then
        log_error "Conda environment '$CONDA_ENV' does not exist"
        log_error "Please run: bash scripts/setup_env.sh"
        exit 1
    fi

    conda activate "$CONDA_ENV"
    log_info "Activated conda environment: $CONDA_ENV"

    # 清理旧进程
    cleanup_stale

    # 检查并清理端口占用
    log_step "Checking port availability..."
    if lsof -i :8442 > /dev/null 2>&1; then
        log_warn "Port 8442 is in use, killing process..."
        lsof -ti :8442 | xargs -r kill -9 2>/dev/null || true
        sleep 1
    fi
    if lsof -i :8443 > /dev/null 2>&1; then
        log_warn "Port 8443 is in use, killing process..."
        lsof -ti :8443 | xargs -r kill -9 2>/dev/null || true
        sleep 1
    fi
    log_info "Ports 8442 and 8443 are available"

    # 检查相机
    log_step "Checking camera..."
    if [ ! -e "/dev/video4" ]; then
        log_error "Camera not found at /dev/video4"
        log_error "Please check if Orbbec Dabai DC1 is connected"
        exit 1
    fi
    log_info "Camera found: /dev/video4"

    # 检查CAN接口
    log_step "Checking CAN interface..."
    if ! ip link show can0 &> /dev/null; then
        log_error "CAN interface 'can0' not found"
        log_error "Please check if ARX-X5 is connected and CAN is configured"
        exit 1
    fi
    log_info "CAN interface found: can0"

    # 启动DORA
    start_dora

    # 等待ZeroMQ sockets就绪
    if ! wait_for_sockets; then
        log_error "Failed to initialize ZeroMQ sockets"
        exit 1
    fi

    # 启动摄像头显示
    start_camera_viewer

    # 等待DORA完全初始化
    log_step "Waiting for DORA to fully initialize (${DORA_INIT_DELAY}s)..."
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
    echo "    VR握把  - 按下开始录制，松开暂停"
    echo "    'q'     - 关闭摄像头显示窗口"
    echo "    Ctrl+C  - 停止并保存数据"
    echo ""
    echo "  Data will be saved to:"
    echo "    ./dataset/$REPO_ID/"
    echo "  Camera display:"
    echo "    实时摄像头画面已打开"
    echo "=========================================="
    echo ""

    # 启动CLI（实际上只是等待）
    start_cli "$@"

    log_info "Recording session ended"
}

# 运行主函数
main "$@"

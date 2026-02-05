#!/bin/bash
# 主臂-从臂遥操启动脚本（基于DORA）
# Leader: Feetech STS3215 on /dev/ttyACM1
# Follower: ARX X5 on can0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=========================================="
echo "主臂-从臂遥操启动"
echo "=========================================="
echo ""

# 1. 配置CAN
log_info "[1/4] 配置CAN接口..."
# 检查CAN是否已经配置
if ip link show can0 &> /dev/null && ip link show can0 | grep -q "UP"; then
    log_info "✓ CAN接口已配置"
else
    log_warn "CAN接口未配置，尝试配置..."
    cd /home/dora/DoRobot-before/ARX_X5
    ./setup_can.sh
    if [ $? -ne 0 ]; then
        log_error "CAN配置失败，请手动运行: sudo /home/dora/DoRobot-before/ARX_X5/setup_can.sh"
        exit 1
    fi
    log_info "✓ CAN配置成功"
fi
echo ""

# 2. 检查设备
log_info "[2/4] 检查设备..."
log_info "  - 检查主臂 (/dev/ttyACM1)..."
if [ ! -e /dev/ttyACM1 ]; then
    log_error "主臂设备不存在: /dev/ttyACM1"
    exit 1
fi
log_info "  ✓ 主臂设备存在"

log_info "  - 检查CAN接口 (can0)..."
if ! ip link show can0 &> /dev/null; then
    log_error "CAN接口不存在: can0"
    exit 1
fi
log_info "  ✓ CAN接口存在"
echo ""

# 3. 设置权限
log_info "[3/4] 设置设备权限..."
sudo chmod 777 /dev/ttyACM1 2>/dev/null && \
    log_info "  ✓ 主臂权限已设置" || \
    log_warn "  无法设置主臂权限"
echo ""

# 4. 启动DORA dataflow
log_info "[4/4] 启动DORA dataflow..."
cd "$SCRIPT_DIR"

# 激活conda环境
source ~/miniconda3/bin/activate dorobot

log_info "运行: dora run dora_leader_follower_x5.yml"
echo ""
echo "=========================================="
echo "  提示:"
echo "    - 移动主臂，从臂会跟随"
echo "    - 按 Ctrl+C 停止"
echo "=========================================="
echo ""

dora run dora_leader_follower_x5.yml

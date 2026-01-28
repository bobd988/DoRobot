#!/bin/bash
# VR 模块停止脚本
# 位置: /home/demo/Public/DoRobot/operating_platform/teleop_vr/stop_vr.sh

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}DoRobot VR 远程操控系统停止脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${YELLOW}正在查找运行中的 VR 数据流...${NC}"

# 查找包含 vr_teleoperate 的数据流
DATAFLOWS=$(dora list 2>/dev/null | grep -i "vr_teleoperate" | awk '{print $1}' || true)

if [ -z "$DATAFLOWS" ]; then
    echo -e "${YELLOW}未找到运行中的 VR 数据流${NC}"
    echo ""
    echo -e "${YELLOW}当前运行的数据流:${NC}"
    dora list
else
    echo -e "${GREEN}找到以下 VR 数据流:${NC}"
    echo "$DATAFLOWS"
    echo ""

    for UUID in $DATAFLOWS; do
        echo -e "${YELLOW}正在停止数据流: ${UUID}${NC}"
        dora stop "$UUID"
        echo -e "${GREEN}✓ 数据流已停止${NC}"
    done
fi

echo ""
echo -e "${YELLOW}是否要停止所有数据流并关闭 Dora 守护进程? (y/N)${NC}"
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${YELLOW}正在停止所有数据流...${NC}"
    dora destroy
    echo -e "${GREEN}✓ 所有数据流已停止${NC}"
else
    echo -e "${YELLOW}保持 Dora 守护进程运行${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VR 系统已停止${NC}"
echo -e "${GREEN}========================================${NC}"

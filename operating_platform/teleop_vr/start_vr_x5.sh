#!/bin/bash
# VR X5 模块快速启动脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}DoRobot VR X5 远程操控系统启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查当前目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}[1/5] 设置 X5 SDK 环境变量...${NC}"

# X5 SDK 路径
X5_SDK_PATH="/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"

# 设置 LD_LIBRARY_PATH
export LD_LIBRARY_PATH="${X5_SDK_PATH}/bimanual/api/arx_x5_src:${X5_SDK_PATH}/bimanual/api:/usr/local/lib:$LD_LIBRARY_PATH"

# 设置 PYTHONPATH
export PYTHONPATH="${X5_SDK_PATH}/bimanual/api:${X5_SDK_PATH}/bimanual/api/arx_x5_python:$PYTHONPATH"

echo -e "${GREEN}✓ 环境变量已设置${NC}"
echo -e "  LD_LIBRARY_PATH: ${LD_LIBRARY_PATH:0:100}..."
echo -e "  PYTHONPATH: ${PYTHONPATH:0:100}..."

echo ""
echo -e "${YELLOW}[2/5] 检查环境...${NC}"

# 检查 SSL 证书
if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    echo -e "${RED}错误: 未找到 SSL 证书文件${NC}"
    echo -e "${YELLOW}正在生成自签名证书...${NC}"
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
        -subj "/C=CN/ST=State/L=City/O=Organization/CN=localhost"
    echo -e "${GREEN}✓ SSL 证书生成完成${NC}"
else
    echo -e "${GREEN}✓ SSL 证书已存在${NC}"
fi

# 检查 CAN 接口
if ! ip link show can0 &>/dev/null; then
    echo -e "${YELLOW}警告: 未检测到 CAN 接口 (can0)${NC}"
    echo -e "${YELLOW}系统将启动，但无法控制真实硬件${NC}"
    echo -e "${YELLOW}如需使用真实硬件，请配置 CAN 接口后重启${NC}"
else
    echo -e "${GREEN}✓ CAN 接口已配置${NC}"
fi

echo ""
echo -e "${YELLOW}[3/5] 启动 Dora 守护进程...${NC}"
dora up
echo -e "${GREEN}✓ Dora 守护进程已启动${NC}"

echo ""
echo -e "${YELLOW}[4/5] 启动 VR X5 数据流...${NC}"
dora start dora_vr_x5.yml

echo ""
echo -e "${YELLOW}[5/5] 获取系统信息...${NC}"
sleep 2

# 获取本机 IP 地址
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VR X5 系统启动成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}访问方式:${NC}"
echo -e "  在 Meta Quest 浏览器中访问:"
echo -e "  ${GREEN}https://${IP_ADDR}:8443${NC}"
echo ""
echo -e "${YELLOW}使用说明:${NC}"
echo -e "  1. 接受自签名证书警告"
echo -e "  2. 点击页面上的 VR 图标进入 VR 模式"
echo -e "  3. 使用左手柄控制机械臂:"
echo -e "     - 握把按钮 (Grip): 按住启用控制"
echo -e "     - 扳机键 (Trigger): 控制夹爪开合"
echo ""
echo -e "${YELLOW}查看日志:${NC}"
echo -e "  dora list                    # 查看运行中的数据流"
echo -e "  dora logs <dataflow-uuid>    # 查看所有日志"
echo -e "  dora logs vr_monitor --follow  # 实时监控VR数据流"
echo ""
echo -e "${YELLOW}停止系统:${NC}"
echo -e "  dora stop <dataflow-uuid>    # 停止指定数据流"
echo -e "  dora destroy                 # 停止所有数据流"
echo ""
echo -e "${GREEN}========================================${NC}"

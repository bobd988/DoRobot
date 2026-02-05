#!/bin/bash
# 快速修复摄像头连接问题

set -e

echo "=========================================="
echo "摄像头连接问题快速修复脚本"
echo "=========================================="
echo ""

echo "[1/6] 停止 DORA 数据流..."
dora stop 2>/dev/null || true
pkill -f "dora" 2>/dev/null || true
sleep 2

echo "[2/6] 清理 ZeroMQ socket..."
rm -f /tmp/dora-zeromq-* 2>/dev/null || true

echo "[3/6] 检查摄像头连接..."
echo ""
rs-enumerate-devices 2>/dev/null | grep -E "(Device info|Serial Number)" || {
    echo "❌ 错误: 无法检测到 RealSense 摄像头"
    echo "请检查:"
    echo "  1. USB 连接是否正常"
    echo "  2. 摄像头是否上电"
    echo "  3. 运行 'rs-enumerate-devices' 查看详细信息"
    exit 1
}
echo ""

echo "[4/6] 重新启动 DORA 数据流..."
cd /home/dora/DoRobot-vr/operating_platform/teleop_vr
dora start dora_leader_follower_x5.yml

echo "[5/6] 等待节点启动 (10秒)..."
for i in {10..1}; do
    echo -ne "\r  剩余 $i 秒...  "
    sleep 1
done
echo ""

echo "[6/6] 检查节点状态..."
echo ""
dora list

echo ""
echo "=========================================="
echo "✓ 修复完成！"
echo "=========================================="
echo ""
echo "现在可以启动数据录制了。"
echo ""
echo "如果仍然有问题，请运行:"
echo "  python3 diagnose_camera_connection.py"
echo ""

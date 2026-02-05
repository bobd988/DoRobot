#!/bin/bash
# 向运行中的 DoRobot 系统发送命令

case "$1" in
    s|save)
        touch /tmp/dorobot_save
        echo "✓ 发送保存命令 (save episode)"
        ;;
    n|next)
        touch /tmp/dorobot_next
        echo "✓ 发送下一个命令 (next episode)"
        ;;
    e|exit)
        touch /tmp/dorobot_exit
        echo "✓ 发送退出命令 (exit)"
        ;;
    *)
        echo "用法: $0 {s|save|n|next|e|exit}"
        echo ""
        echo "命令说明:"
        echo "  s, save  - 保存当前 episode"
        echo "  n, next  - 继续下一个 episode"
        echo "  e, exit  - 退出并保存所有数据"
        exit 1
        ;;
esac

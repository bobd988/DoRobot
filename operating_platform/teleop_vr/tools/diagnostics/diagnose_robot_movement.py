#!/usr/bin/env python3
"""
诊断脚本：检查机械臂为什么在 VR 未连接时移动
"""

import sys
import os
import time

# 设置环境变量
sdk_path = "/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"
sys.path.insert(0, sdk_path)

lib_paths = [
    f"{sdk_path}/bimanual/api/arx_x5_src",
    f"{sdk_path}/bimanual/api",
    "/usr/local/lib"
]
os.environ['LD_LIBRARY_PATH'] = ":".join(lib_paths)

from bimanual import SingleArm
import numpy as np

print("="*70)
print("机械臂状态诊断")
print("="*70)

arm_config = {
    "can_port": "can0",
    "type": 0,
    "num_joints": 6,
    "dt": 0.05
}

try:
    print("\n正在连接机械臂...")
    arm = SingleArm(arm_config)
    time.sleep(2)

    print("\n读取当前关节位置...")
    for i in range(5):
        joints_rad = arm.get_joint_positions()
        joints_deg = np.rad2deg(joints_rad)

        print(f"\n时刻 {i+1}:")
        print(f"  关节位置（度）:")
        for j, deg in enumerate(joints_deg[:6]):
            print(f"    关节{j+1}: {deg:7.2f}°")

        time.sleep(1)

    print("\n" + "="*70)
    print("诊断完成")
    print("="*70)
    print("\n如果关节位置在变化，说明有其他程序在控制机械臂。")
    print("如果关节位置不变，说明机械臂没有移动。")

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()

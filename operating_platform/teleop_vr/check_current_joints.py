#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查机械臂当前关节位置"""

import sys
import os
import time
import numpy as np

# 设置环境变量（与 start_vr_x5.sh 相同）
sdk_path = "/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"
sys.path.insert(0, sdk_path)

lib_paths = [
    f"{sdk_path}/bimanual/api/arx_x5_src",
    f"{sdk_path}/bimanual/api",
    f"{sdk_path}/bimanual/lib/arx_x5_src",
    f"{sdk_path}/bimanual/lib",
    "/opt/ros/noetic/lib",
    "/opt/ros/humble/lib",
    "/usr/local/lib"
]
os.environ['LD_LIBRARY_PATH'] = ":".join(lib_paths)
os.environ['PYTHONPATH'] = f"{sdk_path}/bimanual/api:{sdk_path}/bimanual/api/arx_x5_python"

from bimanual import SingleArm

def main():
    arm_config = {
        "can_port": "can0",
        "type": 0,
        "num_joints": 6,
        "dt": 0.05
    }

    try:
        print("正在连接机械臂...")
        arm = SingleArm(arm_config)
        time.sleep(2)

        joints_rad = arm.get_joint_positions()
        joints_deg = np.rad2deg(joints_rad)

        print("\n" + "="*60)
        print("机械臂当前姿态")
        print("="*60)
        print(f"\n关节位置（弧度）:")
        print(f"  {joints_rad}")

        print(f"\n关节位置（度）:")
        for i, deg in enumerate(joints_deg):
            print(f"  关节{i+1}: {deg:7.2f}°")

        print("\n" + "="*60)
        print("建议修改 arm_to_jointcmd_ik.py 中的 rest 姿态为:")
        print("="*60)
        print(f"rest = {list(joints_rad)}")
        print("\n这样可以防止机械臂在启动时移动")
        print("="*60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

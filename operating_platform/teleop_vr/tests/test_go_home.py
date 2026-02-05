#!/usr/bin/env python3
"""
测试机械臂回零功能
"""
import sys
import os
import time

sdk_path = "/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"
sys.path.insert(0, sdk_path)

lib_paths = [
    f"{sdk_path}/bimanual/api/arx_x5_src",
    f"{sdk_path}/bimanual/api",
    f"{sdk_path}/bimanual/lib/arx_x5_src",
    f"{sdk_path}/bimanual/lib",
    "/usr/local/lib"
]
os.environ['LD_LIBRARY_PATH'] = ":".join(lib_paths)

from bimanual import SingleArm

print("=" * 60)
print("测试机械臂回零功能")
print("=" * 60)

arm_config = {
    "can_port": "can0",
    "type": 0,
    "num_joints": 6,
    "dt": 0.05
}

arm = SingleArm(arm_config)
print("\n✓ 机械臂初始化完成")

time.sleep(2)

print("\n读取初始关节位置...")
joints_before = arm.get_joint_positions()
print(f"初始位置: {[f'{j:.3f}' for j in joints_before]}")

print("\n调用 go_home() 回零...")
try:
    arm.go_home()
    print("✓ go_home() 调用成功")

    print("\n等待5秒让机械臂运动...")
    time.sleep(5)

    print("\n读取回零后的关节位置...")
    joints_after = arm.get_joint_positions()
    print(f"回零后位置: {[f'{j:.3f}' for j in joints_after]}")

    # 检查是否有变化
    changed = any(abs(joints_after[i] - joints_before[i]) > 0.01 for i in range(len(joints_before)))

    if changed:
        print("\n✅ 机械臂已运动，通信正常！")
    else:
        print("\n⚠️  关节位置未变化，可能:")
        print("  1. 机械臂已经在零点位置")
        print("  2. 电机未响应命令")

except Exception as e:
    print(f"\n✗ go_home() 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

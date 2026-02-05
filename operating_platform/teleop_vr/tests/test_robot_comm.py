#!/usr/bin/env python3
"""
简单的机械臂通信测试
"""
import sys
import os
import time

# SDK路径配置（与robot_driver_arx_x5.py相同）
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

print("=" * 60)
print("ARX X5 通信测试")
print("=" * 60)

try:
    print("\n[1/3] 导入SDK...")
    from bimanual import SingleArm
    print("✓ SDK导入成功")

    print("\n[2/3] 初始化机械臂...")
    arm_config = {
        "can_port": "can0",
        "type": 0,
        "num_joints": 6,
        "dt": 0.05
    }

    arm = SingleArm(arm_config)
    print("✓ 机械臂对象创建成功")

    time.sleep(2)

    print("\n[3/3] 读取关节位置...")
    try:
        joints = arm.get_joint_positions()
        print(f"✓ 成功读取关节位置:")
        for i, angle in enumerate(joints):
            print(f"  关节{i+1}: {angle:.4f} rad ({angle*57.3:.1f}°)")

        print("\n" + "=" * 60)
        print("✅ 通信测试成功！机械臂连接正常。")
        print("=" * 60)

    except Exception as e:
        print(f"✗ 读取关节位置失败: {e}")
        print("\n可能原因:")
        print("  1. 电机未上电")
        print("  2. CAN线未连接")
        print("  3. 电机处于错误状态")
        sys.exit(1)

except Exception as e:
    print(f"✗ 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

#!/usr/bin/env python3
"""
测试IK_HOME_POS=(0,0,0)是否可达
"""
import pybullet as pb
import pybullet_data

# 初始化PyBullet
pb.connect(pb.DIRECT)
pb.setAdditionalSearchPath(pybullet_data.getDataPath())

# 加载URDF
urdf_path = "/home/dora/DoRobot/operating_platform/teleop_vr/x5_kinematics_only.urdf"
body = pb.loadURDF(urdf_path, useFixedBase=True)

# 找到末端执行器
ee_idx = -1
for i in range(pb.getNumJoints(body)):
    info = pb.getJointInfo(body, i)
    if info[12].decode('utf-8') == "link6":
        ee_idx = i
        break

# 测试位置 (0, 0, 0)
target_pos = [0.0, 0.0, 0.0]
print(f"测试目标位置: {target_pos}")

try:
    # 尝试IK求解
    sol = pb.calculateInverseKinematics(
        bodyUniqueId=body,
        endEffectorLinkIndex=ee_idx,
        targetPosition=target_pos,
        maxNumIterations=100,
        residualThreshold=1e-4
    )

    print(f"\nIK求解结果（弧度）:")
    for i in range(6):
        print(f"  Joint {i+1}: {sol[i]:.4f} rad ({sol[i]*57.3:.1f}°)")

    # 验证：设置这些关节角度，看实际到达的位置
    for i in range(6):
        pb.resetJointState(body, i, sol[i])

    ls = pb.getLinkState(body, ee_idx)
    actual_pos = ls[0]

    print(f"\n实际到达位置: ({actual_pos[0]:.4f}, {actual_pos[1]:.4f}, {actual_pos[2]:.4f})")

    error = ((actual_pos[0]-target_pos[0])**2 +
             (actual_pos[1]-target_pos[1])**2 +
             (actual_pos[2]-target_pos[2])**2)**0.5

    print(f"位置误差: {error:.4f} 米")

    if error > 0.01:
        print("\n⚠️ 警告: 位置(0,0,0)无法精确到达！")
        print("这个位置在机械臂的工作空间之外或接近奇异点。")
    else:
        print("\n✓ 位置可达")

except Exception as e:
    print(f"\n❌ IK求解失败: {e}")

pb.disconnect()

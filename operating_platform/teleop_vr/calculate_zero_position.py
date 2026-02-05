#!/usr/bin/env python3
"""
计算机械臂在零点位置（所有关节角度为0）时的末端执行器位置
"""
import pybullet as pb
import pybullet_data

# 初始化PyBullet
pb.connect(pb.DIRECT)
pb.setAdditionalSearchPath(pybullet_data.getDataPath())

# 加载URDF
urdf_path = "/home/dora/DoRobot/operating_platform/teleop_vr/x5_kinematics_only.urdf"
body = pb.loadURDF(urdf_path, useFixedBase=True)

# 获取关节信息
num_joints = pb.getNumJoints(body)
print(f"机械臂有 {num_joints} 个关节\n")

# 找到link6（末端执行器）
ee_link_name = "link6"
ee_idx = -1
for i in range(num_joints):
    info = pb.getJointInfo(body, i)
    link_name = info[12].decode('utf-8')
    if link_name == ee_link_name:
        ee_idx = i
        print(f"找到末端链接: {link_name} (索引: {i})")
        break

if ee_idx == -1:
    print(f"错误: 未找到末端链接 {ee_link_name}")
    pb.disconnect()
    exit(1)

# 设置所有关节为0度
print("\n设置所有关节角度为 0 rad (0°)...")
for i in range(num_joints):
    info = pb.getJointInfo(body, i)
    if info[2] != pb.JOINT_FIXED:  # 只设置非固定关节
        pb.resetJointState(body, i, 0.0)
        joint_name = info[1].decode('utf-8')
        print(f"  {joint_name}: 0.0 rad")

# 计算末端执行器位置
ls = pb.getLinkState(body, ee_idx)
ee_pos = ls[0]  # 位置 (x, y, z)
ee_orn = ls[1]  # 姿态 (四元数)

print(f"\n零点位置时的末端执行器位置:")
print(f"  位置 (x, y, z): ({ee_pos[0]:.4f}, {ee_pos[1]:.4f}, {ee_pos[2]:.4f}) 米")
print(f"  姿态 (四元数): ({ee_orn[0]:.4f}, {ee_orn[1]:.4f}, {ee_orn[2]:.4f}, {ee_orn[3]:.4f})")

# 转换为欧拉角
euler = pb.getEulerFromQuaternion(ee_orn)
print(f"  姿态 (欧拉角): roll={euler[0]:.4f}, pitch={euler[1]:.4f}, yaw={euler[2]:.4f} rad")
print(f"  姿态 (度数): roll={euler[0]*57.3:.1f}°, pitch={euler[1]*57.3:.1f}°, yaw={euler[2]*57.3:.1f}°")

pb.disconnect()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计算给定关节角度的末端执行器位置（正运动学）"""

import sys
import pybullet as pb
import pybullet_data

def calculate_fk(joint_angles_rad, urdf_path, ee_link_name):
    """
    计算正运动学
    joint_angles_rad: 关节角度列表（弧度）
    urdf_path: URDF文件路径
    ee_link_name: 末端执行器链接名称
    """
    # 初始化PyBullet
    pb.connect(pb.DIRECT)
    pb.setAdditionalSearchPath(pybullet_data.getDataPath())

    # 加载URDF
    body = pb.loadURDF(
        urdf_path,
        useFixedBase=True,
        flags=(pb.URDF_USE_INERTIA_FROM_FILE |
               pb.URDF_IGNORE_VISUAL_SHAPES |
               pb.URDF_IGNORE_COLLISION_SHAPES)
    )

    # 找到末端执行器链接索引
    ee_idx = None
    n = pb.getNumJoints(body)
    for j in range(n):
        info = pb.getJointInfo(body, j)
        child_link_name = info[12].decode("utf-8", errors="ignore")
        if child_link_name == ee_link_name:
            ee_idx = j
            break

    if ee_idx is None:
        print(f"错误: 未找到末端执行器链接 '{ee_link_name}'")
        pb.disconnect()
        return None

    # 设置关节角度
    for i in range(min(len(joint_angles_rad), 6)):
        pb.resetJointState(body, i, joint_angles_rad[i])

    # 获取末端执行器位置
    ls = pb.getLinkState(body, ee_idx)
    ee_pos = ls[0]  # 位置
    ee_orn = ls[1]  # 姿态（四元数）

    pb.disconnect()

    return ee_pos, ee_orn


if __name__ == "__main__":
    # 配置
    urdf_path = "/home/dora/DoRobot/operating_platform/teleop_vr/x5_kinematics_only.urdf"
    ee_link = "link6"

    # 从终端输出读取的关节反馈（弧度）
    joint_angles_rad = [2.29, 0.61, 1.93, 1.29, 1.48, 1.74]

    print("=" * 70)
    print("正运动学计算 - 机械臂末端执行器位置")
    print("=" * 70)
    print(f"\nURDF: {urdf_path}")
    print(f"末端链接: {ee_link}")
    print(f"\n输入关节角度（弧度）:")
    for i, angle in enumerate(joint_angles_rad):
        print(f"  关节{i+1}: {angle:.4f} rad ({angle * 57.2958:.2f}°)")

    # 计算正运动学
    result = calculate_fk(joint_angles_rad, urdf_path, ee_link)

    if result:
        ee_pos, ee_orn = result
        print(f"\n末端执行器位置（米）:")
        print(f"  X: {ee_pos[0]:.4f}")
        print(f"  Y: {ee_pos[1]:.4f}")
        print(f"  Z: {ee_pos[2]:.4f}")
        print(f"\n末端执行器姿态（四元数）:")
        print(f"  [{ee_orn[0]:.4f}, {ee_orn[1]:.4f}, {ee_orn[2]:.4f}, {ee_orn[3]:.4f}]")

        print("\n" + "=" * 70)
        print("对比信息")
        print("=" * 70)
        print(f"VR手柄位置: [0.134, 2.230, -0.083]")
        print(f"机械臂末端: [{ee_pos[0]:.3f}, {ee_pos[1]:.3f}, {ee_pos[2]:.3f}]")
        print("\n注意: VR位置是在VR追踪空间中的绝对位置")
        print("      机械臂位置是相对于机械臂基座的位置")
        print("      两者不应该直接对应，而是通过相对位移映射")
        print("=" * 70)

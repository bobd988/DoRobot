#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：按下握把键时的计算过程"""

import pybullet as pb
import pybullet_data

def calculate_target_position():
    """模拟按下握把键时的计算"""

    # 配置（从dora_vr_x5.yml读取）
    IK_HOME_POS = [0.10, 0.00, 0.30]  # 配置的初始位置
    IK_POS_MAP = "x,y,z"  # 坐标映射
    IK_POS_SCALE = [1.0, 1.0, 1.0]  # 缩放

    # 当前机械臂关节角度（从终端输出）
    current_joints_rad = [2.29, 0.61, 1.93, 1.29, 1.48, 1.74]

    # 当前VR手柄位置（从终端输出）
    current_vr_pos = [0.138, 2.234, -0.357]

    # URDF配置
    urdf_path = "/home/dora/DoRobot/operating_platform/teleop_vr/x5_kinematics_only.urdf"
    ee_link = "link6"

    print("=" * 80)
    print("诊断：按下握把键时发生了什么")
    print("=" * 80)

    # 步骤1：记录VR初始位置
    vr_home_pos = current_vr_pos[:]
    print(f"\n步骤1：记录VR手柄位置作为起点")
    print(f"  vr_home_pos = {vr_home_pos}")

    # 步骤2：计算机械臂当前末端位置（正运动学）
    print(f"\n步骤2：读取机械臂当前关节角度并计算末端位置")
    print(f"  当前关节（弧度）: {current_joints_rad}")

    # 初始化PyBullet
    pb.connect(pb.DIRECT)
    pb.setAdditionalSearchPath(pybullet_data.getDataPath())

    body = pb.loadURDF(
        urdf_path,
        useFixedBase=True,
        flags=(pb.URDF_USE_INERTIA_FROM_FILE |
               pb.URDF_IGNORE_VISUAL_SHAPES |
               pb.URDF_IGNORE_COLLISION_SHAPES)
    )

    # 找到末端执行器索引
    ee_idx = None
    n = pb.getNumJoints(body)
    for j in range(n):
        info = pb.getJointInfo(body, j)
        child_link_name = info[12].decode("utf-8", errors="ignore")
        if child_link_name == ee_link:
            ee_idx = j
            break

    # 设置当前关节角度
    for i in range(6):
        pb.resetJointState(body, i, current_joints_rad[i])

    # 计算末端位置
    ls = pb.getLinkState(body, ee_idx)
    home_pos = [float(ls[0][0]), float(ls[0][1]), float(ls[0][2])]

    print(f"  计算得到的末端位置: {home_pos}")
    print(f"  home_pos = [{home_pos[0]:.4f}, {home_pos[1]:.4f}, {home_pos[2]:.4f}]")

    # 步骤3：假设手柄移动一点点（例如1厘米）
    print(f"\n步骤3：假设手柄移动（测试）")

    # 测试场景1：手柄不动（位移为0）
    print(f"\n  场景1：手柄不动（刚按下握把键）")
    test_vr_pos = current_vr_pos[:]
    dx = test_vr_pos[0] - vr_home_pos[0]
    dy = test_vr_pos[1] - vr_home_pos[1]
    dz = test_vr_pos[2] - vr_home_pos[2]
    print(f"    VR位移: [{dx:.4f}, {dy:.4f}, {dz:.4f}]")

    # 应用映射（x,y,z = 直接映射）
    d_mapped = [dx, dy, dz]
    d_scaled = [d_mapped[0] * IK_POS_SCALE[0],
                d_mapped[1] * IK_POS_SCALE[1],
                d_mapped[2] * IK_POS_SCALE[2]]
    print(f"    映射后位移: {d_scaled}")

    target_pos = [home_pos[0] + d_scaled[0],
                  home_pos[1] + d_scaled[1],
                  home_pos[2] + d_scaled[2]]
    print(f"    目标位置: [{target_pos[0]:.4f}, {target_pos[1]:.4f}, {target_pos[2]:.4f}]")
    print(f"    ✓ 位移为0，机械臂应该保持不动")

    # 测试场景2：手柄向右移动10厘米
    print(f"\n  场景2：手柄向右移动10厘米")
    test_vr_pos = [current_vr_pos[0] + 0.10, current_vr_pos[1], current_vr_pos[2]]
    dx = test_vr_pos[0] - vr_home_pos[0]
    dy = test_vr_pos[1] - vr_home_pos[1]
    dz = test_vr_pos[2] - vr_home_pos[2]
    print(f"    VR位移: [{dx:.4f}, {dy:.4f}, {dz:.4f}]")

    d_mapped = [dx, dy, dz]
    d_scaled = [d_mapped[0] * IK_POS_SCALE[0],
                d_mapped[1] * IK_POS_SCALE[1],
                d_mapped[2] * IK_POS_SCALE[2]]

    target_pos = [home_pos[0] + d_scaled[0],
                  home_pos[1] + d_scaled[1],
                  home_pos[2] + d_scaled[2]]
    print(f"    目标位置: [{target_pos[0]:.4f}, {target_pos[1]:.4f}, {target_pos[2]:.4f}]")
    print(f"    机械臂应该向右移动10厘米")

    # 检查目标位置是否可达
    print(f"\n步骤4：检查目标位置是否在工作空间内")
    print(f"  当前末端位置: [{home_pos[0]:.4f}, {home_pos[1]:.4f}, {home_pos[2]:.4f}]")
    print(f"  工作空间估计:")
    print(f"    X: -0.5 到 0.5 米")
    print(f"    Y: -0.5 到 0.5 米")
    print(f"    Z:  0.0 到 0.7 米")

    # 检查当前位置
    if (home_pos[0] < -0.5 or home_pos[0] > 0.5 or
        home_pos[1] < -0.5 or home_pos[1] > 0.5 or
        home_pos[2] < 0.0 or home_pos[2] > 0.7):
        print(f"  ⚠️  警告：当前末端位置可能超出工作空间！")
    else:
        print(f"  ✓ 当前末端位置在工作空间内")

    print("\n" + "=" * 80)
    print("可能的问题")
    print("=" * 80)
    print("1. 当前关节角度很大（>100度），可能已经接近关节限位")
    print("2. 如果IK求解失败，可能是因为：")
    print("   - 目标位置超出工作空间")
    print("   - 关节限位约束")
    print("   - IK求解器参数需要调整")
    print("3. 建议：将机械臂移动到更安全的初始姿态（关节角度接近0）")
    print("=" * 80)

    pb.disconnect()

if __name__ == "__main__":
    calculate_target_position()

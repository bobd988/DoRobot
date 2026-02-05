#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正运动学计算工具
从关节角度计算末端执行器位姿

使用方法:
    from fk_calculator import ForwardKinematicsCalculator

    fk = ForwardKinematicsCalculator()
    joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # 6个关节角度（弧度）
    pose = fk.calculate(joint_positions)
    print(pose)  # [x, y, z, roll, pitch, yaw]
"""

import numpy as np
from pathlib import Path


class ForwardKinematicsCalculator:
    """正运动学计算器"""

    def __init__(self, urdf_path: str = None):
        """
        初始化FK计算器

        Args:
            urdf_path: URDF文件路径，如果为None则使用默认路径
        """
        if urdf_path is None:
            # 默认URDF路径
            urdf_path = "/home/dora/DoRobot-vr/operating_platform/teleop_vr/x5_kinematics_only.urdf"

        self.urdf_path = Path(urdf_path)

        if not self.urdf_path.exists():
            raise FileNotFoundError(f"URDF文件不存在: {urdf_path}")

        # 尝试导入运动学库
        self.fk_method = self._init_kinematics_library()

    def _init_kinematics_library(self):
        """初始化运动学库"""
        # 尝试方法1: ikpy
        try:
            import ikpy.chain
            self.chain = ikpy.chain.Chain.from_urdf_file(str(self.urdf_path))
            print(f"✓ 使用 ikpy 库进行FK计算")
            return "ikpy"
        except ImportError:
            pass

        # 尝试方法2: roboticstoolbox
        try:
            import roboticstoolbox as rtb
            self.robot = rtb.Robot.URDF(str(self.urdf_path))
            print(f"✓ 使用 roboticstoolbox 库进行FK计算")
            return "roboticstoolbox"
        except ImportError:
            pass

        # 尝试方法3: pybullet
        try:
            import pybullet as p
            import pybullet_data
            # 初始化pybullet（无GUI）
            self.physics_client = p.connect(p.DIRECT)
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
            self.robot_id = p.loadURDF(str(self.urdf_path))
            print(f"✓ 使用 pybullet 库进行FK计算")
            return "pybullet"
        except ImportError:
            pass

        # 如果都没有，使用简化的DH参数方法
        print("⚠ 未找到运动学库，使用简化的DH参数方法")
        print("  建议安装: pip install ikpy")
        return "dh_simple"

    def calculate(self, joint_positions: list) -> list:
        """
        计算末端执行器位姿

        Args:
            joint_positions: 6个关节角度（弧度）

        Returns:
            [x, y, z, roll, pitch, yaw] - 末端位姿（米和弧度）
        """
        if len(joint_positions) != 6:
            raise ValueError(f"需要6个关节角度，但提供了{len(joint_positions)}个")

        if self.fk_method == "ikpy":
            return self._calculate_ikpy(joint_positions)
        elif self.fk_method == "roboticstoolbox":
            return self._calculate_rtb(joint_positions)
        elif self.fk_method == "pybullet":
            return self._calculate_pybullet(joint_positions)
        else:
            return self._calculate_dh_simple(joint_positions)

    def _calculate_ikpy(self, joint_positions: list) -> list:
        """使用ikpy计算FK"""
        import ikpy.chain

        # ikpy需要包含固定关节，所以添加0在开头和结尾
        full_joints = [0] + list(joint_positions) + [0]

        # 计算变换矩阵
        transform_matrix = self.chain.forward_kinematics(full_joints)

        # 提取位置
        position = transform_matrix[:3, 3]

        # 提取旋转矩阵并转换为欧拉角
        rotation_matrix = transform_matrix[:3, :3]
        roll, pitch, yaw = self._rotation_matrix_to_euler(rotation_matrix)

        return [
            float(position[0]),
            float(position[1]),
            float(position[2]),
            float(roll),
            float(pitch),
            float(yaw)
        ]

    def _calculate_rtb(self, joint_positions: list) -> list:
        """使用roboticstoolbox计算FK"""
        # 计算变换矩阵
        T = self.robot.fkine(joint_positions)

        # 提取位置
        position = T.t

        # 提取欧拉角
        rpy = T.rpy()

        return [
            float(position[0]),
            float(position[1]),
            float(position[2]),
            float(rpy[0]),
            float(rpy[1]),
            float(rpy[2])
        ]

    def _calculate_pybullet(self, joint_positions: list) -> list:
        """使用pybullet计算FK"""
        import pybullet as p

        # 设置关节角度
        for i in range(6):
            p.resetJointState(self.robot_id, i, joint_positions[i])

        # 获取末端连杆的状态
        link_state = p.getLinkState(self.robot_id, 5)  # 假设第6个连杆是末端

        # 提取位置和姿态
        position = link_state[0]
        orientation_quat = link_state[1]

        # 四元数转欧拉角
        euler = p.getEulerFromQuaternion(orientation_quat)

        return [
            float(position[0]),
            float(position[1]),
            float(position[2]),
            float(euler[0]),
            float(euler[1]),
            float(euler[2])
        ]

    def _calculate_dh_simple(self, joint_positions: list) -> list:
        """
        使用简化的DH参数方法计算FK
        这是一个近似方法，仅用于没有运动学库的情况

        注意: 这个方法需要根据实际机器人的DH参数调整
        """
        # ARX-X5的近似DH参数（需要根据实际情况调整）
        # 这里使用一个简化的模型

        # 连杆长度（米）- 这些是估计值，需要从URDF或实际测量获取
        L1 = 0.0  # 基座到关节1
        L2 = 0.15  # 关节1到关节2
        L3 = 0.15  # 关节2到关节3
        L4 = 0.10  # 关节3到关节4
        L5 = 0.05  # 关节4到末端

        q = joint_positions

        # 简化的FK计算（仅作为示例）
        # 实际应该使用完整的DH变换
        x = (L2 * np.cos(q[0]) * np.cos(q[1]) +
             L3 * np.cos(q[0]) * np.cos(q[1] + q[2]) +
             L4 * np.cos(q[0]) * np.cos(q[1] + q[2] + q[3]))

        y = (L2 * np.sin(q[0]) * np.cos(q[1]) +
             L3 * np.sin(q[0]) * np.cos(q[1] + q[2]) +
             L4 * np.sin(q[0]) * np.cos(q[1] + q[2] + q[3]))

        z = (L1 +
             L2 * np.sin(q[1]) +
             L3 * np.sin(q[1] + q[2]) +
             L4 * np.sin(q[1] + q[2] + q[3]))

        # 姿态（简化）
        roll = q[4]
        pitch = q[1] + q[2] + q[3]
        yaw = q[0]

        return [float(x), float(y), float(z), float(roll), float(pitch), float(yaw)]

    def _rotation_matrix_to_euler(self, R: np.ndarray) -> tuple:
        """
        将旋转矩阵转换为欧拉角 (roll, pitch, yaw)
        使用ZYX顺序
        """
        sy = np.sqrt(R[0, 0]**2 + R[1, 0]**2)

        singular = sy < 1e-6

        if not singular:
            roll = np.arctan2(R[2, 1], R[2, 2])
            pitch = np.arctan2(-R[2, 0], sy)
            yaw = np.arctan2(R[1, 0], R[0, 0])
        else:
            roll = np.arctan2(-R[1, 2], R[1, 1])
            pitch = np.arctan2(-R[2, 0], sy)
            yaw = 0

        return roll, pitch, yaw


# 测试代码
if __name__ == "__main__":
    print("=" * 70)
    print("正运动学计算器测试")
    print("=" * 70)

    try:
        fk = ForwardKinematicsCalculator()

        # 测试几个关节配置
        test_configs = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # 零位
            [0.0, 0.5, -0.5, 0.0, 0.0, 0.0],  # 简单配置
            [0.1, 0.8, -1.0, -0.5, 0.2, -0.1],  # 复杂配置
        ]

        for i, joints in enumerate(test_configs):
            print(f"\n测试配置 {i+1}:")
            print(f"  关节角度: {joints}")
            pose = fk.calculate(joints)
            print(f"  末端位姿:")
            print(f"    位置 (x, y, z): ({pose[0]:.4f}, {pose[1]:.4f}, {pose[2]:.4f}) 米")
            print(f"    姿态 (r, p, y): ({pose[3]:.4f}, {pose[4]:.4f}, {pose[5]:.4f}) 弧度")
            print(f"                    ({np.rad2deg(pose[3]):.2f}°, {np.rad2deg(pose[4]):.2f}°, {np.rad2deg(pose[5]):.2f}°)")

        print("\n" + "=" * 70)
        print("✓ 测试完成")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n建议:")
        print("  1. 安装运动学库: pip install ikpy")
        print("  2. 或安装: pip install roboticstoolbox-python")
        print("  3. 或安装: pip install pybullet")

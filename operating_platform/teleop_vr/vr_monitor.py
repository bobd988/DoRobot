#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR控制系统监控脚本
监控VR启动、使能状态、位姿变化和关节姿态
"""

import json
import os
import time
from typing import Any, Optional, Dict, List
from datetime import datetime
import pyarrow as pa

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


# ==================== 数据提取工具 ====================

def extract_bytes(value: Any) -> Optional[bytes]:
    """从Dora值中提取字节数据"""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)

    if isinstance(value, pa.Array):
        if len(value) == 0:
            return None
        try:
            if pa.types.is_integer(value.type):
                ints = value.to_pylist()
                ints = [x for x in ints if x is not None]
                return bytes((int(x) & 0xFF) for x in ints)
        except Exception:
            pass
        item = value[0].as_py()
        if item is None:
            return None
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, str):
            return item.encode("utf-8")
        return str(item).encode("utf-8")

    if isinstance(value, pa.Scalar):
        item = value.as_py()
        if item is None:
            return None
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, str):
            return item.encode("utf-8")
        return str(item).encode("utf-8")

    return None


def extract_float_list(value: Any) -> Optional[List[float]]:
    """从Dora值中提取浮点数列表"""
    if value is None:
        return None

    if isinstance(value, pa.Array):
        try:
            xs = value.to_pylist()
            xs = [x for x in xs if x is not None]
            if not xs:
                return None
            return [float(x) for x in xs]
        except Exception:
            pass

    raw = extract_bytes(value)
    if not raw:
        return None

    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return None

    if isinstance(obj, list):
        try:
            return [float(x) for x in obj]
        except Exception:
            return None

    if isinstance(obj, dict):
        # 尝试从字典中提取关节数据
        for k in ("joint", "joints", "q", "angles", "positions", "pos", "joint_positions"):
            v = obj.get(k)
            if isinstance(v, list) and len(v) >= 6:
                try:
                    return [float(x) for x in v]
                except Exception:
                    return None

    return None


# ==================== 监控状态类 ====================
    """从Dora值中提取浮点数列表"""
    if value is None:
        return None

    if isinstance(value, pa.Array):
        try:
            xs = value.to_pylist()
            xs = [x for x in xs if x is not None]
            if not xs:
                return None
            return [float(x) for x in xs]
        except Exception:
            pass

    raw = extract_bytes(value)
    if not raw:
        return None

    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return None

    if isinstance(obj, list):
        try:
            return [float(x) for x in obj]
        except Exception:
            return None

    if isinstance(obj, dict):
        # 尝试从字典中提取关节数据
        for k in ("joint", "joints", "q", "angles", "positions", "pos", "joint_positions"):
            v = obj.get(k)
            if isinstance(v, list) and len(v) >= 6:
                try:
                    return [float(x) for x in v]
                except Exception:
                    return None

    return None


# ==================== 监控状态类 ====================

class VRMonitor:
    def __init__(self):
        # 统计信息
        self.vr_event_count = 0
        self.arm_cmd_count = 0
        self.action_joint_count = 0
        self.joint_feedback_count = 0

        # 状态信息
        self.vr_connected = False
        self.last_vr_time = 0
        self.enable_state = False
        self.last_enable_change = 0

        # 位姿信息
        self.last_vr_pos = None
        self.last_vr_quat = None
        self.last_gripper = 0.0

        # 关节信息
        self.last_joint_cmd = None
        self.last_joint_feedback = None

        # 性能统计
        self.start_time = time.time()
        self.last_print_time = time.time()

        # 配置
        self.print_interval = float(os.environ.get("MONITOR_PRINT_INTERVAL", "1.0"))
        self.pos_threshold = float(os.environ.get("MONITOR_POS_THRESHOLD", "0.01"))
        self.gripper_threshold = float(os.environ.get("MONITOR_GRIPPER_THRESHOLD", "0.05"))

        print("=" * 80)
        print("VR控制系统监控器启动")
        print("=" * 80)
        print(f"打印间隔: {self.print_interval}秒")
        print(f"位置变化阈值: {self.pos_threshold}米")
        print(f"夹爪变化阈值: {self.gripper_threshold}")
        print("=" * 80)
        print()

    def format_timestamp(self) -> str:
        """格式化时间戳"""
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def format_pos(self, pos: List[float]) -> str:
        """格式化位置"""
        if pos is None or len(pos) < 3:
            return "N/A"
        return f"[{pos[0]:6.3f}, {pos[1]:6.3f}, {pos[2]:6.3f}]"

    def format_quat(self, quat: List[float]) -> str:
        """格式化四元数"""
        if quat is None or len(quat) < 4:
            return "N/A"
        return f"[{quat[0]:5.2f}, {quat[1]:5.2f}, {quat[2]:5.2f}, {quat[3]:5.2f}]"

    def format_joints(self, joints: List[float]) -> str:
        """格式化关节角度"""
        if joints is None:
            return "N/A"
        if len(joints) >= 6:
            return f"[{joints[0]:5.2f}, {joints[1]:5.2f}, {joints[2]:5.2f}, {joints[3]:5.2f}, {joints[4]:5.2f}, {joints[5]:5.2f}]"
        return str(joints)

    def pos_changed(self, new_pos: List[float]) -> bool:
        """检查位置是否变化"""
        if self.last_vr_pos is None:
            return True
        if new_pos is None or len(new_pos) < 3:
            return False

        dx = abs(new_pos[0] - self.last_vr_pos[0])
        dy = abs(new_pos[1] - self.last_vr_pos[1])
        dz = abs(new_pos[2] - self.last_vr_pos[2])

        return max(dx, dy, dz) > self.pos_threshold

    def process_vr_event(self, raw: bytes):
        """处理VR事件"""
        self.vr_event_count += 1

        try:
            vr = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"[{self.format_timestamp()}] ✗ VR数据解析失败: {e}")
            return

        # 检测VR连接
        if not self.vr_connected:
            self.vr_connected = True
            print(f"[{self.format_timestamp()}] ✓ VR设备已连接")
            print()

        self.last_vr_time = time.time()

        # 提取数据（兼容两种格式）
        if isinstance(vr.get("left"), dict):
            left = vr.get("left")
            pos = left.get("pos", [0.0, 0.0, 0.0])
            quat = left.get("quat", [0.0, 0.0, 0.0, 1.0])
            enable = bool(left.get("grip", False))
            gripper = float(left.get("trigger", 0.0))
        elif isinstance(vr.get("leftController"), dict):
            lc = vr["leftController"]
            p = lc.get("position") or {}
            q = lc.get("quaternion") or {}
            pos = [float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 0.0))]
            quat = [float(q.get("x", 0.0)), float(q.get("y", 0.0)), float(q.get("z", 0.0)), float(q.get("w", 1.0))]
            enable = bool(lc.get("gripActive", False))
            gripper = float(lc.get("trigger", 0.0))
        else:
            return

        # 检测使能状态变化
        if enable != self.enable_state:
            self.enable_state = enable
            self.last_enable_change = time.time()
            status = "✓ 使能" if enable else "✗ 失能"
            print(f"[{self.format_timestamp()}] {status} (握持按钮)")
            print()

        # 检测位置变化
        pos_changed = self.pos_changed(pos)
        gripper_changed = abs(gripper - self.last_gripper) > self.gripper_threshold

        if pos_changed or gripper_changed:
            if pos_changed:
                print(f"[{self.format_timestamp()}] 📍 VR位姿变化:")
                print(f"  位置: {self.format_pos(pos)}")
                print(f"  姿态: {self.format_quat(quat)}")

            if gripper_changed:
                print(f"[{self.format_timestamp()}] 🤏 夹爪: {self.last_gripper:.2f} → {gripper:.2f}")

            print()

        self.last_vr_pos = pos
        self.last_vr_quat = quat
        self.last_gripper = gripper

    def process_arm_cmd(self, raw: bytes):
        """处理机械臂命令"""
        self.arm_cmd_count += 1

        try:
            cmd = json.loads(raw.decode("utf-8"))
        except Exception:
            return

        # 提取信息
        enable = cmd.get("enable", False)
        ee_pose = cmd.get("ee_pose", {})
        pos = ee_pose.get("pos", [])
        quat = ee_pose.get("quat", [])
        gripper = cmd.get("gripper", 0.0)

        # 只在使能状态变化时打印
        # （位姿变化已经在VR事件中打印）

    def process_action_joint(self, value: Any):
        """处理关节命令（IK求解结果）"""
        self.action_joint_count += 1

        # IK节点发送的是 PyArrow 数组: [joint1, joint2, joint3, joint4, joint5, joint6, gripper]
        joint_data = extract_float_list(value)
        if not joint_data or len(joint_data) < 7:  # 改为7（6个关节+夹爪）
            return

        # 前6个是关节角度（度），最后一个是夹爪值（0-100）
        joint_positions = joint_data[:6]  # 改为6个关节
        gripper = joint_data[6] / 100.0  # 第7个是夹爪，转换为 0-1 范围

        # 检测关节变化
        if self.last_joint_cmd is None or self._joints_changed(joint_positions, self.last_joint_cmd):
            print(f"[{self.format_timestamp()}] 🎯 IK求解结果:")
            print(f"  关节角度: {self.format_joints(joint_positions)}")
            print(f"  夹爪命令: {gripper:.2f}")
            print()

        self.last_joint_cmd = joint_positions

    def process_joint_feedback(self, raw: bytes):
        """处理关节反馈（X5实际位置）"""
        self.joint_feedback_count += 1

        try:
            feedback = json.loads(raw.decode("utf-8"))
        except Exception:
            return

        joint_positions = feedback.get("joint_positions")

        if joint_positions is None:
            return

        # 定期打印反馈
        if self.joint_feedback_count % 50 == 0:
            print(f"[{self.format_timestamp()}] 📊 X5反馈:")
            print(f"  实际关节: {self.format_joints(joint_positions)}")
            print()

        self.last_joint_feedback = joint_positions

    def _joints_changed(self, j1: List[float], j2: List[float]) -> bool:
        """检查关节是否变化"""
        if len(j1) != len(j2):
            return True

        threshold = 0.05  # 约3度
        for a, b in zip(j1, j2):
            if abs(a - b) > threshold:
                return True
        return False

    def print_status(self):
        """打印状态摘要"""
        now = time.time()
        if now - self.last_print_time < self.print_interval:
            return

        self.last_print_time = now
        elapsed = now - self.start_time

        print("=" * 80)
        print(f"[{self.format_timestamp()}] 状态摘要 (运行时间: {elapsed:.1f}秒)")
        print("-" * 80)

        # VR连接状态
        vr_status = "✓ 已连接" if self.vr_connected else "✗ 未连接"
        print(f"VR设备: {vr_status}")

        if self.vr_connected:
            time_since_vr = now - self.last_vr_time
            if time_since_vr > 2.0:
                print(f"  ⚠️  警告: {time_since_vr:.1f}秒未收到VR数据")

        # 使能状态
        enable_status = "✓ 使能" if self.enable_state else "✗ 失能"
        print(f"控制状态: {enable_status}")

        # 数据统计
        print(f"\n数据流统计:")
        print(f"  VR事件:     {self.vr_event_count:6d} 条")
        print(f"  机械臂命令: {self.arm_cmd_count:6d} 条")
        print(f"  关节命令:   {self.action_joint_count:6d} 条")
        print(f"  关节反馈:   {self.joint_feedback_count:6d} 条")

        # 当前位姿
        if self.last_vr_pos is not None:
            print(f"\n当前VR位姿:")
            print(f"  位置: {self.format_pos(self.last_vr_pos)}")
            print(f"  姿态: {self.format_quat(self.last_vr_quat)}")
            print(f"  夹爪: {self.last_gripper:.2f}")

        # 当前关节
        if self.last_joint_cmd is not None:
            print(f"\n当前关节命令:")
            print(f"  {self.format_joints(self.last_joint_cmd)}")

        if self.last_joint_feedback is not None:
            print(f"\n当前关节反馈:")
            print(f"  {self.format_joints(self.last_joint_feedback)}")

        # 性能指标
        if elapsed > 0:
            vr_hz = self.vr_event_count / elapsed
            cmd_hz = self.action_joint_count / elapsed
            print(f"\n性能指标:")
            print(f"  VR频率:   {vr_hz:5.1f} Hz")
            print(f"  命令频率: {cmd_hz:5.1f} Hz")

        print("=" * 80)
        print()


# ==================== 主函数 ====================

def main():
    node = Node()
    monitor = VRMonitor()

    print(f"[{monitor.format_timestamp()}] 等待数据流...")
    print()

    try:
        for event in node:
            et = event.get("type")
            eid = event.get("id")

            if et == "STOP":
                print(f"[{monitor.format_timestamp()}] 收到停止信号")
                break

            if et != "INPUT":
                continue

            eid = event.get("id")

            # action_joint 需要直接处理 PyArrow 数组
            if eid == "action_joint":
                monitor.process_action_joint(event.get("value"))
                continue

            # 其他输入提取为字节
            raw = extract_bytes(event.get("value"))
            if not raw:
                continue

            if eid == "vr_event":
                monitor.process_vr_event(raw)
            elif eid == "arm_cmd":
                monitor.process_arm_cmd(raw)
            elif eid == "joint":
                monitor.process_joint_feedback(raw)
            elif eid == "tick":
                # 定期打印状态摘要
                monitor.print_status()

    except KeyboardInterrupt:
        print(f"\n[{monitor.format_timestamp()}] 用户中断")
    except Exception as e:
        print(f"\n[{monitor.format_timestamp()}] 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 打印最终统计
        print("\n" + "=" * 80)
        print("监控结束 - 最终统计")
        print("=" * 80)
        elapsed = time.time() - monitor.start_time
        print(f"运行时间: {elapsed:.1f}秒")
        print(f"VR事件总数: {monitor.vr_event_count}")
        print(f"机械臂命令总数: {monitor.arm_cmd_count}")
        print(f"关节命令总数: {monitor.action_joint_count}")
        print(f"关节反馈总数: {monitor.joint_feedback_count}")
        if elapsed > 0:
            print(f"平均VR频率: {monitor.vr_event_count / elapsed:.1f} Hz")
            print(f"平均命令频率: {monitor.action_joint_count / elapsed:.1f} Hz")
        print("=" * 80)


if __name__ == "__main__":
    main()

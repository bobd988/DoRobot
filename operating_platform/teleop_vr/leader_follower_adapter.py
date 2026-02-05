#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主臂到从臂的数据适配器
将主臂的弧度值转换为从臂的度数值，并处理零位对齐
"""

import json
import numpy as np
import pyarrow as pa
import os

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


def main():
    node = Node()

    print("[adapter] Leader-Follower Adapter started", flush=True)
    print("[adapter] Converting radians to degrees with zero-position alignment", flush=True)

    # 零位对齐：记录主臂的初始位置作为零点
    initial_position = None
    zero_aligned = False

    # 上一次发送的关节位置（用于死区过滤）
    last_sent_positions = None

    # ========== 滤波器选择 ==========
    # 可选: "ema", "kalman", 或 "lowpass"
    filter_type = os.getenv("FILTER_TYPE", "lowpass").lower()
    print(f"[adapter] Using {filter_type.upper()} filter", flush=True)

    # ========== 一阶低通滤波器（当前使用）==========
    # 一阶低通滤波器：使用截止频率参数，物理意义更明确
    import math

    class LowPassFilter1D:
        """一阶低通滤波器，用于关节位置平滑"""
        def __init__(self, cutoff_freq=3.0, sample_rate=20.0):
            """
            cutoff_freq: 截止频率（Hz），越小越平滑但响应越慢
            sample_rate: 采样频率（Hz），默认20Hz
            """
            self.fc = cutoff_freq
            self.fs = sample_rate
            self.dt = 1.0 / sample_rate

            # 计算alpha系数
            # alpha = dt / (RC + dt), 其中 RC = 1 / (2*pi*fc)
            rc = 1.0 / (2.0 * math.pi * self.fc)
            self.alpha = self.dt / (rc + self.dt)

            self.y = None  # 滤波器输出

        def update(self, x):
            """更新滤波器，返回滤波后的值"""
            if self.y is None:
                # 首次初始化
                self.y = x
                return self.y

            # 一阶低通滤波公式: y = alpha * x + (1 - alpha) * y_old
            self.y = self.alpha * x + (1.0 - self.alpha) * self.y
            return self.y

    # 为每个关节创建低通滤波器
    # 不同关节使用不同的截止频率（根据需要的响应速度调整）
    lowpass_filters = [
        LowPassFilter1D(cutoff_freq=2.0, sample_rate=20.0),  # joint_0 基座：较低截止频率，更平滑
        LowPassFilter1D(cutoff_freq=3.0, sample_rate=20.0),  # joint_1 肩部：中等截止频率
        LowPassFilter1D(cutoff_freq=4.0, sample_rate=20.0),  # joint_2 肘部：较高截止频率，更快响应
        LowPassFilter1D(cutoff_freq=5.0, sample_rate=20.0),  # joint_3 腕部：高截止频率
        LowPassFilter1D(cutoff_freq=5.0, sample_rate=20.0),  # joint_4 腕部：高截止频率
        LowPassFilter1D(cutoff_freq=5.0, sample_rate=20.0),  # joint_5 腕部：高截止频率
    ]

    # ========== EMA滤波器（已注释，保留以便对比）==========
    # ema_positions = None
    # # EMA平滑系数：0.0=完全平滑(慢响应), 1.0=无平滑(快响应)
    # # 较小的alpha值会产生更强的平滑效果，但响应会变慢
    # ema_alpha = float(os.getenv("EMA_ALPHA", "0.25"))

    # ========== 卡尔曼滤波器（已注释，保留以便对比）==========
    # # 为每个关节创建独立的卡尔曼滤波器
    # class KalmanFilter1D:
    #     """简单的一维卡尔曼滤波器，用于关节位置估计"""
    #     def __init__(self, process_noise=0.01, measurement_noise=1.0):
    #         """
    #         process_noise (Q): 过程噪声，模型不确定性（越小越信任模型）
    #         measurement_noise (R): 测量噪声，传感器噪声（越大越不信任测量）
    #         """
    #         self.Q = process_noise      # 过程噪��协方差
    #         self.R = measurement_noise   # 测量噪声协方差
    #         self.P = 1.0                 # 估计协方差（初始不确定性）
    #         self.x = None                # 状态估计（关节位置）
    #         self.K = 0                   # 卡尔曼增益
    #
    #     def update(self, measurement):
    #         """更新滤波器，返回估计值"""
    #         if self.x is None:
    #             # 首次初始化
    #             self.x = measurement
    #             return self.x
    #
    #         # 预测步骤（假设位置不变）
    #         # x_pred = x  (位置保持不变)
    #         # P_pred = P + Q
    #         P_pred = self.P + self.Q
    #
    #         # 更新步骤
    #         # 卡尔曼增益: K = P_pred / (P_pred + R)
    #         self.K = P_pred / (P_pred + self.R)
    #
    #         # 状态更新: x = x_pred + K * (measurement - x_pred)
    #         self.x = self.x + self.K * (measurement - self.x)
    #
    #         # 协方差更新: P = (1 - K) * P_pred
    #         self.P = (1 - self.K) * P_pred
    #
    #         return self.x
    #
    # # 为每个关节创建卡尔曼滤波器
    # # 不同关节使用不同的噪声参数（根据负载调整）
    # kalman_filters = [
    #     KalmanFilter1D(process_noise=0.01, measurement_noise=2.0),  # joint_0 基座：测量噪声大
    #     KalmanFilter1D(process_noise=0.01, measurement_noise=1.0),  # joint_1 肩部：测量噪声中等
    #     KalmanFilter1D(process_noise=0.01, measurement_noise=0.8),  # joint_2 肘部：测量噪声中等
    #     KalmanFilter1D(process_noise=0.01, measurement_noise=0.5),  # joint_3 腕部：测量噪声小
    #     KalmanFilter1D(process_noise=0.01, measurement_noise=0.5),  # joint_4 腕部：测量噪声小
    #     KalmanFilter1D(process_noise=0.01, measurement_noise=0.5),  # joint_5 腕部：测量噪声小
    # ]

    # EMA滤波器（用于对比）
    ema_positions = None
    ema_alpha = float(os.getenv("EMA_ALPHA", "0.25"))

    # 从环境变量读取是否启用零位对齐
    enable_zero_align = os.getenv("ENABLE_ZERO_ALIGN", "true").lower() == "true"
    # 零位对齐延迟（等待几帧后再记录零位，确保数据稳定）
    zero_align_delay = int(os.getenv("ZERO_ALIGN_DELAY", "10"))

    # 底座旋转偏移（度数）
    # 设置为 90 表示顺时针旋转90度，-90 表示逆时针旋转90度
    base_rotation_offset = float(os.getenv("BASE_ROTATION_OFFSET", "90"))
    print(f"[adapter] Base rotation offset: {base_rotation_offset}°", flush=True)

    # 死区阈值（度数）：小于此值的变化将被忽略，减少抖动
    # 分层死区策略：不同关节根据功能使用不同的死区
    # - 基座：较大死区（在稳定性和响应之间平衡，避免抖动和"一卡一卡"）
    # - 主运动关节：更小死区（响应速度优先）
    # - 末端关节：中等死区（平衡稳定性和响应）
    deadband_thresholds = [
        0.0,  # joint_0 (基座) - 无死区，测试原始跟随性能
        1.0,  # joint_1 (肩部) - 较小死区，提高响应速度
        0.7,  # joint_2 (肘部) - 更小死区，提高响应速度（用户反馈响应慢）
        1.5,  # joint_3 (腕部1) - 中等死区
        1.5,  # joint_4 (腕部2) - 中等死区
        1.5,  # joint_5 (腕部3) - 中等死区
    ]

    cmd_count = 0

    for event in node:
        et = event.get("type")
        eid = event.get("id")

        if et == "STOP":
            print("[adapter] Received STOP signal", flush=True)
            break

        if et != "INPUT":
            continue

        if eid == "leader_joint":
            value = event.get("value")
            if value is None:
                continue

            # 提取关节值（弧度）
            if isinstance(value, pa.Array):
                joint_radians = value.to_pylist()
            else:
                continue

            if len(joint_radians) < 7:
                continue

            cmd_count += 1

            # 零位对齐：记录初始位置
            if enable_zero_align and not zero_aligned:
                if cmd_count >= zero_align_delay:
                    initial_position = joint_radians[:6]  # 只记录前6个关节
                    zero_aligned = True
                    print(f"[adapter] Zero position recorded: {[f'{x:.3f}' for x in initial_position]} rad", flush=True)
                    print(f"[adapter] Zero position in degrees: {[f'{np.rad2deg(x):.1f}' for x in initial_position]}°", flush=True)
                else:
                    # 还在等待稳定，不发送命令
                    continue

            # 前6个关节：弧度 -> 度数，并应用零位偏移
            joint_degrees = []
            for i in range(6):
                rad = joint_radians[i]
                # 如果启用零位对齐，减去初始位置
                if enable_zero_align and initial_position is not None:
                    rad = rad - initial_position[i]
                # 弧度转度数
                deg = np.rad2deg(rad)

                # 关节特殊处理
                if i == 0:
                    # 底座反向并旋转偏移（从环境变量读取）
                    deg = -deg + base_rotation_offset
                elif i == 1:
                    # 第二个关节反向
                    deg = -deg

                joint_degrees.append(deg)

            # ========== 滤波步骤 ==========
            if filter_type == "lowpass":
                # 一阶低通滤波（当前使用）
                filtered_degrees = []
                for i in range(6):
                    filtered = lowpass_filters[i].update(joint_degrees[i])
                    filtered_degrees.append(filtered)
                joint_degrees = filtered_degrees
            elif filter_type == "kalman":
                # 卡尔曼滤波（已注释，需要取消注释kalman_filters才能使用）
                # filtered_degrees = []
                # for i in range(6):
                #     filtered = kalman_filters[i].update(joint_degrees[i])
                #     filtered_degrees.append(filtered)
                # joint_degrees = filtered_degrees
                print("[adapter] WARNING: Kalman filter is commented out, falling back to EMA", flush=True)
                # 回退到EMA
                if ema_positions is None:
                    ema_positions = joint_degrees.copy()
                else:
                    smoothed_degrees = []
                    for i in range(6):
                        smoothed = ema_alpha * joint_degrees[i] + (1 - ema_alpha) * ema_positions[i]
                        smoothed_degrees.append(smoothed)
                    ema_positions = smoothed_degrees
                    joint_degrees = smoothed_degrees
            else:
                # EMA滤波（原始方法，保留以便对比）
                if ema_positions is None:
                    ema_positions = joint_degrees.copy()
                else:
                    smoothed_degrees = []
                    for i in range(6):
                        smoothed = ema_alpha * joint_degrees[i] + (1 - ema_alpha) * ema_positions[i]
                        smoothed_degrees.append(smoothed)
                    ema_positions = smoothed_degrees
                    joint_degrees = smoothed_degrees

            # 第二步：死区过滤（在滤波之后应用）
            # 如果变化小于阈值，使用上一次的值
            if last_sent_positions is not None:
                filtered_degrees = []
                for i in range(6):
                    delta = abs(joint_degrees[i] - last_sent_positions[i])
                    if delta < deadband_thresholds[i]:
                        # 变化太小，使用上一次的值
                        filtered_degrees.append(last_sent_positions[i])
                    else:
                        # 变化足够大，使用新值
                        filtered_degrees.append(joint_degrees[i])
                joint_degrees = filtered_degrees

            # 第三步：软限位保护（防止超出ARX X5机械范围）
            # ARX X5关节限制（度数）- 基于机械限位，留安全余量
            JOINT_LIMITS = [
                (-140, 170),    # joint_0 基座：机械限位-150到+180，留余量
                (-5, 200),      # joint_1
                (-5, 170),      # joint_2
                (-70, 70),      # joint_3
                (-80, 80),      # joint_4
                (-95, 95),      # joint_5
            ]

            clamped_degrees = []
            for i in range(6):
                lower, upper = JOINT_LIMITS[i]
                clamped = max(lower, min(upper, joint_degrees[i]))
                if abs(clamped - joint_degrees[i]) > 0.1:
                    # 如果发生了限位，打印警告
                    if cmd_count % 10 == 0:  # 避免日志刷屏
                        print(f"[adapter] WARNING: joint_{i} clamped from {joint_degrees[i]:.1f}° to {clamped:.1f}°", flush=True)
                clamped_degrees.append(clamped)
            joint_degrees = clamped_degrees

            # 记录本次发送的位置
            last_sent_positions = joint_degrees.copy()

            # 夹爪值：弧度 -> 0-100
            # 主臂夹爪的标定范围是 [1863, 2487]，span=624
            # 弧度范围大约是 ±0.48 (基于4096分辨率)
            # 映射：-0.48 -> 0 (闭合), 0 -> 50 (中间), +0.48 -> 100 (张开)
            gripper_rad = joint_radians[6]
            # 假设夹爪弧度范围是 ±0.5
            gripper_range = 0.5
            # 映射到0-100
            gripper_value = ((gripper_rad + gripper_range) / (2 * gripper_range)) * 100
            # 限制在0-100范围内
            gripper_value = max(0, min(100, gripper_value))

            # 组合成从臂需要的格式：[joint1_deg, ..., joint6_deg, gripper_0_100]
            output_data = joint_degrees + [gripper_value]

            # 发送给从臂
            node.send_output("action_joint", pa.array(output_data, type=pa.float32()), event.get("metadata", {}) or {})

            if cmd_count % 50 == 0:
                print(f"[adapter] Cmd #{cmd_count}: rad={[f'{x:.2f}' for x in joint_radians[:3]]}... deg={[f'{x:.1f}' for x in joint_degrees[:3]]}... gripper={gripper_value:.1f}", flush=True)

    print(f"[adapter] Shutting down. Total commands: {cmd_count}", flush=True)


if __name__ == "__main__":
    main()

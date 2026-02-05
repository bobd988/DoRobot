#!/usr/bin/env python3
"""测试 Leader X5 主臂连接和读取"""

import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_leader_arm():
    """测试主臂连接"""
    print("=" * 60)
    print("Leader X5 主臂测试")
    print("=" * 60)

    try:
        # 导入配置
        from operating_platform.robot.robots.configs import LeaderX5RobotConfig
        print("\n✓ 配置加载成功")

        # 创建配置实例
        config = LeaderX5RobotConfig()
        print(f"✓ 配置实例创建成功")
        print(f"  主臂端口: {config.leader_arms['main'].port}")
        print(f"  舵机数量: {len(config.leader_arms['main'].motors)}")

        # 导入电机总线
        from operating_platform.robot.components.arm_normal_so101_v1.motors.feetech import FeetechMotorsBus
        print("\n✓ Feetech 电机总线模块加载成功")

        # 创建电机配置
        motors_config = config.leader_arms['main']
        port = motors_config.port

        # 转换电机配置格式
        from operating_platform.robot.components.arm_normal_so101_v1.motors.motors_bus import Motor, MotorNormMode
        motors = {}
        for name, (motor_id, model) in motors_config.motors.items():
            motors[name] = Motor(motor_id, model, MotorNormMode.RADIANS)

        print(f"\n正在连接主臂 ({port})...")
        print("-" * 60)

        # 创建电机总线
        bus = FeetechMotorsBus(
            port=port,
            motors=motors,
        )

        # 连接
        bus.connect()
        print("✓ 主臂连接成功!\n")

        # 读取关节位置
        print("读取关节位置:")
        print("-" * 60)

        for i in range(3):
            print(f"\n第 {i+1} 次读取:")
            try:
                # 读取当前位置
                positions = bus.sync_read("Present_Position")

                print(f"  原始数据: {positions}")

                # 显示每个关节
                for name, pos in positions.items():
                    print(f"  {name:12s}: {pos:8.4f}")

                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ 读取失败: {e}")

        # 读取其他信息
        print("\n" + "=" * 60)
        print("读取舵机状态:")
        print("-" * 60)

        try:
            # 读取电压
            voltages = bus.sync_read("Present_Voltage")
            print("\n电压:")
            for name, voltage in voltages.items():
                print(f"  {name:12s}: {voltage:.2f}V")
        except Exception as e:
            print(f"  ❌ 读取电压失败: {e}")

        try:
            # 读取温度
            temps = bus.sync_read("Present_Temperature")
            print("\n温度:")
            for name, temp in temps.items():
                print(f"  {name:12s}: {temp:.1f}°C")
        except Exception as e:
            print(f"  ❌ 读取温度失败: {e}")

        try:
            # 读取负载
            loads = bus.sync_read("Present_Load")
            print("\n负载:")
            for name, load in loads.items():
                print(f"  {name:12s}: {load:.2f}")
        except Exception as e:
            print(f"  ❌ 读取负载失败: {e}")

        # 断开连接
        bus.disconnect()
        print("\n" + "=" * 60)
        print("✓ 测试完成,已断开连接")
        print("=" * 60)

    except ImportError as e:
        print(f"\n❌ 导入错误: {e}")
        print("\n请确保:")
        print("  1. 已激活 dorobot conda 环境")
        print("  2. 已安装 scservo_sdk: pip install scservo-sdk")
        import traceback
        traceback.print_exc()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_leader_arm()

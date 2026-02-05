#!/usr/bin/env python3
"""诊断主臂连接 - 识别关节数和舵机型号"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def scan_feetech_servos(port, baudrate=1000000):
    """扫描 Feetech 舵机"""
    try:
        import scservo_sdk as scs

        # 初始化端口
        portHandler = scs.PortHandler(port)
        packetHandler = scs.PacketHandler(0)  # Protocol 0

        if not portHandler.openPort():
            print(f"❌ 无法打开端口 {port}")
            return None

        if not portHandler.setBaudRate(baudrate):
            print(f"❌ 无法设置波特率 {baudrate}")
            portHandler.closePort()
            return None

        print(f"✓ 已打开端口 {port} (波特率: {baudrate})")
        print("\n正在扫描舵机 (ID 0-20)...")
        print("-" * 60)

        found_servos = []

        for servo_id in range(21):
            # 尝试读取模型号 (地址 3, 长度 2)
            model_number, result, error = packetHandler.read2ByteTxRx(
                portHandler, servo_id, 3
            )

            if result == scs.COMM_SUCCESS:
                # 读取固件版本
                fw_major, _, _ = packetHandler.read1ByteTxRx(portHandler, servo_id, 0)
                fw_minor, _, _ = packetHandler.read1ByteTxRx(portHandler, servo_id, 1)

                # 读取当前位置
                present_pos, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)

                servo_info = {
                    'id': servo_id,
                    'model_number': model_number,
                    'firmware': f"{fw_major}.{fw_minor}",
                    'position': present_pos
                }
                found_servos.append(servo_info)

                # 判断舵机型号
                model_name = "未知"
                if model_number == 777:
                    model_name = "sts3215"
                elif model_number == 0:
                    model_name = "scs_series"

                print(f"  ID {servo_id:2d}: 型号={model_name:12s} (编号:{model_number:4d})  "
                      f"固件={fw_major}.{fw_minor}  位置={present_pos:4d}")

        portHandler.closePort()

        if not found_servos:
            print("\n❌ 未找到任何舵机")
            return None

        print("\n" + "=" * 60)
        print(f"✓ 找到 {len(found_servos)} 个舵机")
        print("=" * 60)

        # 分析舵机型号
        model_numbers = set(s['model_number'] for s in found_servos)
        if len(model_numbers) == 1:
            model_num = list(model_numbers)[0]
            if model_num == 777:
                model_name = "sts3215"
            elif model_num == 0:
                model_name = "scs_series"
            else:
                model_name = f"未知 (编号: {model_num})"

            print(f"\n舵机型号: {model_name}")
        else:
            print(f"\n⚠️  检测到多种舵机型号: {model_numbers}")

        print(f"关节数量: {len(found_servos)}")

        # 给出配置建议
        print("\n" + "=" * 60)
        print("配置建议:")
        print("=" * 60)

        if len(found_servos) == 7:
            print("\n检测到 7 个舵机，可能的配置:")
            print("  - SO101 机械臂 (6 关节 + 1 夹爪)")
            print("  - Piper UAarm (6 关节 + 1 夹爪)")
            print("\n在 configs.py 中使用:")
            print(f'  port="{port}"')
            print(f'  motors={{')
            for i, servo in enumerate(found_servos):
                if i < 6:
                    print(f'    "joint_{i}": [{servo["id"]}, "{model_name}"],')
                else:
                    print(f'    "gripper": [{servo["id"]}, "{model_name}"],')
            print(f'  }}')

        elif len(found_servos) == 6:
            print("\n检测到 6 个舵机，可能的配置:")
            print("  - 6 自由度机械臂 (无夹爪)")
            print("\n在 configs.py 中使用:")
            print(f'  port="{port}"')
            print(f'  motors={{')
            for servo in found_servos:
                print(f'    "joint_{servo["id"]}": [{servo["id"]}, "{model_name}"],')
            print(f'  }}')

        else:
            print(f"\n检测到 {len(found_servos)} 个舵机")
            print("\n在 configs.py 中使用:")
            print(f'  port="{port}"')
            print(f'  motors={{')
            for servo in found_servos:
                print(f'    "joint_{servo["id"]}": [{servo["id"]}, "{model_name}"],')
            print(f'  }}')

        return found_servos

    except ImportError:
        print("❌ 未安装 scservo_sdk")
        print("请运行: pip install scservo-sdk")
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 60)
    print("主臂诊断工具")
    print("=" * 60)

    # 检查可用的串口
    import glob
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')

    if not ports:
        print("\n❌ 未找到任何 USB 串口设备")
        print("请检查:")
        print("  1. 主臂是否已连接")
        print("  2. USB 线是否正常")
        print("  3. 是否有权限访问串口 (sudo usermod -a -G dialout $USER)")
        return

    print(f"\n找到以下串口设备:")
    for i, port in enumerate(ports):
        print(f"  {i+1}. {port}")

    # 尝试每个端口
    for port in ports:
        print(f"\n\n{'=' * 60}")
        print(f"正在扫描端口: {port}")
        print('=' * 60)

        result = scan_feetech_servos(port)
        if result:
            break


if __name__ == "__main__":
    main()

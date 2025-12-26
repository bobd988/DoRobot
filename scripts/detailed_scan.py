#!/usr/bin/env python3
"""详细扫描主臂舵机"""

import serial
import time
import re

def pwm_to_angle(response_str: str, pwm_min=500, pwm_max=2500, angle_range=270):
    match = re.search(r'P(\d{4})', response_str)
    if not match:
        return None, None
    pwm_val = int(match.group(1))
    pwm_span = pwm_max - pwm_min
    angle = (pwm_val - pwm_min) / pwm_span * angle_range
    return angle, pwm_val

def main():
    port = "/dev/ttyUSB0"

    print("详细扫描主臂舵机 (ID 0-20)...\n")

    try:
        ser = serial.Serial(port, 115200, timeout=0.2)  # 增加超时时间
        print(f"✓ 已连接到 {port}\n")

        detected_motors = []

        # 扫描更大范围，包括ID 0
        for motor_id in range(0, 21):
            cmd = f'#{motor_id:03d}PRAD!'

            # 多次尝试读取
            success = False
            for attempt in range(3):
                ser.reset_input_buffer()
                ser.write(cmd.encode('ascii'))
                time.sleep(0.03)  # 增加等待时间
                response = ser.read_all().decode('ascii', errors='ignore')

                angle, pwm_val = pwm_to_angle(response.strip())
                if angle is not None and pwm_val is not None:
                    if not success:  # 只打印一次
                        detected_motors.append(motor_id)
                        print(f"✓ 检测到舵机 ID {motor_id:2d}: {angle:.2f}° (PWM={pwm_val})")
                        success = True
                    break

        print(f"\n{'='*60}")
        print(f"总共检测到 {len(detected_motors)} 个舵机")
        print(f"舵机 ID 列表: {detected_motors}")
        print('='*60)

        ser.close()

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

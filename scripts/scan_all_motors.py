#!/usr/bin/env python3
"""扫描总线上所有的舵机"""

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
    port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"

    print("扫描总线上的舵机 (ID 1-15)...\n")

    try:
        ser = serial.Serial(port, 115200, timeout=0.1)
        print(f"✓ 已连接到 {port}\n")

        detected_motors = []

        # 尝试读取 ID 1-15 的舵机
        for motor_id in range(1, 16):
            cmd = f'#{motor_id:03d}PRAD!'
            ser.reset_input_buffer()
            ser.write(cmd.encode('ascii'))
            time.sleep(0.02)
            response = ser.read_all().decode('ascii', errors='ignore')

            angle, pwm_val = pwm_to_angle(response.strip())
            if angle is not None and pwm_val is not None:
                detected_motors.append(motor_id)
                print(f"✓ 检测到舵机 ID {motor_id}: {angle:.2f}° (PWM={pwm_val})")

        print(f"\n总共检测到 {len(detected_motors)} 个舵机")
        print(f"舵机 ID 列表: {detected_motors}")

        ser.close()

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

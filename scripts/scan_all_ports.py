#!/usr/bin/env python3
"""扫描所有串口上的舵机"""

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

def scan_port(port_name):
    print(f"\n{'='*60}")
    print(f"扫描串口: {port_name}")
    print('='*60)

    try:
        ser = serial.Serial(port_name, 115200, timeout=0.1)
        print(f"✓ 已连接\n")

        detected_motors = []

        for motor_id in range(1, 16):
            cmd = f'#{motor_id:03d}PRAD!'
            ser.reset_input_buffer()
            ser.write(cmd.encode('ascii'))
            time.sleep(0.02)
            response = ser.read_all().decode('ascii', errors='ignore')

            angle, pwm_val = pwm_to_angle(response.strip())
            if angle is not None and pwm_val is not None:
                detected_motors.append(motor_id)
                print(f"  ✓ ID {motor_id}: {angle:.2f}° (PWM={pwm_val})")

        print(f"\n  总计: {len(detected_motors)} 个舵机")
        if detected_motors:
            print(f"  ID列表: {detected_motors}")

        ser.close()
        return detected_motors

    except Exception as e:
        print(f"  ✗ 无法连接: {e}")
        return []

def main():
    ports = [
        "/dev/ttyUSB0",
        "/dev/ttyACM0",
    ]

    all_motors = {}

    for port in ports:
        motors = scan_port(port)
        if motors:
            all_motors[port] = motors

    print(f"\n{'='*60}")
    print("总结")
    print('='*60)
    total = sum(len(m) for m in all_motors.values())
    print(f"总共检测到 {total} 个舵机")
    for port, motors in all_motors.items():
        print(f"  {port}: {len(motors)} 个 (ID: {motors})")

if __name__ == "__main__":
    main()

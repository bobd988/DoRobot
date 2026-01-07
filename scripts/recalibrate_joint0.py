#!/usr/bin/env python3
"""重新标定 joint_0 的运动范围"""

import sys
import os
import json

# 读取标定文件
calib_file = 'operating_platform/robot/components/arm_normal_so101_v1/.calibration/SO101-leader.json'

with open(calib_file, 'r') as f:
    calib_data = json.load(f)

print("="*70)
print("joint_0 重新标定工具")
print("="*70)

# 显示当前配置
current = calib_data['joint_0']
print(f"\n当前配置:")
print(f"  range_min: {current['range_min']}")
print(f"  range_max: {current['range_max']}")
print(f"  总范围: {current['range_max'] - current['range_min']} PWM 单位")

# 当前位置
current_pwm = 1234
print(f"\n当前位置: PWM {current_pwm}")

# 建议新的范围（以当前位置为中心，60度总范围）
half_range = 222  # (60/270) * 2000 / 2 ≈ 222
new_min = current_pwm - half_range
new_max = current_pwm + half_range

print(f"\n建议的新范围（60° 总范围，以当前位置为中心）:")
print(f"  range_min: {new_min}")
print(f"  range_max: {new_max}")
print(f"  范围: ±30°")

# 询问确认
confirm = input("\n是否应用此配置? (y/n): ").strip().lower()

if confirm != 'y':
    print("已取消")
    sys.exit(0)

# 更新配置
calib_data['joint_0']['range_min'] = new_min
calib_data['joint_0']['range_max'] = new_max

# 备份原文件
backup_file = calib_file + '.backup'
import shutil
shutil.copy(calib_file, backup_file)
print(f"\n✓ 原文件已备份到: {backup_file}")

# 保存新配置
with open(calib_file, 'w') as f:
    json.dump(calib_data, f, indent=4)
print(f"✓ 新配置已保存")

print("\n" + "="*70)
print("重新标定完成！")
print("="*70)

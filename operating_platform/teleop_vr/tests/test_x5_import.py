#!/usr/bin/env python3
import sys
import os

# 设置环境
sdk_path = "/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"
sys.path.insert(0, f"{sdk_path}/bimanual/api")
sys.path.insert(0, f"{sdk_path}/bimanual/api/arx_x5_python")

print("尝试导入 bimanual...")
try:
    from bimanual import SingleArm
    print("✓ 导入成功")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
"""
VR 坐标映射诊断工具
帮助确定正确的 VR 到机械臂坐标映射关系
"""

import numpy as np

print("="*70)
print("VR 坐标映射诊断工具")
print("="*70)

# 定义所有可能的映射组合
mappings = {
    "x,y,z": lambda v: (v[0], v[1], v[2]),
    "-x,y,z": lambda v: (-v[0], v[1], v[2]),
    "x,-y,z": lambda v: (v[0], -v[1], v[2]),
    "x,y,-z": lambda v: (v[0], v[1], -v[2]),
    "-x,-y,z": lambda v: (-v[0], -v[1], v[2]),
    "-x,y,-z": lambda v: (-v[0], v[1], -v[2]),
    "x,-y,-z": lambda v: (v[0], -v[1], -v[2]),
    "-x,-y,-z": lambda v: (-v[0], -v[1], -v[2]),

    "y,x,z": lambda v: (v[1], v[0], v[2]),
    "-y,x,z": lambda v: (-v[1], v[0], v[2]),
    "y,-x,z": lambda v: (v[1], -v[0], v[2]),
    "y,x,-z": lambda v: (v[1], v[0], -v[2]),
    "-y,-x,z": lambda v: (-v[1], -v[0], v[2]),
    "-y,x,-z": lambda v: (-v[1], v[0], -v[2]),
    "y,-x,-z": lambda v: (v[1], -v[0], -v[2]),
    "-y,-x,-z": lambda v: (-v[1], -v[0], -v[2]),

    "z,y,x": lambda v: (v[2], v[1], v[0]),
    "-z,y,x": lambda v: (-v[2], v[1], v[0]),
    "z,-y,x": lambda v: (v[2], -v[1], v[0]),
    "z,y,-x": lambda v: (v[2], v[1], -v[0]),
    "-z,-y,x": lambda v: (-v[2], -v[1], v[0]),
    "-z,y,-x": lambda v: (-v[2], v[1], -v[0]),
    "z,-y,-x": lambda v: (v[2], -v[1], -v[0]),
    "-z,-y,-x": lambda v: (-v[2], -v[1], -v[0]),

    "x,z,y": lambda v: (v[0], v[2], v[1]),
    "-x,z,y": lambda v: (-v[0], v[2], v[1]),
    "x,-z,y": lambda v: (v[0], -v[2], v[1]),
    "x,z,-y": lambda v: (v[0], v[2], -v[1]),
    "-x,-z,y": lambda v: (-v[0], -v[2], v[1]),
    "-x,z,-y": lambda v: (-v[0], v[2], -v[1]),
    "x,-z,-y": lambda v: (v[0], -v[2], -v[1]),
    "-x,-z,-y": lambda v: (-v[0], -v[2], -v[1]),

    "y,z,x": lambda v: (v[1], v[2], v[0]),
    "-y,z,x": lambda v: (-v[1], v[2], v[0]),
    "y,-z,x": lambda v: (v[1], -v[2], v[0]),
    "y,z,-x": lambda v: (v[1], v[2], -v[0]),
    "-y,-z,x": lambda v: (-v[1], -v[2], v[0]),
    "-y,z,-x": lambda v: (-v[1], v[2], -v[0]),
    "y,-z,-x": lambda v: (v[1], -v[2], -v[0]),
    "-y,-z,-x": lambda v: (-v[1], -v[2], -v[0]),

    "z,x,y": lambda v: (v[2], v[0], v[1]),
    "-z,x,y": lambda v: (-v[2], v[0], v[1]),
    "z,-x,y": lambda v: (v[2], -v[0], v[1]),
    "z,x,-y": lambda v: (v[2], v[0], -v[1]),
    "-z,-x,y": lambda v: (-v[2], -v[0], v[1]),
    "-z,x,-y": lambda v: (-v[2], v[0], -v[1]),
    "z,-x,-y": lambda v: (v[2], -v[0], -v[1]),
    "-z,-x,-y": lambda v: (-v[2], -v[0], -v[1]),
}

# 用户观察到的行为
print("\n用户观察到的行为:")
print("-" * 70)
observations = [
    ("VR 向左 (-X)", (-1, 0, 0), "机械臂向上 (+Z)"),
    ("VR 向右 (+X)", (1, 0, 0), "机械臂向右 (-Y)"),
    ("VR 向上 (+Y)", (0, 1, 0), "基座右转 (?)"),
    ("VR 向下 (-Y)", (0, -1, 0), "基座左转 (?)"),
    ("VR 向前 (+Z)", (0, 0, 1), "机械臂向前 (+X)"),
    ("VR 向后 (-Z)", (0, 0, -1), "机械臂向后 (-X)"),
]

for desc, vr_input, expected in observations:
    print(f"{desc:20} → {expected}")

print("\n" + "="*70)
print("分析：寻找匹配的映射")
print("="*70)

# 根据观察，我们知道：
# VR left (-X) → Robot up (+Z)
# VR right (+X) → Robot right (-Y)
# VR forward (+Z) → Robot forward (+X)
# VR backward (-Z) → Robot backward (-X)

print("\n从观察中我们可以推断：")
print("1. VR 左右 (±X) 影响机械臂的 Z 和 Y")
print("2. VR 前后 (±Z) 影响机械臂的 X")
print("3. VR 上下 (±Y) 的行为不清楚（导致基座旋转）")

print("\n可能的问题：")
print("- VR 上下移动不应该导致基座旋转")
print("- 这可能是因为 IK 求解器无法到达目标位置")
print("- 或者坐标映射导致目标位置在工作空间之外")

print("\n" + "="*70)
print("建议的测试步骤：")
print("="*70)
print("""
1. 重新启动系统
2. 按住握把
3. 只向一个方向移动手柄（例如只向左）
4. 观察并记录：
   - 哪些关节在动？（关节1-6）
   - 末端执行器的位置如何变化？（X/Y/Z方向）
5. 重复测试其他5个方向

这样我们可以准确确定映射关系。
""")

print("\n当前配置: IK_POS_MAP: '-y,z,-x'")
print("这意味着:")
print("  机械臂 X = -VR Y")
print("  机械臂 Y = VR Z")
print("  机械臂 Z = -VR X")

print("\n根据这个映射，预期行为应该是:")
test_cases = [
    ("VR 向左 (-X)", (-1, 0, 0)),
    ("VR 向右 (+X)", (1, 0, 0)),
    ("VR 向上 (+Y)", (0, 1, 0)),
    ("VR 向下 (-Y)", (0, -1, 0)),
    ("VR 向前 (+Z)", (0, 0, 1)),
    ("VR 向后 (-Z)", (0, 0, -1)),
]

for desc, vr_delta in test_cases:
    robot_x = -vr_delta[1]
    robot_y = vr_delta[2]
    robot_z = -vr_delta[0]

    direction = []
    if robot_x > 0:
        direction.append("向前(+X)")
    elif robot_x < 0:
        direction.append("向后(-X)")
    if robot_y > 0:
        direction.append("向左(+Y)")
    elif robot_y < 0:
        direction.append("向右(-Y)")
    if robot_z > 0:
        direction.append("向上(+Z)")
    elif robot_z < 0:
        direction.append("向下(-Z)")

    print(f"{desc:20} → 机械臂 {', '.join(direction) if direction else '不动'}")

print("\n" + "="*70)

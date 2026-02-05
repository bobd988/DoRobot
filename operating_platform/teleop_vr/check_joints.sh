#!/bin/bash
# 检查机械臂当前关节位置

cd /home/dora/DoRobot/operating_platform/teleop_vr

# 设置 X5 SDK 环境变量
X5_SDK_PATH="/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"

export LD_LIBRARY_PATH="${X5_SDK_PATH}/bimanual/api/arx_x5_src:${X5_SDK_PATH}/bimanual/api:${X5_SDK_PATH}/bimanual/lib/arx_x5_src:${X5_SDK_PATH}/bimanual/lib:/opt/ros/noetic/lib:/opt/ros/humble/lib:/usr/local/lib:${LD_LIBRARY_PATH}"

export PYTHONPATH="${X5_SDK_PATH}/bimanual/api:${X5_SDK_PATH}/bimanual/api/arx_x5_python:${PYTHONPATH}"

# 运行检查脚本
/home/dora/miniconda3/envs/dorobot/bin/python3 check_current_joints.py

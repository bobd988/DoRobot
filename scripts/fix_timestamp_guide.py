#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复方案：使用真实时间戳的数据记录器

关键修改：
1. 在开始录制时记录起始时间
2. 每帧使用真实的系统时间而不是 frame_index / fps
3. 这样视频播放速度就会与实际运动速度一致
"""

# 修改说明：
#
# 在 data_recorder_v2.py 中需要做以下修改：
#
# 1. 在 start_episode() 方法中添加：
#    self.episode_start_time = time.time()
#
# 2. 在 add_frame() 方法中，在调用 self.dataset.add_frame() 之前添加：
#    # 使用真实时间戳
#    real_timestamp = time.time() - self.episode_start_time
#    frame['timestamp'] = real_timestamp
#
# 3. 在 DoRobotDataset.add_frame() 中修改：
#    # 如果frame中已经有timestamp，使用它；否则使用frame_index计算
#    if 'timestamp' in frame:
#        timestamp = frame['timestamp']
#        del frame['timestamp']  # 从frame中删除，避免重复
#    else:
#        timestamp = frame_index / self.fps

print("""
修复方案：使用真实时间戳
======================================================================

问题原因：
  当前系统使用 frame_index / fps 计算时间戳，导致：
  - 时间戳总是理想的等间隔
  - 但实际采集可能慢于目标帧率
  - 视频播放速度快于实际运动速度

解决方案：
  使用真实的系统时间作为时间戳

需要修改的文件：
  1. operating_platform/teleop_vr/data_recorder_v2.py
  2. operating_platform/dataset/dorobot_dataset.py

详细步骤：
======================================================================

步骤1: 修改 data_recorder_v2.py
----------------------------------------------------------------------

在 VRX5Recorder 类中添加：

  def __init__(self):
      ...
      self.episode_start_time = None  # 添加这一行

  def start_episode(self):
      ...
      self.recording = True
      self.episode_start_time = time.time()  # 添加这一行
      ...

  def add_frame(self):
      ...
      # 在调用 self.dataset.add_frame() 之前添加真实时间戳
      if self.episode_start_time is not None:
          frame['timestamp'] = time.time() - self.episode_start_time

      self.dataset.add_frame(frame, self.task)

步骤2: 修改 dorobot_dataset.py
----------------------------------------------------------------------

在 add_frame() 方法中（约第918行）：

  # 原代码：
  # timestamp = frame_index / self.fps

  # 修改为：
  if 'timestamp' in frame:
      # 使用真实时间戳（如果提供）
      timestamp = frame['timestamp']
      del frame['timestamp']  # 从frame中删除，避免重复
  else:
      # 否则使用frame_index计算（向后兼容）
      timestamp = frame_index / self.fps

步骤3: 测试
----------------------------------------------------------------------

1. 重新采集一段数据
2. 检查视频播放速度是否与实际一致
3. 使用 diagnose_framerate.py 检查时间戳

======================================================================

注意事项：
  • 这个修改会使时间戳反映真实的采集时间
  • 如果系统运行慢于30fps，时间戳间隔会大于0.0333s
  • 视频仍然以30fps编码，但播放速度会与实际一致
  • 可能需要在训练时考虑不均匀的时间间隔

======================================================================
""")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时摄像头显示
从ZeroMQ接收图像并显示
"""

import os
import sys
import zmq
import cv2
import numpy as np
import signal
from functools import cache

# 全局标志
running = True

def signal_handler(sig, frame):
    global running
    print("\n[camera_viewer] Stopping...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@cache
def is_headless() -> bool:
    """检测是否在无显示器环境中运行"""
    try:
        import pynput  # noqa
        return False
    except Exception:
        return True


class CameraViewer:
    def __init__(self):
        # ZeroMQ配置
        self.socket_image = os.environ.get("SOCKET_IMAGE", "/tmp/dora-zeromq-vr-x5-image")

        # 图像尺寸配置
        self.width = int(os.environ.get("IMAGE_WIDTH", "640"))
        self.height = int(os.environ.get("IMAGE_HEIGHT", "480"))

        # 检查是否在headless环境
        self.headless = is_headless()
        if self.headless:
            print("[camera_viewer] Running in headless mode (no display)")

        # 创建ZeroMQ context
        self.context = zmq.Context()

        # 创建SUB socket
        self.sub_image = self.context.socket(zmq.SUB)
        self.sub_image.connect(f"ipc://{self.socket_image}")
        self.sub_image.setsockopt_string(zmq.SUBSCRIBE, "")  # 订阅所有消息

        # 设置超时
        self.sub_image.setsockopt(zmq.RCVTIMEO, 1000)  # 1秒超时

        print(f"[camera_viewer] Connected to: {self.socket_image}")
        print(f"[camera_viewer] Image size: {self.width}x{self.height}")
        if not self.headless:
            print("[camera_viewer] Press 'q' to quit")

    def run(self):
        global running

        frame_count = 0
        print("[camera_viewer] Starting main loop...")

        while running:
            try:
                # 接收图像数据
                parts = self.sub_image.recv_multipart()

                if len(parts) >= 2:
                    camera_name = parts[0].decode()
                    image_data = parts[1]

                    frame_count += 1
                    if frame_count % 30 == 0:  # 每30帧打印一次
                        print(f"[camera_viewer] Received frame {frame_count}, size: {len(image_data)} bytes")

                    # 将字节数据转换为numpy数组
                    expected_size = self.width * self.height * 3
                    if len(image_data) == expected_size:
                        # 原始像素数据，直接reshape（需要copy使其可写）
                        img_array = np.frombuffer(image_data, dtype=np.uint8).copy()
                        frame = img_array.reshape((self.height, self.width, 3))

                        # 如果不是headless环境，显示图像
                        if not self.headless:
                            try:
                                # 添加摄像头名称标签
                                cv2.putText(frame, camera_name, (10, 30),
                                          cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                                # 显示图像
                                cv2.imshow("VR X5 Camera", frame)

                                # 检查按键
                                key = cv2.waitKey(1) & 0xFF
                                if key == ord('q'):
                                    print("[camera_viewer] User pressed 'q', exiting...")
                                    running = False
                                    break
                            except cv2.error as e:
                                # 如果cv2.imshow失败，切换到headless模式
                                if not self.headless:
                                    print(f"[camera_viewer] Display error, switching to headless mode: {e}")
                                    self.headless = True
                    else:
                        if frame_count % 30 == 0:
                            print(f"[camera_viewer] Unexpected image size: {len(image_data)} bytes (expected {expected_size})")

            except zmq.Again:
                # 超时，继续等待
                if frame_count == 0:
                    print("[camera_viewer] Waiting for first frame...")
                continue
            except Exception as e:
                print(f"[camera_viewer] Error: {e}")
                import traceback
                traceback.print_exc()
                continue

        # 清理
        if not self.headless:
            try:
                cv2.destroyAllWindows()
            except:
                pass
        self.sub_image.close()
        self.context.term()
        print("[camera_viewer] Stopped")


def main():
    viewer = CameraViewer()
    viewer.run()


if __name__ == "__main__":
    main()

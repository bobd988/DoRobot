#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZeroMQ发送节点
将DORA数据通过ZeroMQ发送给main.py进行数据保存
"""

import os
import sys
import zmq
import json
import signal
import numpy as np

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


def extract_bytes(value):
    """从DORA value中提取bytes数据"""
    if isinstance(value, bytes):
        return value
    elif hasattr(value, 'to_numpy'):
        # PyArrow array
        return value.to_numpy().tobytes()
    elif hasattr(value, 'tobytes'):
        # NumPy array
        return value.tobytes()
    else:
        return bytes(value)


class ZeroMQSender:
    def __init__(self):
        # ZeroMQ配置
        self.socket_image = os.environ.get("SOCKET_IMAGE", "/tmp/dora-zeromq-vr-x5-image")
        self.socket_joint = os.environ.get("SOCKET_JOINT", "/tmp/dora-zeromq-vr-x5-joint")
        self.socket_vr = os.environ.get("SOCKET_VR", "/tmp/dora-zeromq-vr-x5-vr")

        # 创建ZeroMQ context
        self.context = zmq.Context()

        # 创建PUB sockets
        self.pub_image = self.context.socket(zmq.PUB)
        self.pub_image.bind(f"ipc://{self.socket_image}")

        self.pub_joint = self.context.socket(zmq.PUB)
        self.pub_joint.bind(f"ipc://{self.socket_joint}")

        self.pub_vr = self.context.socket(zmq.PUB)
        self.pub_vr.bind(f"ipc://{self.socket_vr}")

        print(f"[zeromq_sender] Bound to:")
        print(f"  image: {self.socket_image}")
        print(f"  joint: {self.socket_joint}")
        print(f"  vr: {self.socket_vr}")

    def send_image(self, camera_name, data, metadata):
        """发送图像数据"""
        try:
            # 转换PyArrow数据为bytes
            image_bytes = extract_bytes(data)
            # 转换metadata为JSON
            metadata_json = json.dumps(metadata)
            self.pub_image.send_multipart([
                camera_name.encode(),
                image_bytes,
                metadata_json.encode('utf-8')
            ])
            # Debug: 只打印前几次
            if not hasattr(self, '_image_count'):
                self._image_count = 0
            self._image_count += 1
            if self._image_count <= 3:
                print(f"[zeromq_sender] Sent image #{self._image_count}: {camera_name}, size={len(image_bytes)}, metadata={metadata}")
        except Exception as e:
            print(f"[zeromq_sender] ERROR sending image: {e}")

    def send_joint(self, joint_type, data):
        """发送关节数据"""
        try:
            # 转换PyArrow数据为bytes
            joint_bytes = extract_bytes(data)
            self.pub_joint.send_multipart([
                joint_type.encode(),
                joint_bytes
            ])
            # Debug: 只打印前几次
            if not hasattr(self, '_joint_count'):
                self._joint_count = 0
            self._joint_count += 1
            if self._joint_count <= 3:
                print(f"[zeromq_sender] Sent joint #{self._joint_count}: {joint_type}, size={len(joint_bytes)}")
        except Exception as e:
            print(f"[zeromq_sender] ERROR sending joint: {e}")

    def send_vr(self, event_id, data):
        """发送VR数据"""
        try:
            # 转换PyArrow数据为bytes
            vr_bytes = extract_bytes(data)
            self.pub_vr.send_multipart([
                event_id.encode(),
                vr_bytes
            ])
        except Exception as e:
            print(f"[zeromq_sender] ERROR sending vr: {e}")

    def close(self):
        """关闭所有socket"""
        self.pub_image.close()
        self.pub_joint.close()
        self.pub_vr.close()
        self.context.term()
        print("[zeromq_sender] Closed")


def main():
    sender = ZeroMQSender()

    # 信号处理
    def signal_handler(sig, frame):
        print("[zeromq_sender] Received signal, stopping...")
        sender.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # DORA节点
    node = Node()

    print("[zeromq_sender] Ready")

    # 主循环
    for event in node:
        event_type = event.get("type")

        if event_type == "STOP":
            print("[zeromq_sender] Received STOP event")
            break

        if event_type == "INPUT":
            event_id = event.get("id")
            value = event.get("value")
            metadata = event.get("metadata", {})

            # 发送图像
            if event_id == "image":
                sender.send_image("camera_orbbec", value, metadata)

            # 发送关节数据
            elif event_id == "joint":
                sender.send_joint("joint", value)

            # 发送动作命令
            elif event_id == "action_joint":
                sender.send_joint("action_joint", value)

            # 发送VR数据
            elif event_id == "vr_event":
                sender.send_vr("vr_event", value)

    # 清理
    sender.close()


if __name__ == "__main__":
    main()

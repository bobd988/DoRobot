#!/usr/bin/env python3
"""
摄像头连接诊断工具
用于检查 RealSense 摄像头是否正常工作
"""

import pyrealsense2 as rs
import sys

def check_realsense_cameras():
    """检查所有 RealSense 摄像头"""
    print("=" * 60)
    print("RealSense 摄像头连接诊断")
    print("=" * 60)

    # 期望的摄像头配置
    expected_cameras = {
        "405622073811": "top (顶部视角)",
        "347622073355": "wrist (腕部视角)",
        "346522074669": "right_realsense (右侧视角)"
    }

    try:
        # 创建 context
        ctx = rs.context()
        devices = ctx.query_devices()

        if len(devices) == 0:
            print("❌ 错误: 没有检测到任何 RealSense 摄像头！")
            print("\n可能的原因:")
            print("  1. 摄像头没有连接")
            print("  2. USB 端口问题")
            print("  3. 驱动程序问题")
            return False

        print(f"\n✓ 检测到 {len(devices)} 个 RealSense 设备\n")

        found_cameras = {}

        for i, device in enumerate(devices):
            serial = device.get_info(rs.camera_info.serial_number)
            name = device.get_info(rs.camera_info.name)
            firmware = device.get_info(rs.camera_info.firmware_version)

            print(f"设备 {i+1}:")
            print(f"  序列号: {serial}")
            print(f"  名称: {name}")
            print(f"  固件版本: {firmware}")

            # 检查是否是期望的摄像头
            if serial in expected_cameras:
                camera_name = expected_cameras[serial]
                found_cameras[serial] = camera_name
                print(f"  ✓ 匹配配置: {camera_name}")

                # 尝试启动流
                try:
                    pipeline = rs.pipeline()
                    config = rs.config()
                    config.enable_device(serial)
                    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

                    profile = pipeline.start(config)

                    # 尝试获取一帧
                    frames = pipeline.wait_for_frames(timeout_ms=5000)
                    color_frame = frames.get_color_frame()

                    if color_frame:
                        print(f"  ✓ 成功获取图像 (分辨率: {color_frame.get_width()}x{color_frame.get_height()})")
                    else:
                        print(f"  ❌ 无法获取图像帧")

                    pipeline.stop()

                except Exception as e:
                    print(f"  ❌ 启动流失败: {e}")
            else:
                print(f"  ⚠ 未知摄像头（不在配置中）")

            print()

        # 检查是否所有期望的摄像头都找到了
        print("=" * 60)
        print("配置检查:")
        print("=" * 60)

        all_found = True
        for serial, name in expected_cameras.items():
            if serial in found_cameras:
                print(f"✓ {name} (序列号: {serial})")
            else:
                print(f"❌ {name} (序列号: {serial}) - 未找到！")
                all_found = False

        print()

        if all_found:
            print("✓ 所有摄像头都已正确连接")
            return True
        else:
            print("❌ 部分摄像头缺失")
            print("\n建议:")
            print("  1. 检查 USB 连接")
            print("  2. 重新插拔摄像头")
            print("  3. 检查 USB 端口供电是否充足")
            print("  4. 运行 'rs-enumerate-devices' 查看详细信息")
            return False

    except Exception as e:
        print(f"❌ 检查过程中出错: {e}")
        return False


if __name__ == "__main__":
    success = check_realsense_cameras()
    sys.exit(0 if success else 1)

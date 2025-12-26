#!/usr/bin/env python3
"""调试主臂发送的关节数据"""

import zmq
import numpy as np
import time

def main():
    context = zmq.Context()

    # 连接到 ZeroMQ 发布端口
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5555")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print("=" * 80)
    print("监控 ZeroMQ 关节数据流")
    print("=" * 80)
    print("等待数据...\n")

    last_print_time = time.time()

    while True:
        try:
            # 接收数据
            topic = socket.recv_string()
            data = socket.recv_pyobj()

            # 只显示关节数据
            if "joint" in topic.lower():
                current_time = time.time()

                # 每秒最多打印一次
                if current_time - last_print_time > 1.0:
                    print(f"\n[{time.strftime('%H:%M:%S')}] Topic: {topic}")

                    if isinstance(data, (list, np.ndarray)):
                        print(f"  数据类型: {type(data)}")
                        print(f"  数据长度: {len(data)}")
                        print(f"  数据内容: {data}")

                        if len(data) > 0:
                            print(f"  各个值:")
                            for i, val in enumerate(data):
                                print(f"    [{i}] = {val:.4f}")
                    else:
                        print(f"  数据: {data}")

                    print("-" * 80)
                    last_print_time = current_time

        except KeyboardInterrupt:
            print("\n\n程序已停止")
            break
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(0.1)

    socket.close()
    context.term()

if __name__ == "__main__":
    main()

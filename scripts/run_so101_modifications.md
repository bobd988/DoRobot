# run_so101.sh 修改总结

## 修改目的
将原SO101双臂遥操脚本改造为主臂-从臂（Leader-Follower）遥操脚本，支持：
- **主臂（Leader）**: Feetech STS3215 (7关节) on /dev/ttyACM1
- **从臂（Follower）**: ARX-X5 (6关节+夹爪) on can0

## 主要修改

### 1. 版本和描述
- 版本号: `0.3.0-LeaderFollower`
- 脚本描述更新为Leader-Follower模式

### 2. 设备配置
```bash
# 主臂端口（默认）
ARM_LEADER_PORT=/dev/ttyACM1  # Feetech leader arm

# 从臂CAN接口（默认）
ARM_FOLLOWER_CAN=can0  # ARX-X5 follower arm
```

### 3. DORA配置
```bash
# DORA目录
DORA_DIR=$PROJECT_ROOT/operating_platform/teleop_vr

# Dataflow文件
dora_leader_follower_x5.yml

# Socket名称
/tmp/dora-zeromq-leader-follower-image
/tmp/dora-zeromq-leader-follower-joint
```

### 4. 新增功能：CAN接口设置
```bash
setup_can_interface() {
    # 检查CAN接口是否已配置
    # 尝试使用ARX setup脚本
    # 失败则手动配置
}
```

### 5. 设备权限管理
- 只检查主臂串口权限（/dev/ttyACM1）
- 检查CAN接口状态（can0是否UP）

### 6. CLI参数
```bash
--robot.type=leader_x5
--record.repo_id=leader-follower-x5
--record.single_task="Leader-follower teleoperation..."
```

### 7. 移除prepare_follower步骤
ARX-X5通过CAN控制，不需要串口准备步骤

## 使用方法

### 基本使用
```bash
cd /home/dora/DoRobot-vr
bash scripts/run_so101.sh
```

### 自定义参数
```bash
# 自定义数据集名称
REPO_ID=my-dataset bash scripts/run_so101.sh

# 本地模式（不上传）
CLOUD=0 bash scripts/run_so101.sh

# 边缘模式（rsync到边缘服务器）
CLOUD=2 EDGE_SERVER_HOST=192.168.1.100 bash scripts/run_so101.sh
```

## 保留的功能

所有原SO101脚本的功能都保留：
- ✅ 设备配置管理（配置文件支持）
- ✅ NPU支持（Ascend加速）
- ✅ 云端/边缘计算模式（5种模式）
- ✅ 完善的清理机制
- ✅ 权限检查和设置
- ✅ ZeroMQ通信
- ✅ 数据录制和上传
- ✅ CLI交互界面

## 工作流程

1. 初始化conda环境
2. 设置NPU环境（如果启用）
3. **设置CAN接口**（新增）
4. 导出设备端口配置
5. 设置设备权限
6. 清理旧进程和socket
7. 启动DORA dataflow（后台）
8. 等待ZeroMQ socket就绪
9. 等待DORA节点完全初始化
10. 最终权限检查
11. 启动CLI（前台，阻塞）
12. 退出时执行清理

## 注意事项

1. **首次运行需要sudo配置CAN**:
   ```bash
   sudo /home/dora/DoRobot-before/ARX_X5/setup_can.sh
   ```

2. **主臂权限**:
   ```bash
   sudo chmod 777 /dev/ttyACM1
   ```

3. **数据录制**: 按's'保存episode，按'e'停止并上传（如果启用云端模式）

4. **零位对齐**: 适配器会自动记录主臂初始位置，从臂只跟随相对运动

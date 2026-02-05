# u-arm(Feetech舵机)-Piper(松灵)
## 虚拟环境准备(dorobot)。
```bash
bash scripts/setup_env.sh
```
## 硬件连接
主臂(Feetech-6轴+夹爪)和从臂（piper:6轴+夹爪，can通信协议）的USB控制线直插电脑
### 查看相机连接
```bash
v4l2-ctl --list-devices #列出视频设备,两个相机
```
找到RGB图像的通道，修改根目录下的.dorobot_device.conf 配置。
## 激活can
```bash 
conda activate dorobot
cd DoRobot/
bash scripts/find_activate_can.sh 
```
## 标定
```bash
 scripts/calib_feetech_leader.py # 进行主臂标定
```
## 遥操
- 把主臂（舵机：Feetech）和从臂(piper)摆到相同的姿态，给从臂上电。
```bash
bash scripts/run_so101.sh #开启遥操
```
- s 保存当前episod，n 进行下一轮，最后一轮按 e 结束采集。


# u-arm(config 2,Feetech舵机)-ARX X5(方舟无限)
## 虚拟环境准备(dorobot)。
```bash
bash scripts/setup_env.sh
```
## 硬件连接
- 准备一个拓展坞，三个相机（top、wrist、right_realsense）,ARX-X5,u-arm(config 2)
拓展坞连接主臂，丛臂，两个相机（wrist、right_realsense）,top相机直连电脑
- 准备ARX-X5的sdk
- 激活丛臂（can0）
```bash
cd /home/dora/DoRobot-before/ARX_X5
bash setup_can.sh
```
## 遥操
```bash
cd DoRobot-vr
bash scripts/run_so101.sh
```
- 保存数据，另启动一个终端(只实现了一轮数据采集的保存，多轮未实现)
```bash
cd DoRobot-vr
bash scripts/send_command.sh s
bash scripts/send_command.sh e
```
- 数据格式转换 (注意路径)
```bash
cd DoRobot-vr
python convert_to_delivery_format.py
```

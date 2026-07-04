# 基于 RK3588 的芒果端侧 AI 视觉质检与智能分拣系统 — 完整工程文档

> 项目：**ELF2 / 2026 年嵌入式芯片与系统设计大赛 · 瑞芯微赛道**
> 主题：基于 RK3588 的芒果端侧 AI 视觉质检与智能分拣系统
> 项目根目录：`/home/elf/projects`
> 本文档目录：`/home/elf/projects/docs/项目详细文档/`

本套文档对整个工程的**全部子系统、算法细节、框架结构、数据契约与配置项**进行逐一说明，所有阈值、寄存器地址、协议字节、公式、权重均直接引自源码与配置文件。

---

## 文档索引

| 文件 | 内容 |
|------|------|
| [README.md](README.md)（本文件） | 工程总览、系统架构、模块地图、数据流、运行方式 |
| [01-系统架构总览.md](01-系统架构总览.md) | 分层架构、端到端数据流、进程编排、目录结构、技术栈 |
| [02-硬件驱动层.md](02-硬件驱动层.md) | camera / led / motor / sensors / servo / spectrum 全部驱动细节 |
| [03-芒果质检核心算法.md](03-芒果质检核心算法.md) | 视觉+光谱+传感融合评分、成熟度/糖度/腐烂/分级、自动分拣决策 |
| [04-语音助手与YOLO深度学习.md](04-语音助手与YOLO深度学习.md) | DeepSeek 语音播报、YOLO11 RKNN 推理、多核 NPU 线程池、跟踪计数 |
| [05-Qt上位机与云端涂鸦IoT.md](05-Qt上位机与云端涂鸦IoT.md) | Qt HMI 触控台、tuya_proxy 云代理、TuyaOpen 固件、DP 映射 |
| [06-微信小程序与数据格式契约.md](06-微信小程序与数据格式契约.md) | 微信小程序、云函数、全部 CSV/JSON schema、全部配置文件 |

---

## 一、项目概述

以 **RK3588（ELF2 开发板）** 为核心主控，构建一体化的芒果端侧智能质检终端：

- **视觉批量检测**：NPU 上运行 YOLO11，完成芒果识别、成熟度判定（未熟/成熟/过熟），并提取 RGB/HSV 颜色特征。
- **视觉 + 光谱双模态单体检测**：对单颗芒果融合 AS7341 光谱数据，输出成熟度、糖度（参考区间）、腐烂风险等无损检测结论。
- **环境辅助感知**：SHT30（温湿度）、SCD40（CO₂）、GY-302/BH1750（光照）、MQ-135（空气质量）实时监测存储环境。
- **智能分拣执行**：传送带（步进电机）+ 舵机拨杆按质检结论把芒果分流到不同通道。
- **多端交互**：Qt 触控上位机（HMI）、DeepSeek 语音播报、微信小程序远程监控与控制。
- **云端接入**：涂鸦（Tuya）云，两条链路（HTTP 代理 + MQTT 固件）实现远程监控/控制/OTA。

### 竞赛契合度
面向端侧 AI 视觉选题，支持 **1080p@30fps** 实时视频流稳定显示与检测，突出端侧 AI 的实时性与工程化应用价值。

---

## 二、系统总体架构（分层）

```
┌──────────────────────────────────────────────────────────────────────┐
│  交互展示层   Qt 上位机(HMI) │ 语音助手(DeepSeek+TTS) │ 微信小程序          │
├──────────────────────────────────────────────────────────────────────┤
│  云端接入层   tuya_proxy.py(HTTP+OpenAPI签名) │ TuyaOpen 固件(MQTT DP)     │
├──────────────────────────────────────────────────────────────────────┤
│  软件算法层   YOLO11 RKNN 推理+跟踪 │ 芒果质检融合(fusion) │ 自动分拣编排     │
├──────────────────────────────────────────────────────────────────────┤
│  数据契约层   datas/csv/*.{csv,json}（文件即数据总线）│ config/*.{yaml,json} │
├──────────────────────────────────────────────────────────────────────┤
│  硬件驱动层   camera │ spectrum(AS7341) │ sensors │ led │ motor │ servo    │
├──────────────────────────────────────────────────────────────────────┤
│  硬件平台层   RK3588 NPU(6TOPS) │ I2C/SPI/UART/PWM/SARADC │ USB/MIPI Camera │
└──────────────────────────────────────────────────────────────────────┘
```

**设计核心：以文件为数据总线，以子进程为控制通道。**
各采集/推理程序把结果原子写入 `datas/csv/` 下的 CSV/JSON；上位机、小程序、云端固件都从这些文件读取状态，并通过拉起 Python 硬件脚本下发控制命令。子系统之间**松耦合**，任一环节可独立运行、独立调试。

---

## 三、端到端数据流

```
                        ┌─ 摄像头 /dev/video21
                        ▼
YOLO11 RKNN 检测+跟踪(camera_detect.py)
   │  → vision_color_realtime.csv（逐帧颜色特征）
   │  → mango_object_realtime.csv/.json（过线完成的单果对象）
   ▼
AS7341 光谱(collect.py/color.py) → spectrum_quality_samples.csv
   │
   ▼
三模态融合(fusion.py / assess_mango_quality)
   │  → mango_quality_realtime.csv/.json（当前芒果完整结论）
   │  → mango_quality_history.csv（去重历史）
   │  → mango_batch_summary.csv/.json（批次统计）
   │
   ├──► 自动分拣(auto_sorter → sorter.py) → 舵机PWM → mango_sorter_events.csv
   ├──► 语音助手(voice_assistant.py) → DeepSeek/本地模板生成播报 → edge-tts/espeak-ng/spd-say
   ├──► Qt 上位机（轮询 CSV 渲染图表卡片）
   └──► 涂鸦云（tuya_proxy / TuyaOpen 固件按 DP 上报）→ 微信小程序

环境链路：sensors(csv_logger.py) → sensor_realtime.csv → Qt/自动补光/云上报
补光链路：ws2812b.py → led_state.csv
```

---

## 四、目录结构地图

| 目录 | 作用 | 关键内容 |
|------|------|----------|
| `src/hardware/` | 硬件驱动层 | camera / led / motor / sensors / servo / spectrum |
| `src/software/mango_quality/` | 质检融合算法 | fusion.py（核心）、auto_sorter.py、color_features.py、CLI |
| `src/software/voice_assistant/` | 语音播报 | voice_assistant.py（DeepSeek + TTS） |
| `deeplearning/yolo11_demo/` | 生产 YOLO11 推理 | camera_detect.py、yolo11_rknn.py、rknn_pool.py |
| `deeplearning/demo/` | YOLOv8 帧率参考 demo | main_camera_fps_v8.py |
| `deeplearning/*.rknn` | RK3588 INT8 量化模型 | mango_yolo11_rk3588_i8.rknn 等 |
| `deeplearning/rknn-toolkit-lite2/` | 板端推理运行时 v2.3.2 | RKNNLite aarch64 wheel 包 |
| `qt/fruit_quality_qt/` | Qt 上位机 HMI | mainwindow.cpp（~3400 行）、sensordatareader |
| `cloud/tuya_proxy/` | 云端 HTTP 代理 | tuya_proxy.py（OpenAPI 签名网关） |
| `iot/TuyaOpen/` | 涂鸦开源 IoT SDK（子模块，~22000 文件） | apps/tuya_cloud/fruit_quality_cloud 固件 |
| `wechat_miniapp/` | 微信小程序 | index/quality 页面 + tuyaDevice 云函数 |
| `config/` | 全部配置 | camera/led/motor/sensors/servo/yolo11.yaml + tuya_cloud.json |
| `datas/csv/` | 数据总线 | 全部实时 CSV/JSON |
| `docs/` | 文档 | projects.md、gpiod.md、整体框架图.png、本文档目录 |

---

## 五、技术栈汇总

| 层 | 技术 |
|----|------|
| 主控/AI | RK3588、NPU 3 核（~6 TOPS INT8）、RKNN-Toolkit-Lite2 v2.3.2 |
| 视觉 | YOLO11（anchor-free）、OpenCV、INT8 量化 `.rknn`、letterbox 640 |
| 光谱 | AS7341 11 通道、CIE1931 色度学、sRGB/HSV 转换 |
| 融合算法 | 规则专家系统（加权评分），无需训练集 |
| 硬件接口 | I2C（原生 ioctl）、SPI（WS2812B 位模拟）、UART（步进电机）、PWM sysfs（舵机）、IIO/SARADC（MQ-135） |
| 上位机 | Qt5 Widgets + QPainter 自绘图表、QProcess、C++14、qmake |
| 语音 | DeepSeek Chat API（urllib）、edge-tts 神经网络语音，回退 espeak-ng / speech-dispatcher（ALSA/HDMI） |
| 云端 | 涂鸦 OpenAPI（HMAC-SHA256 v2 签名）、TuyaOpen C SDK（MQTT）、微信云开发云函数 |
| 前端 | 微信小程序（WXML/WXSS/JS）、云函数 Node.js（crypto/https） |
| 数据 | CSV/JSON 原子写（.tmp + os.replace）、集中式 YAML 配置 |

---

## 六、运行方式（各子系统独立启动）

```bash
# 1) 环境传感器采集（写 sensor_realtime.csv）
python3 src/hardware/sensors/csv_logger.py

# 2) YOLO11 摄像头检测（写 vision/object CSV，--qt-stream 供 Qt 内嵌）
python3 deeplearning/yolo11_demo/camera_detect.py

# 3) 光谱采集（写 spectrum_quality_samples.csv）
python3 src/hardware/spectrum/collect.py --count 1

# 4) 三模态融合 + 自动分拣（写 mango_quality_realtime.csv 等）
python3 src/software/mango_quality/mango_quality_cli.py

# 5) 语音播报（读 mango_quality_realtime.csv）
export DEEPSEEK_API_KEY=...   # 联网播报需要
python3 src/software/voice_assistant/voice_assistant.py --watch

# 6) 云端代理（供小程序调用）
python3 cloud/tuya_proxy/tuya_proxy.py --host 0.0.0.0 --port 8765
#   或 mock 模式：--mock

# 7) Qt 上位机（一键统筹拉起以上进程）
cd qt/fruit_quality_qt && ./fruit_quality_qt

# 8) 涂鸦云固件（Qt 会自动拉起）
iot/TuyaOpen/apps/tuya_cloud/fruit_quality_cloud/dist/.../fruit_quality_cloud_0.1.0.elf
```

> Qt 上位机是整机运行的“总控”：进入工作页会自动启动传感、摄像头、融合进程，并常驻拉起涂鸦固件、周期探测网络状态。

---

## 七、关键说明与已知局限

1. **糖度为参考值**：无实测 Brix 标定数据集，`reference_brix_range` 仅供显示；腐烂时明确标注“不可靠”。
2. **多源鲁棒**：任一信号缺失时融合仍可运行（YOLO 权重随置信度收缩，缺失项被加权平均自动跳过）。
3. **腐烂优先**：分级/通道逻辑中腐烂状态优先级最高，可直接触发剔除/复检。
4. **凭据隔离**：涂鸦 `client_secret`、固件 UUID/AUTHKEY 均存于被 git 忽略的 secrets 文件。
5. **相机入口**：原 `src/hardware/camera/cam.py` 空占位已移除，实际相机采集由 `deeplearning/yolo11_demo/camera_detect.py` 承担。
6. **conf 阈值双值**：YOLO 代码默认 `conf=0.25`，但生产 `yolo11.yaml` 使用 `conf=0.7`，运行时以 YAML/命令行为准。

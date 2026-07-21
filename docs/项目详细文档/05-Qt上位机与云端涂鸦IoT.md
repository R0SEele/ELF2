# 05 · Qt 上位机与云端涂鸦 IoT 技术文档

本篇覆盖两个子系统：Qt 上位机（HMI）、云端代理与涂鸦 IoT。

---

## Qt 上位机 HMI

### 概述

Qt 上位机运行在 RK3588 上，以全屏无边框方式显示的触摸操作台（HMI），是整机人机交互中枢。它本身**不直接读写硬件、不做推理**，通过两种解耦手段与后端协作：

1. **以文件为数据总线**：周期性轮询 `datas/csv` 下由各 Python 程序写出的 CSV/JSON，渲染成图表与卡片。
2. **以子进程为控制通道**：用 `QProcess` 拉起/终止 Python 硬件脚本与涂鸦 IoT 固件 ELF，并向电机/LED/舵机脚本传参下发控制命令。

工程由 3 源文件 + 2 头文件构成，主逻辑集中在 `mainwindow.cpp`（约 3400 行）。

### 工程配置（`fruit_quality_qt.pro`）

```pro
QT += widgets network
CONFIG += c++14
CONFIG -= app_bundle
TEMPLATE = app
TARGET = fruit_quality_qt
SOURCES += src/main.cpp src/mainwindow.cpp src/sensordatareader.cpp
HEADERS += src/mainwindow.h src/sensordatareader.h
```

- **Qt 模块**：`widgets`（QWidget/QPainter，非 QML）+ `network`（`QNetworkAccessManager`）。
- **C++14**，`qmake` 构建，可执行文件 `fruit_quality_qt`。

### 程序入口与生命周期（`src/main.cpp`）

- `QApplication` 全局字体 `QFont("Noto Sans CJK SC")` 18pt。
- 窗口 `Qt::FramelessWindowHint` 无边框、铺满主屏 `availableGeometry()`、`showFullScreen()`。
- **信号安全退出（self-pipe trick）**：`pipe(g_signalPipe)` 非阻塞管道；`SIGINT/SIGTERM/SIGHUP` 的 `signalHandler` 仅 `write()` 一字节（异步信号安全）；主线程 `QSocketNotifier` 监听读端，激活后 `shutdownHardware()` + `app.quit()`。
- `connect(&app, aboutToQuit, &window, shutdownHardware)` 保证任意退出都复位硬件。

### 类结构总览（`src/mainwindow.h`）

7 个自绘 QWidget（重写 `paintEvent`，`QPainter` 绘制，无第三方图表库）：

| 类 | 作用 | 关键方法 |
|---|---|---|
| `VideoDisplayWidget` | 显示摄像头 JPEG 帧/提示，背景 `#0B0F14` | `setFrame/setMessage/clearFrame` |
| `AspectRatioVideoFrame`(QFrame) | 按视频宽高比居中缩放，默认 4:3 | `setContentWidget/setAspectRatioFromSize` |
| `DonutChartWidget` | 环形图（批次成熟度分布） | `setData(values, labels, colors)` |
| `BarChartWidget` | 柱状图（等级/通道分布） | `setData(...)` |
| `QualityScoreWidget` | 单果综合评分仪表 | `setScore(score, status, color)` |
| `QualityFactorWidget` | 单果五因子明细图 | `setData(labels, values, details, colors)` |
| `EnvironmentTrendChartWidget` | 环境历史折线图（网格、时间轴、断点处理） | `setSeries(points, title, unit, color)` |

主类 `MainWindow : QMainWindow`，`public slots: shutdownHardware()`。

### 窗口 / UI 结构（页面栈）

中心控件 `QStackedWidget *m_pages`，3 个顶层页面：
- **索引 0 启动页** `createStartPage()`：Logo（`logo.jpeg`，`loadStartLogo()` 抠黑成透明）、标题、`开始检测` 按钮 → `showWorkPage()`。
- **索引 1 工作页** `createWorkPage()`：左右分栏（6:3）。左列（5:2）= 视频面板（右上角网络状态标签 `m_networkStatusLabel`）+ 6 张环境卡；右列 = `createFunctionPlaceholder()` 内嵌 `QStackedWidget *m_functionPages`。
- **索引 2 历史页** `createMangoHistoryPage()`：`QTableWidget` 8 列 `{编号,时间,等级,成熟度,参考糖度,腐烂,流向,结论}`。

**功能子页面栈 `m_functionPages`**：

| 索引 | 页面 | 切换槽 |
|---|---|---|
| 0 | 功能主页 | `showFunctionHomePage()` |
| 1 | 传送带控制 | `showConveyorControlPage()` |
| 2 | LED 补光控制 | `showLedControlPage()` |
| 3 | 芒果质检（单果） | `showMangoQualityPage()` |
| 4 | 批次统计 | `showBatchStatsPage()` |
| 5 | 舵机分拣控制 | `showServoControlPage()` |
| 6 | 语音评价 | `showVoicePromptPage()` |
| 7 | 环境趋势 | `showEnvironmentTrendPage()` |

样式由 `applyGlobalStyle()`（约 2119–2550 行 QSS）统一，用 `objectName` + `property("state")` 选择器（网络状态标签 `state=online/offline/checking/warning` 切配色，`unpolish()/polish()` 刷新）。

### 常量与文件路径（`mainwindow.cpp` 匿名命名空间）

**脚本路径**：
- `kSensorCsvScript = src/hardware/sensors/csv_logger.py`
- `kCameraScript = deeplearning/yolo11_demo/camera_detect.py`
- `kMangoQualityScript = src/software/mango_quality/mango_quality_cli.py`
- `kVoiceAssistantScript = src/software/voice_assistant/voice_assistant.py`
- `kMotorCommandScript = src/hardware/motor/conveyor_cli.py`
- `kLedCommandScript = src/hardware/led/ws2812b.py`
- `kServoCommandScript = src/hardware/servo/sorter.py`

**数据/涂鸦路径**：`kSensorCsvFile=sensor_realtime.csv`、`kMangoQualityCsvFile`、`kMangoBatchCsvFile`、`kMangoHistoryCsvFile`、`kMotorConfigFile=config/motor.yaml`；`kTuyaIotElf=iot/TuyaOpen/apps/tuya_cloud/fruit_quality_cloud/dist/.../fruit_quality_cloud_0.1.0.elf`、`kTuyaIotProcessPattern="[f]ruit_quality_cloud_0.1.0.elf"`（pgrep 判活）、`kNetworkProbeUrl=https://openapi.tuyacn.com`。

**关键定时/阈值常量**：

| 常量 | 值 | 含义 |
|---|---|---|
| `kEnvironmentSampleIntervalS` | 5 | 传感脚本 `--interval` 秒 |
| `kSensorRefreshIntervalMs` | 5000 | 环境卡刷新 |
| `kLedAutoIntervalMs` | 5000 | LED 自动调光轮询 |
| `kLedAutoMinAdjustGapMs` | 4500 | 两次自动调光最小间隔 |
| `kIotStatusIntervalMs` | 5000 | IoT/网络状态检查 |
| `kIotNetworkTimeoutMs` | 4000 | 网络探测超时 |
| `kLedAutoDeadbandLux` | 100 | 自动调光死区 |
| `kLedAutoMediumErrorLux/LargeErrorLux` | 300/600 | 分档步进阈值 |
| `kLedAutoFilterAlpha` | 0.35 | 光照一阶低通系数 |
| `kSensorStopWaitMs` | 8000 | 传感进程 terminate 等待 |
| `kSensorCardCount` | 6 | 环境卡数 |
| `kFrameHeaderSize/kMaxFrameBytes` | 4 / 20MB | 视频帧头 / 单帧上限 |

### 定时器、信号与槽、线程模型

**单线程 GUI 模型**：无 QThread，并发靠 `QProcess`+`QTimer`+`QSocketNotifier`/`QNetworkReply`。

- `m_sensorTimer`（5000ms）→ `refreshSensorData()`
- `m_mangoQualityTimer`（**1000ms**）→ `refreshMangoQualityData()`
- `m_iotStatusTimer`（5000ms）→ `updateIotStatus()`；构造时即启动涂鸦固件 + 探测
- `m_ledAutoTimer`（5000ms）→ `updateLedAutoControl()`（仅自动调光开启时 start）

`QProcess` 信号：`m_sensorProcess`(stderr→readSensorMessages, finished→handleSensorFinished)、`m_mangoQualityProcess`、`m_voicePromptProcess`(MergedChannels，stdout/stderr→readVoicePromptMessages, finished→handleVoicePromptFinished)、`m_cameraProcess`(stdout→readCameraFrames 二进制帧流)、`m_tuyaIotProcess`(MergedChannels，读丢弃防阻塞)、`m_motorCommandProcess`（命令级临时 connect/disconnect）。`finished` 用 `static_cast` 消歧重载。

### 页面切换驱动的进程生命周期

- `showWorkPage()`：`startSensorProcess()`+刷新+启定时器；`startCameraProcess()`；`startMangoQualityProcess()`+刷新+启定时器。
- `showStartPage()`：`shutdownHardware()`+停定时器+切索引 0。
- `showMangoQualityPage()`/`showBatchStatsPage()`/`showMangoHistoryPage()`：切子页并刷新。
- `showVoicePromptPage()`：切到语音评价子页；两个按钮分别触发 `voice_assistant.py --once --target previous --speak-invalid --backend <后端> --edge-voice <声音> --tts-timeout <秒> --alsa-device <设备> --timeout 5` 和 `--target batch`。后端优先取 `VOICE_BACKEND`，未设置时为 `edge-tts`；TTS 超时优先取 `VOICE_TTS_TIMEOUT`，默认 12 秒；设备优先取 `VOICE_ALSA_DEVICE`，未设置时默认 `plughw:2,0`。如需网络失败时也能出声，可设 `VOICE_BACKEND=auto`。
- `shutdownHardware()`（幂等，`m_shutdownDone` 守卫）：停 LED 自动、必要时关灯、停传送带、停三模态、停语音评价进程、停传感、停摄像头、kill 电机命令进程。析构额外 `stopTuyaIotProcess()`。

### 环境传感数据读取（`SensorDataReader`）

```cpp
struct SensorValue { QString name; QString value; QString unit; };
struct SensorSnapshot { QVector<SensorValue> values; QString sourceFile; QString updatedAt; };
class SensorDataReader { SensorSnapshot readLatest() const; ... };
```

- `readLatest()`：文件不存在返回提示 `"未检测到环境 CSV 文件"`；`updatedAt` 取文件 `lastModified()` 格式化 `yyyy-MM-dd HH:mm:ss`。
- `readCsv()`：UTF-8 逐行；若首行像表头（`looksLikeHeader`）且列数一致，取表头+最后一行键值配对；否则回退每行 `key,value[,unit]`。
- **白名单字段**：`temperature_c, humidity_rh, co2_ppm, light_lux, air_quality_ppm, env_status`。
- `displayNameFor`：中文名映射；`displayValueFor`+`ratingFor`：附中文评级（温度 `<15偏低/≤28适宜/≤35偏高/过热`；湿度 `偏干/舒适/偏湿`；CO2 `空气清新/略高/偏闷/通风不足`；光照 `偏暗/柔和/明亮/较亮/强光`；空气质量 `良好/一般/偏差/较差`）。温度带 `℃`，湿度/空气质量带 `%`。

`refreshSensorData()` → `updateSensorCards()`：写 6 张卡，不足用 `defaultSensorName(i)` + `"--"`。

> `sensor_realtime.csv` 表头：`temperature_c,humidity_rh,co2_ppm,light_lux,air_quality_ppm,env_status,timestamp,sensor_errors`。

### 环境趋势（`refreshEnvironmentTrendData`）

- 功能主页“数据查看”内的“环境趋势”进入索引 7 子页。
- 指标切换：温度、湿度、CO₂、光照、空气质量；时间范围：最近 1 小时、6 小时、24 小时、全部。
- 读取 `sensor_realtime.csv` 后按时间排序，以最新采样时间作为区间终点；曲线按时间桶保留最小/最大值，最多绘制 420 个点，统计卡仍使用完整区间计算当前/最低/最高值。
- 相邻采样间隔大于常规间隔 8 倍（且至少 60 秒）时断开折线，避免把停机时段错误画成连续变化。
- 页面打开时立即刷新；停留在趋势页时复用 `m_sensorTimer` 每 5 秒更新。

### 单果三模态质检读取（`refreshMangoQualityData`）

读 `mango_quality_realtime.csv`（表头+最后一行）。字段：`maturity_label/score`、`sugar_label/score/reference_brix_range`、`rot_status/score`、`final_status`、`mango_id`、`quality_grade`、`suggested_channel`、`stable_frames/consistency_label/score`、`yolo_label/confidence`、`data_status`、`reason`、`timestamp`。

计算：
- `freshnessValue = 100 - rotRiskValue`
- **综合分**（仅 `hasValidDetection`）：`overall = maturity*0.30 + sugar*0.20 + freshness*0.30 + stability*0.10 + yolo*0.10`（限 0–100）。
- 评分色：`可接受→#2F6B4F`、`需要复检→#C77B2B`、`建议剔除→#A53A32`、其它 `#697468`。
- `data_status` 归一：`vision_ok+spectrum_ok→视觉+光谱`，单一→仅视觉/仅光谱，含 missing→等待数据。
- 写 `m_mangoScoreChart->setScore(...)`、`m_mangoFactorChart->setData({成熟度,参考糖度,新鲜度,稳定性,YOLO}, ...)`，末尾链式 `refreshBatchStatsData()`。

### 批次统计读取（`refreshBatchStatsData`）

读 `mango_batch_summary.csv`。三图：`m_batchMaturityChart`（Donut 未熟/成熟/过熟 `#34C759/#FFCC00/#FF9500`）、`m_batchGradeChart`（Bar A/B/C/剔除 `#007AFF/#34C759/#FF9500/#FF3B30`）、`m_batchChannelChart`（Bar 销售/催熟/加工/复检/剔除）。摘要 `"本批次已统计N个芒果，可销售X%，异常风险Y%。最近结果：…。"`。缺失走 `resetBatchUi()`。

### 历史记录读取（`refreshMangoHistoryData`）

读 `mango_quality_history.csv` 全部行，**倒序**填 `m_historyTable`，列键 `{mango_id,timestamp,quality_grade,maturity_label,reference_brix_range,rot_status,suggested_channel,final_status}`，`mango_id` 前加 `#`。底部“已检测 N 个芒果”。

### 语音评价（`runVoicePromptCommand`）

功能主页新增“语音评价”入口，子页内两个功能键：
- `评价上一个芒果` → `announcePreviousMango()` → `voice_assistant.py --once --target previous --speak-invalid --backend <后端> --edge-voice <声音> --tts-timeout <秒> --alsa-device <设备> --timeout 5`，读取 `mango_quality_history.csv` 最后一条历史单果。
- `评价整批芒果` → `announceBatchMango()` → `voice_assistant.py --once --target batch --speak-invalid --backend <后端> --edge-voice <声音> --tts-timeout <秒> --alsa-device <设备> --timeout 5`，读取 `mango_batch_summary.csv` 最后一条批次统计。

语音脚本由 `m_voicePromptProcess` 异步运行；运行期间禁用两个语音按钮，结束后恢复并用 `m_voicePromptStatusLabel` 显示完成或失败状态。

### 视频帧协议

摄像头脚本 `--qt-stream --parent-pid <pid>` 启动（cwd `deeplearning/yolo11_demo`）。Qt 从 stdout 累积到 `m_cameraBuffer`：
- **帧格式**：4 字节大端长度头 + JPEG；`frameSize ∉ (0, 20MB]` 视为错误清缓冲。
- `showCameraFrame()`：`QPixmap::loadFromData(jpegData,"JPG")` → 更新宽高比 → `setFrame()`。

### 硬件控制（子进程下发）

均 `python3 <脚本> <参数>`、`setWorkingDirectory("/home/elf/projects")`。

- **传送带** `runMotorCommand`：`forward/reverse/stop`；非 stop 追加 `--speed-ms <档位速度>`。三档 `m_conveyorSpeedGear` 0/1/2 → `0.10/0.13/0.16`（`loadConveyorSpeedRange()` 解析 `motor.yaml` 的 `conveyor:` 段覆盖）。成员进程 `m_motorCommandProcess` 异步，临时 connect `finished` 更新状态标签。
- **LED** `runLedCommand`：`ws2812b.py set --brightness <pct>` 或 `off`。局部 `QProcess` 同步（`waitForFinished(3000)`）。**自动调光** `updateLedAutoControl()`：`readLatestLightLux()` 取 `light_lux` → 一阶低通（α=0.35）→ 误差超死区 100lx 按 300/600lx 分档步进 1/3/5 调亮度（0–100），间隔 ≥4500ms。
- **舵机** `runServoCommand`：`sorter.py <position>`，同步 `waitForFinished(4000)`。位置 `"1"(1号0度)/"2"(2号120度)/"3"(3号240度)`。

### 涂鸦 IoT 进程与网络状态

- `startTuyaIotProcess()`：检查 ELF 存在可执行；`isTuyaIotProcessRunning()`（自身状态 + `pgrep -f`）避免重复；成功置 `m_tuyaIotStartedByQt=true`。
- `updateIotStatus()`（5s）：未运行→“物联网未运行(offline)”并尝试重启；运行→先“运行中(checking)”，再 `QNetworkAccessManager` GET `https://openapi.tuyacn.com`（`singleShot(4000,abort)` 超时）→ online/warning/offline。`setIotStatusText(text,state)` 刷新样式。
- `stopTuyaIotProcess()` 仅在 `m_tuyaIotStartedByQt` 为真时 terminate/kill（不误杀外部实例）。

---

## 云端代理与涂鸦 IoT

### 概述

把 RK3588 本地芒果质检数据接入**涂鸦（Tuya）云**，由两条互补链路组成：

1. **`tuya_proxy.py`（本地 HTTP 反向代理 / API 网关）**：轻量 HTTP 服务（`http.server`，无第三方依赖），供**微信小程序**调用。把涂鸦凭据留设备侧，负责 OpenAPI 签名、令牌管理、设备状态读取、控制下发，并在涂鸦不可用时**回退本地执行硬件脚本**。
2. **`TuyaOpen` SDK + `fruit_quality_cloud` 固件（ELF）**：涂鸦开源 C/C++ SDK 编译的 Ubuntu 可执行文件，作为**真正的涂鸦设备端**（MQTT 直连），周期读本地 CSV/JSON 以 DP 上报、接收下发 DP 执行硬件脚本。即 Qt 拉起的 `kTuyaIotElf`。

```
微信小程序 ──HTTP──> tuya_proxy.py ──OpenAPI(签名)──> 涂鸦云
                          └──subprocess(回退)──> 本地硬件脚本
datas/csv/*.{json,csv} ──> fruit_quality_cloud.elf(TuyaOpen) ──MQTT──> 涂鸦云 ──DP下发──> 本地硬件脚本
```

### 一、tuya_proxy.py 架构

文件 `cloud/tuya_proxy/tuya_proxy.py`（仅标准库 `urllib/hmac/hashlib/http.server/csv/json/subprocess`）。

**路径常量**（相对 `PROJECT_ROOT`）：`DEFAULT_CONFIG=config/tuya_cloud.json`、`DEFAULT_SECRET_CONFIG=config/tuya_cloud_secrets.json`、`QUALITY_JSON=mango_quality_realtime.json`、`SENSOR_CSV=sensor_realtime.csv`、`BATCH_JSON=mango_batch_summary.json`、`CONTROL_STATE_JSON=tuya_proxy_control_state.json`。

**HTTP 服务**：`ThreadingHTTPServer` + `BaseHTTPRequestHandler`，`server_version="MangoTuyaProxy/0.1"`。参数 `--host`(默认 127.0.0.1)、`--port`(8765)、`--config`、`--secret-config`、`--mock`。全响应含 CORS（`Allow-Origin:*`, `Methods:GET,POST,OPTIONS`, `Headers:Content-Type`）。

**API**：

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/api/health` | 健康检查（mode、device_id） |
| GET | `/api/device/config` | 全部 `dp_meta`、`writable`、`group_labels` |
| GET | `/api/device/status` | 设备完整状态（items/groups） |
| POST | `/api/device/command` | 下发单条命令 `{code,value}` |
| POST | `/api/device/commands` | 下发多条 `{"commands":[...]}` |

`/api/device/status`：mock→`mock_tuya_response()`；真实→`api.device_status()`；无 items 回退 `build_local_status_payload(...,"local_fallback")`。

#### 涂鸦 OpenAPI 客户端（`TuyaOpenApi`）与鉴权

`load_config`：合并 `tuya_cloud.json`+`secrets`；`client_secret` 优先环境变量 `TUYA_CLIENT_SECRET`；默认 `endpoint=https://openapi.tuyacn.com`、`api_variant=iot-03`。

**签名 `_sign_headers`（HMAC-SHA256 v2）**：
- `t=毫秒时间戳`、`nonce=uuid4().hex`、`content_sha256=sha256(body)`。
- `stringToSign = f"{METHOD}\n{content_sha256}\n\n{url_path}"`（query 按 key 排序 URL 编码）。
- 取令牌前签名源 `client_id+t+nonce+stringToSign`；取令牌后 `client_id+access_token+t+nonce+stringToSign`。
- `sign = HMAC_SHA256(client_secret, source).hexdigest().upper()`。
- 头：`client_id, sign, t, nonce, sign_method=HMAC-SHA256`，有 token 加 `access_token`。

**令牌 `token()`**：`GET /v1.0/token?grant_type=1`，缓存至过期前 60s；`request()` 遇 code∈{1010,1011,1012,1013} 刷新重试一次。超时 12s，错误封装 `ProxyError(502)`。

**状态读取 `device_status()`（多端点回退）**：① `GET /v2.0/cloud/thing/{id}/shadow/properties`（Thing 模型影子，`_source=tuya_v2_shadow`）；② `/v1.0/iot-03/devices/{id}/status` 与 `/v1.0/devices/{id}/status`（`api_variant=legacy` 时顺序反转）。

**命令下发 `send_commands()`**：① `POST /v2.0/cloud/thing/{id}/shadow/properties/issue`，body `{"properties":{code:value}}`；② 回退 `/v1.0/iot-03/devices/{id}/commands` 与 `/v1.0/devices/{id}/commands`，body `{"commands":[{code,value}]}`。

#### DP 定义（`DP_META`，35 个 DP）

分组 `GROUP_LABELS`：device 设备 / quality 当前芒果 / environment 环境 / batch 批次 / control 控制。

- **environment（只读）**：`temperature_c`(℃,scale1)、`humidity_rh`(%RH,scale1)、`co2_ppm`、`light_lux`、`air_quality_ppm`、`env_status`(normal/partial_error/error/unknown)。
- **quality（只读）**：`mango_id`、`quality_grade`(unknown/a/b/c/reject)、`maturity_label`(none/unripe/ripe/overripe/unknown)、`maturity_score`、`maturity_confidence`(%)、`sugar_label`(low/normal/high/unable/unknown)、`sugar_score`、`rot_status`(normal/suspect/rotten/unable/unknown)、`rot_score`、`final_status`、`yolo_label`、`yolo_confidence`(%)、`data_status`、`last_update`、`suggested_channel`(sales/ripen/process/recheck/reject/unknown)。
- **batch（只读）**：`batch_total/batch_a_count/batch_b_count/batch_reject_count`。
- **control（writable:true）**：`conveyor_cmd`(stop/forward/reverse)、`conveyor_speed`(slow/medium/fast)、`sorter_position`(left/center/right)、`led_switch`(bool)、`led_brightness`(value%，validate 夹 0–100)、`detect_cmd`(idle/start/stop/snapshot)、`auto_sort_enable`(bool)。
- **device**：`device_status`(idle/running/error/offline/unknown)、`error_message`。

数值 DP `scale`：上行 `numeric = value/10**scale` 拼单位；下行/上报 `int(value*10**scale)`。`enum_code` 做“中文/别名→枚举码”模糊匹配。

#### 本地状态拼装

`read_local_status`/`build_local_status_payload`：以 `read_control_state()` 为基底，叠加 `QUALITY_JSON`（中文标签经 `enum_code` 转码，分数 `scaled_number(...,1)`）、`SENSOR_CSV`（最后一行，跳表头）、`BATCH_JSON`。`build_status_payload` 产出 `{ok,source,device_id,updated_at(ms),status,items[],groups{},group_labels}`。

#### 控制态文件 `datas/csv/tuya_proxy_control_state.json`

持久化最近可写控制 DP 值。默认 `DEFAULT_CONTROL_STATUS`：`{device_status:running, conveyor_cmd:stop, conveyor_speed:medium, sorter_position:center, led_switch:false, led_brightness:40, detect_cmd:idle, auto_sort_enable:true}`。`read_control_state()` 默认值兜底；`write_control_state()` 只写白名单键，原子写。**联动 `apply_control_commands`**：`led_brightness>0 → led_switch=true`；`conveyor_cmd=stop → device_status=idle`，`forward/reverse → running`。

#### 命令校验与回退

- `validate_commands`：拒绝非 `DP_META` 或非 writable（400）；按 type 校验；`led_brightness` 夹 0–100。
- POST：校验 → mock 成功 / 真实 `api.send_commands` → 成功后 `apply_control_commands`+`write_control_state`。
- **本地回退** `can_use_local_fallback`：涂鸦错误含 `"command or value not support"` 或 code 2008 时，本地执行 `run_local_command`（`subprocess.run(check=True,timeout=8)` 调 `conveyor_cli.py/sorter.py/ws2812b.py`；速度 slow=0.10/medium=0.13/fast=0.16），成功返回 `source:"local_fallback"`，失败回滚 `previous_state` 报 500。
- **注意**：proxy 是**请求驱动**的（每请求实时取数/发命令），无后台轮询上报循环；周期上云由固件负责。

#### 配置 schema

- `config/tuya_cloud.json`：`{"endpoint":"https://openapi.tuyacn.com","client_id":"8nwmcqqvfastfx4vdwdf","device_id":"6c97539f5b52b88685mt3o","api_variant":"iot-03"}`
- `config/tuya_cloud_secrets.json`（git 忽略）：`{"client_secret":"..."}`，或环境变量 `TUYA_CLIENT_SECRET`。

### 二、TuyaOpen 开源嵌入式 IoT SDK

目录 `iot/TuyaOpen`（涂鸦官方开源 SDK git 子模块，约 22000 文件）。

**它是什么**：涂鸦开源的跨平台 C/C++ 物联网/AI-agent 设备端 SDK（Apache-2.0）。支持涂鸦 T 系列 Wi-Fi/BT MCU、树莓派、ESP32 等，直连涂鸦云实现远程控制/监控/OTA，内置鉴权与数据加密，提供 ASR/KWS/TTS/STT 与多模态 AI 能力。支持 Ubuntu（可直接在 Linux 主机运行）、Tuya T2/T3/T5、ESP32/C3/S3、LN882H、BK7231N 等。

**本项目用法**：不改 SDK 内部，在 `apps/tuya_cloud/` 下新增应用 `fruit_quality_cloud`（面向 Ubuntu，`CONFIG_BOARD_CHOICE_UBUNTU=y`，版本 0.1.0），产物即 `fruit_quality_cloud_0.1.0.elf`。用 `tuya_iot`/`tuya_iot_dp`/`netmgr`/`tal_*` API 完成激活、MQTT 直连与 DP 收发，把 RK3588 变成标准涂鸦设备。

#### 固件主流程（`tuya_main.c`）

- `user_main()`：`app_runtime_init()`（cJSON hooks、日志、KV、软定时器、workqueue）→ `fruit_quality_bridge_init()` → `app_iot_init()` → 循环 `for(;;){ tuya_iot_yield(&s_client); fruit_quality_bridge_poll(&s_client); }`。Linux `main()` 直接调 `user_main()`。
- `app_iot_init()`：读授权（否则回退宏 `TUYA_OPENSDK_UUID/AUTHKEY`）；`tuya_iot_init(TUYA_PRODUCT_ID + uuid/authkey + 回调)`；`netmgr_init`（WIFI/WIRED/CELLULAR 按开关）；`tuya_iot_start`。
- `user_event_handler_on()`：`BIND_START/ACTIVATE_SUCCESSED/MQTT_CONNECTED/DISCONNECT`、`DIRECT_MQTT_CONNECTED`（输出绑定 URL `https://smartapp.tuya.com/s/p?p=<PID>&uuid=<uuid>&v=2.0` 供 App 扫码绑定）、`UPGRADE_NOTIFY`（OTA）、`RESET/RESET_COMPLETE`（复位重启）、`DP_RECEIVE_OBJ`（转 `fruit_quality_bridge_handle_dp` 并回报）。

#### 数据桥（`fruit_quality_bridge.c`）—— 本地文件 ↔ 涂鸦 DP（数字 DP ID）

`101 temperature_c、102 humidity_rh、103 co2_ppm、104 light_lux、105 air_quality_ppm、106 env_status；111 mango_id、112 quality_grade、113 maturity_label、114 maturity_score、115 maturity_confidence、116 sugar_label、117 sugar_score、118 rot_status、119 rot_score、120 final_status、121 yolo_label、123 yolo_confidence、124 data_status、125 last_update、126 suggested_channel；131 batch_total、132 batch_a_count、133 batch_b_count、134 batch_reject_count；141 conveyor_cmd、142 conveyor_speed、143 sorter_position、144 led_switch、145 led_brightness、146 detect_cmd、147 auto_sort_enable、148 device_status、149 error_message`。

- **上报 `fruit_quality_bridge_poll`**（`tuya_iot_dp_report_json`，仅连接时）：
  - `report_quality()`：读 `mango_quality_realtime.json`，中文标签转枚举——间隔 `FRUIT_REPORT_INTERVAL_MS=5000ms`。
  - `report_environment()`：读 `sensor_realtime.csv` 最后一行——间隔 `FRUIT_ENV_REPORT_INTERVAL_MS=10000ms`。
  - `report_batch()`：读 `mango_batch_summary.json`——间隔 **30000ms**。
- **下行 `fruit_quality_bridge_handle_dp`**（`system(...)` 执行本地脚本）：
  - `141` → `conveyor_cli.py <cmd> --speed-ms <0.10/0.13/0.16>`
  - `142` → 更新速度，运行中则重发电机命令
  - `143` → `sorter.py <pos> --config config/servo.yaml`
  - `144/145` → `ws2812b.py set --brightness N` 或 `off`（夹 0–100）
- `146` → 写入带 `detect_request_id` 的共享控制状态，由 Qt 执行检测启动/停止/抓拍
- `147` → 持久化 `auto_sort_enable`，融合分拣进程每次决策前读取
  - 失败经 `report_error`（DP 149 + DP 148=error）上报。每次成功后 `report_control_state()` 回报 DP 141–149。

#### 固件配置

`src/tuya_config.h`：`TUYA_PRODUCT_ID`（默认 `nxk9ktssjoc4xbbe`）、`TUYA_OPENSDK_UUID/AUTHKEY`（占位，由 git 忽略的 `tuya_config_secrets.h` 覆盖）、`FRUIT_PROJECT_ROOT`（默认 `/home/elf/projects`）、上报间隔宏。

### 三、两链路关系与凭据隔离

- **proxy 路**：请求驱动、面向小程序、HTTP+签名、可本地回退，凭据 `client_secret` 只在设备侧。
- **固件路**：常驻、面向涂鸦 App/云、MQTT 直连、周期上报 + DP 下发执行，凭据 `PID/UUID/AUTHKEY`。
- 两者对同一批 `datas/csv/*.{csv,json}` 与同一套 DP 语义/枚举/scale 一致，涂鸦不可用/直连时都兜底调用**相同的本地硬件脚本**（速度档 0.10/0.13/0.16 m/s 一致），确保云端与本地行为统一。

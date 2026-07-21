# 04 · 语音助手与 YOLO11 深度学习技术文档

本篇覆盖两个子系统：**语音助手**（质检结果语音播报）与**深度学习 / YOLO11 RKNN 推理**（NPU 实时目标检测）。所有阈值、模型名、参数均直接引自源码。

---

## 语音助手

### 概述

语音助手（`voice_assistant`）是质检系统的**语音播报模块**，并非交互式对话助手，而是**单向结果播报器**：读取三模态融合后的芒果质检结果 CSV、历史 CSV 或批次统计 CSV，调用云端大模型 **DeepSeek** 生成一句普通人能听懂的中文口语评价，再交给本机 TTS 播报。云端不可用时自动降级到本地固定模板，保证离线可用。

源码（`src/software/voice_assistant/`）：`voice_assistant.py`、`README.md`、`install_voice_dependencies.sh`、`__init__.py`。

### 架构分层

处理链 5 阶段，**无唤醒词与 ASR**——输入是 CSV 文件而非麦克风语音：

| 阶段 | 实现 | 说明 |
|------|------|------|
| 输入/数据源 | `read_latest_csv_row()` | 读当前质检、历史记录或批次统计 CSV 的最后一条有效行 |
| 意图/有效性 | `is_valid_mango_result()`、`row_identity()` | 判断是否有效芒果、是否新结果 |
| LLM 文本生成 | `deepseek_announcement()`、`deepseek_batch_announcement()` | 调用 DeepSeek Chat Completions API |
| 本地降级 | `local_announcement()`、`local_batch_announcement()` | 云端失败用固定中文模板 |
| TTS 播报 | `speak_text()` | 优先 `edge-tts`，回退 `espeak-ng` / `spd-say` |

调度层 `main()` / `announce_latest()`，支持**单次**与**持续监听（watch）**模式；`--target current|previous|batch` 分别播报当前实时结果、上一条历史单果记录、整批统计。

### 依赖与库

- **核心 Python 代码仅依赖标准库**：`argparse/csv/json/os/shutil/subprocess/sys/time/urllib/pathlib/tempfile`。DeepSeek 调用是手写 `urllib` HTTP POST；`edge-tts` 是可选命令行后端，需单独安装。
- **推荐神经网络 TTS**：`edge-tts`（`python3 -m pip install --user edge-tts`），默认中文声音 `zh-CN-XiaoxiaoNeural`。
- **系统级回退 TTS**（`install_voice_dependencies.sh` 用 apt 装）：`espeak-ng` + `espeak-ng-data`、`speech-dispatcher`（`spd-say`）、`mpv`。安装：`sudo apt-get install -y espeak-ng espeak-ng-data speech-dispatcher mpv`。
- 音频走 **ALSA**（当前用 HDMI 音频，推荐 `plughw:2,0`；板载喇叭用 `plughw:1,0`）。

### 音频 / TTS 管线（`speak_text`）

`speak_text(text, backend="auto", wait=True, dry_run=False, alsa_device="", edge_voice="zh-CN-XiaoxiaoNeural", tts_timeout_s=12)`：
1. `dry_run=True` 只 `print` 不发声。
2. `backend="auto"` 按序尝试 `["edge-tts", "espeak-ng", "spd-say"]`。
3. `shutil.which()` 检查可执行文件。
4. 命令：
   - **edge-tts**：`edge-tts --voice <edge_voice> --text <text> --write-media <tmp.mp3>`，再用 `mpv` 或 `ffplay` 播放；声音自然，但需要联网。
   - **espeak-ng**：未指定 ALSA 设备时直接 `espeak-ng -v zh -s 155 <text>`；指定 `--alsa-device` 时先 `espeak-ng -v zh -s 155 -w <tmp.wav> <text>`，再 `aplay -D <alsa_device> <tmp.wav>`。
   - **spd-say**：`spd-say -l zh-CN -r -10 [-w] <text>`（`wait=True` 加 `-w` 阻塞）。
5. **ALSA 设备**：`edge-tts` 通过 `mpv --audio-device=alsa/<设备>`，`espeak-ng` 通过 `aplay -D <设备>`，来自 `--alsa-device` 或环境变量 `VOICE_ALSA_DEVICE`。
6. 逐后端 `subprocess.run(check=True, timeout=tts_timeout_s)`，全失败抛 `RuntimeError`。`edge-tts` 联网慢或不可达时会超时并回退。

### LLM 文本生成（DeepSeek）

常量：`DEFAULT_MODEL="deepseek-v4-flash"`、`DEFAULT_API_BASE="https://api.deepseek.com"`（端点 `.../chat/completions`）、`DEFAULT_TIMEOUT_S=15`、API Key 取环境变量 `DEEPSEEK_API_KEY`（空则抛错）。

请求体参数：`model="deepseek-v4-flash"`、`thinking={"type":"disabled"}`、`temperature=0.3`、`stream=False`；单果 `max_tokens=120`，批次 `max_tokens=140`。

Prompt：
- **system**：`"你是芒果品质检测设备的语音播报助手。根据检测字段生成一句普通人能听懂的中文播报。要求：不超过45个汉字；语气客观；不要提CSV、模型、算法、置信度；不要编造字段以外的信息。"`
- **user**：把 CSV 行字段打包成 JSON（单果含 `subject/mango_id/quality_grade/maturity_label/maturity_confidence/reference_brix_range/sugar_label/rot_status/final_status/suggested_channel/data_status/reason`；批次含 `total_count/saleable_ratio/reject_count/rot_risk_ratio/channel_*` 等），后接 `"请生成一句现场播报。"`

HTTP 头：`Authorization: Bearer <key>`、`Content-Type: application/json`。响应取 `payload["choices"][0]["message"]["content"]`。

**文本清洗** `sanitize_announcement()`：折叠空白，>80 字符截断到 80 并补 `。`。返回为空则回退本地模板。

### 本地降级模板（`local_announcement`）

单果模板：`"{subject}检测完成，等级{grade}，成熟度{maturity}{sugar_text}，腐烂状况{rot}，建议{channel}。"`
- subject 默认为“当前芒果”，`--target previous` 时为“上一个芒果”；糖度优先 `reference_brix_range`（“，参考糖度{}”）否则 `sugar_label`（“，糖度{}”）。
- 兜底："未评级"/"成熟度未知"/"腐烂情况未知"/"待人工确认"/"检测完成"。

批次模板：`"本批次共N个芒果，可销售X%，剔除Y个，异常风险Z%。"`；若 `total_count<=0`，播报 `"当前批次尚未统计到有效芒果。"`

`build_announcement()` / `build_batch_announcement()`：`use_api=True` 时先试 DeepSeek，异常则打印 fallback 并回退本地；返回 `(text, source)`。

### 意图 / 有效性处理

- `is_valid_mango_result`：`final_status ∈ {"","--","无有效检测"}` 无效；`maturity_label ∈ {"","--","未检测到芒果"}` 无效；否则需 `mango_id` 或 maturity 非空。
- `row_identity`：`mango_id|timestamp|quality_grade|final_status` 拼身份串用于去重（watch 模式仅身份变化才播报）。
- `is_valid_batch_result`：`total_count > 0` 才视为有效批次；`batch_identity` 用 `batch_id|timestamp|total_count|last_mango_id` 去重。
- `read_latest_csv_row`：`csv.DictReader` 保留最后一条任一字段非空的行。

### 配置与命令行参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--quality-csv` | mango_quality_realtime.csv | 主输入 |
| `--history-csv` | mango_quality_history.csv | 上一个芒果输入 |
| `--batch-csv` | mango_batch_summary.csv | 批次统计输入 |
| `--target` | current | current/previous/batch |
| `--text` | `""` | 直接播报指定文字 |
| `--once` / `--watch` | — | 运行一次 / 持续监听 |
| `--interval` | 1.0 | watch 轮询间隔（>0） |
| `--no-api` | — | 仅本地模板 |
| `--model` | deepseek-v4-flash | 模型名 |
| `--api-base` | 环境变量或 api.deepseek.com | API 基址 |
| `--timeout` | 15 | 超时 |
| `--backend` | auto | auto/edge-tts/espeak-ng/spd-say |
| `--edge-voice` | zh-CN-XiaoxiaoNeural | edge-tts 声音 |
| `--tts-timeout` | 12 | TTS 生成/播放超时 |
| `--alsa-device` | 环境变量或 "" | ALSA 输出设备；edge-tts 经 `mpv` 播放、espeak-ng 经 `aplay` 播放时使用 |
| `--dry-run` / `--speak-invalid` | — | 只打印 / 无效结果也播报 |

环境变量：`DEEPSEEK_API_KEY`（联网必需）、`DEEPSEEK_API_BASE`、`VOICE_BACKEND`、`VOICE_EDGE_VOICE`、`VOICE_TTS_TIMEOUT`、`VOICE_ALSA_DEVICE`。

### 运行流程与系统集成

`main()`：`--once` 或未指定 `--watch` → 一次 `announce_latest`；`--watch` → 循环 + `sleep(interval)`。`announce_latest()` 会按 `--target` 路由到当前单果、上一条历史单果或批次统计。

**集成链路**：`camera_detect.py` → `mango_object/vision_color CSV` → `fusion.py` → `mango_quality_realtime.csv`/`mango_quality_history.csv`/`mango_batch_summary.csv` → **Qt“语音评价”按钮或语音助手读取播报**。Qt 侧按钮分别调用 `voice_assistant.py --once --target previous --speak-invalid --backend <后端> --edge-voice <声音> --tts-timeout <秒> --alsa-device <设备> --timeout 5` 与 `voice_assistant.py --once --target batch --speak-invalid --backend <后端> --edge-voice <声音> --tts-timeout <秒> --alsa-device <设备> --timeout 5`；后端优先取 `VOICE_BACKEND`，未设置时为 `edge-tts`，避免回退到机械音；如需网络失败时也能出声可设为 `auto`。设备优先取 `VOICE_ALSA_DEVICE`，未设置时默认 `plughw:2,0`。自动播报当前实时结果仍可用 `--watch` 常驻。

---

## 深度学习与 YOLO11 RKNN 推理

### 概述

在 RK3588 **NPU** 上运行 **YOLO11**（anchor-free）模型，实现摄像头实时芒果检测、跨帧跟踪与颜色特征提取。模型经 INT8 量化并编译为 Rockchip `.rknn`，通过 **rknn-toolkit-lite2 (RKNNLite)** 在 3 个 NPU 核心多线程并行推理。检测结果画框显示、提取每个芒果 ROI 的 RGB/HSV 颜色特征、过线计数跟踪统计完整芒果个体，写入 CSV/JSON 供下游融合模块消费。

生产代码为 `deeplearning/yolo11_demo/`：芒果专用 YOLO11 推理、跟踪、颜色特征与质量对接。

### RKNN 工具链与模型文件

- **rknn-toolkit-lite2 v2.3.2**（2025-04-03，支持 RV1126B）。`packages/` 含 aarch64 cp37–cp312 六个 wheel。
- **用途**：RKNNLite 是板端推理专用轻量运行时（不含转换/量化）；负责 `load_rknn()` 加载、`init_runtime()` 绑核、`inference()` 前向。
- **`.rknn` 模型**（RK3588、INT8 `i8`）：`mango_yolo11_rk3588_i8.rknn`（≈4.21MB，生产芒果模型，YAML 默认）和 `fruits1_yolo11_rk3588_i8.rknn`（通用水果）。
- **`i8` = INT8 量化**：权重/激活 8 位整型，配合 RK3588 NPU INT8 算力（官方标称约 6 TOPS）降低延迟/内存。

### 模型输出结构（芒果模型）

`mango_yolo11_rk3588_i8.rknn` 输出**单 tensor `[1, 7, 8400]`**——4 bbox 通道 + 3 类别通道（无 objectness），8400=80²+40²+20²。对应 `postprocess_yolo11` 分支；demo 的 YOLOv8 走多输出分支。

### 类别标签

`labels.txt`（3 类芒果成熟度）：`mango_unripe`（未成熟）、`mango_ripe`（成熟）、`mango_overripe`（过熟）。`load_labels()` 忽略空行与 `#` 注释；数量不符抛 `ValueError`。与 mango quality 融合模块一致。

### 预处理（letterbox）

`preprocess()`：
1. `cv2.cvtColor(frame, COLOR_BGR2RGB)`。
2. `letterbox(rgb, (img_size, img_size))`，**默认 `img_size=640`**（YAML 一致）。
3. letterbox：`ratio=min(new_h/h, new_w/w)`，两侧对称黑边补齐，`INTER_LINEAR`，`top=round(dh-0.1)`、`bottom=round(dh+0.1)`。
4. 布局：`nchw` 时 `transpose(2,0,1)`；**默认 `nhwc`** 只 `expand_dims`。
5. `rknn.inference(inputs=[tensor], data_format=[input_format])`。

> **未做 /255 归一化**——归一化 mean/std 已在量化阶段固化进 `.rknn`，板端直接喂 0–255 uint8。

### RKNN 推理流水线（单帧 `infer`）

`infer(rknn, frame)`：`preprocess` → `rknn.inference` → `postprocess_auto` → 首帧生成默认标签 → `extract_color_features` → `draw_detections`（在 `frame.copy()`） → 返回 `(annotated_frame, len(scores), color_features)`。

### 多核 NPU 线程池设计（`rknn_pool.py`）

RK3588 有 **3 个 NPU 核心**（NPU_CORE_0/1/2）。创建多个 RKNNLite 实例各绑不同核，线程池异步提交、队列保序取回，实现边采集边推理隐藏延迟。

- `_core_mask(index)`：`masks[index % 3]` → CORE_0/1/2。
- `init_rknn(model_path, index)`：`RKNNLite()` → `load_rknn()` → `init_runtime(core_mask=...)`；`index<0` 用 `NPU_CORE_0_1_2`（三核合一）。
- `RKNNPoolExecutor(model_path, workers, infer_func)`：创建 `workers` 个实例（worker 0→CORE_0，1→CORE_1，2→CORE_2）；`ThreadPoolExecutor(max_workers=workers)`；`_queue=Queue()` FIFO 保序。
  - `put(frame)`：轮询实例 `_rknns[_submit_count % workers]`，`pool.submit(infer_func, rknn, frame)` 入队。
  - `get()`：队空 `(None, False)`；否则 `queue.get().result()` 保序取回 `(result, True)`。
  - `release()`：`pool.shutdown(wait=True)` 后逐个 `rknn.release()`。
- **默认 workers=3**（YAML）。

### YOLO11 后处理（anchor-free 解码 + NMS）

`postprocess_auto()` 按输出数量分派：单输出→`postprocess_yolo11`；多输出（3 的倍数）→`postprocess_split_yolo`（DFL）。

**`postprocess_yolo11`（芒果单输出）**：
- `normalize_yolo_output`：转 float32，若 `shape[0]<shape[1]` 转置为 `[8400,7]`。
- **anchor-free 解码**：`has_objectness=False` 时 `boxes_xywh=pred[:,:4]`，`class_scores=pred[:,4:]`，`scores=max(axis=1)`，`class_ids=argmax`。`apply_sigmoid=False`——分数已是概率。
- 过滤 `keep = scores >= conf_threshold`；`xywh_to_xyxy`；`scale_boxes`（减 padding、除 ratio、clip）。
- `pre_nms_topk` 在 NMS 前只保留最高分候选框，防止候选框过多时 CPU 贪心 NMS 拖慢 NPU 流水线。
- **按类别分组 NMS**（类内抑制，类间不互相抑制）；排序取前 `max_det`。

**`box_process`/`dfl`（DFL 解码）**：`dfl` reshape `(n,4,mc,h,w)` 在 axis=2 softmax（减 max 稳定）× `arange(mc)` 求期望；`box_process` 用 `meshgrid`，`stride=img_size//grid`，`box_xy=grid+0.5∓dfl` × stride。

**`nms`**：标准贪心 NMS，按 score 降序保留最高、抑制 IoU>阈值者。

**阈值（多来源）**：
- 代码默认：`conf_threshold=0.25`、`iou_threshold=0.45`、`max_det=100`、`pre_nms_topk=1000`。
- **YAML 生产（实际生效）**：`conf=0.7`、`iou=0.45`、`max_det=100`、`pre_nms_topk=1000`。芒果生产用 **conf=0.7**（比默认严格，减少误检）。
- demo：`OBJ_THRESH, NMS_THRESH, IMG_SIZE = 0.25, 0.45, 640`，score 用 `class_max_score * box_confidences`。

### 颜色特征提取（feed 质量系统）

`extract_color_features(image, boxes, class_ids, scores, labels)` 裁 ROI（坐标 clip 防越界），优先调 `src.software.mango_quality.color_features.extract_mango_color_features_from_bgr_roi(roi)`（顶部 try-import，失败用内置简化版）。

特征（见 [03-芒果质检核心算法.md](03-芒果质检核心算法.md)）：`rgb_r/g/b_mean`、`hsv_h_mean_deg`（H×2）、`hsv_s/v_mean_pct`、`green_ratio`（H35–95,S≥20）、`yellow_orange_ratio`（H8–38,S≥25）、`dark_spot_ratio`（V<28 或 RGB<65）、`brown_area_ratio`（H8–42,S≥18,V≤55,R≥G≥B）；有效像素门限 `S>12 & V>10`。每个特征字典含 `detection_id/label/confidence/x1..y2/area_px`。

### 芒果跟踪与过线计数（`camera_detect.py`）

`MangoTracker`/`MangoTrack` 把逐帧检测汇聚成“单个物理芒果”稳定结论：

- **两条虚拟线**：进入线 `enter_line_ratio=0.20`、计数线 `count_line_ratio=0.75`。
- **数据关联** `_match_score`：中心点位移（`max_dx=max(60,W*0.18)`、`max_dy=max(80,H*0.22)`）、面积比（0.30–3.20）、IoU 综合，要求向下运动（传送带场景），贪心最小分匹配。
- **稳定性**：`track_min_frames=4`、`track_max_missed=6`；每 track 最多保留 40 样本。
- **计数触发**：`prev_center_y < count_line_y ≤ center_y` 且样本≥min_frames 且已越进入线 → `counted=True`、`completed_count+=1`。
- **多帧融合** `summary()`：`_vote_label` 置信度加权投票 + 一致性分；`_consistency_label`：≥0.80 高、≥0.60 中、否则低。颜色特征取样本均值。

### 输出与数据流

主循环原子写（`.tmp`+`os.replace`）：
1. **逐帧颜色 CSV** `vision_color_realtime.csv`（每 `color_log_interval=5` 帧写一次，`COLOR_CSV_FIELDS`）。
2. **完成对象** `mango_object_realtime.csv/.json`（芒果跨计数线时写，`OBJECT_CSV_FIELDS`，含 `mango_id/track_id/stable_frames/consistency_score/label` 与聚合颜色）。

**完整链路**：`camera_detect.py` → vision/object CSV → `fusion.py`（`read_latest_vision`/`read_latest_object` + 光谱）→ `mango_quality_realtime.csv` → **语音助手播报**。fusion 输出字段正是语音助手 prompt 与本地模板消费的字段，闭环。

### 显示、Qt 嵌入与 FPS 优化

主循环用 `RKNNPoolExecutor` 预热（先 `put` `workers+1` 帧），叠加 FPS/检测数/计数 HUD。三种输出：OpenCV 窗口、`--no-display` 无头、`--qt-stream`（标注帧编码为**4 字节大端长度前缀 JPEG** `struct.pack(">I",len)` 写 stdout 供 Qt 内嵌，`--jpeg-quality` 默认 82，clamp 30–95）。支持 `--parent-pid`、SIGTERM/SIGINT 优雅停止、X11 `DISPLAY`/`XAUTHORITY` 自动配置。

**FPS 优化技术**：
1. INT8 量化模型（i8）——NPU 高吞吐低内存。
2. 三 NPU 核并行 + 线程池异步流水线，采集与推理重叠。
3. letterbox 等比缩放 640 + `INTER_LINEAR`，尺寸固定利于 NPU。
4. nhwc 直喂、免归一化，减少 CPU 预处理。
5. 向量化 NumPy 后处理（DFL softmax 稳定、按类 NMS）。
6. 显示解耦：`--qt-stream` 只向 Qt 输出 4 字节长度头 + JPEG 帧，`--jpeg-quality` 默认 82（限制 30–95），避免 OpenCV 窗口与 Qt 嵌入互相耦合。
7. 颜色特征每 5 帧落盘、结果原子写，减少 IO 抢占。

### 相机配置（`yolo11.yaml`）

- 摄像头源 `/dev/video21`。
- `yolo11.yaml`：`model=mango_yolo11_rk3588_i8.rknn`、`labels=labels.txt`、`camera=/dev/video21`、`img_size:640`、`conf:0.7`、`iou:0.45`、`workers:3`、`max_det:100`、`pre_nms_topk:1000`、`input_format:nhwc`、`objectness:false`、`sigmoid:false`、`width/height/fps:0`、`display=":0"`、`xauthority=/run/user/1000/gdm/Xauthority`、`window=yolo11_rknn_camera`。命令行覆盖 YAML，YAML 覆盖 DEFAULTS。

> **注意**：`conf` 阈值代码默认 0.25，但生产 YAML 用 0.7，运行时以 YAML/命令行为准。

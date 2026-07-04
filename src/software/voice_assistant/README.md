# Voice Assistant

芒果检测语音播报模块。模块读取三模态融合结果、历史记录或批次统计 CSV，调用 DeepSeek 生成一句普通人能听懂的中文评价，再交给本机 TTS 播报。

## Install

```bash
sudo apt-get update
sudo apt-get install -y espeak-ng espeak-ng-data speech-dispatcher
python3 -m pip install --user edge-tts
```

推荐安装 `edge-tts`，中文声音比 `espeak-ng` 自然；如果只验证 DeepSeek 文本生成，不需要先安装语音后端。

## API Key

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
```

默认 API 地址：

```bash
https://api.deepseek.com/chat/completions
```

默认模型：

```bash
deepseek-v4-flash
```

## Usage

只生成文字，不播报：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --once --dry-run
```

评价上一个已检测芒果：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --once --target previous
```

评价整批芒果：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --once --target batch
```

不调用 DeepSeek，使用本地模板生成播报：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --once --no-api
```

持续监听最新检测结果，新芒果出现时播报：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --watch
```

直接播报一段文字：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --text "语音模块测试成功"
```

使用更自然的神经网络中文语音：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --text "语音模块测试成功" --backend edge-tts --tts-timeout 12
```

如果默认设备没有声音，可以指定 ALSA 设备。当前项目使用 HDMI 音频，推荐：

```bash
export VOICE_ALSA_DEVICE="plughw:2,0"
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --text "语音模块测试成功" --backend espeak-ng
```

指定 `--alsa-device` 后，脚本会先用 `espeak-ng` 生成临时 WAV，再用 `aplay -D <设备>` 播放，便于明确选中 HDMI/喇叭声卡并暴露播放错误。

也可以先用 ALSA 测试扬声器：

```bash
speaker-test -D hw:2,0 -c 2 -t sine -f 800 -l 1
aplay -D plughw:2,0 /usr/share/sounds/alsa/Front_Center.wav
```

如果改用板载 3.5mm/喇叭输出，再切回 `plughw:1,0`。

## Qt Integration

Qt 功能区的“语音评价”页面会按按钮调用：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --once --target previous --speak-invalid --timeout 5
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --once --target batch --speak-invalid --timeout 5
```

Qt 会额外传入 `--backend <后端> --edge-voice <声音> --tts-timeout <秒> --alsa-device <设备>`；后端优先取 `VOICE_BACKEND`，未设置时为 `edge-tts`，避免回退到机械音。声音优先取 `VOICE_EDGE_VOICE`，默认 `zh-CN-XiaoxiaoNeural`；TTS 超时优先取 `VOICE_TTS_TIMEOUT`，默认 12 秒；设备优先取 `VOICE_ALSA_DEVICE`，未设置时默认 `plughw:2,0`。如果现场需要网络失败时也能出声，可设 `VOICE_BACKEND=auto`，自动顺序是 `edge-tts → espeak-ng → spd-say`。

如果仍需要自动播报当前实时检测结果，可在开始检测时启动：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --watch
```

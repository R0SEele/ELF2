# Voice Assistant

芒果检测语音播报模块。模块读取三模态融合结果 CSV，调用 DeepSeek 生成一句普通人能听懂的中文评价，再交给本机 TTS 播报。

## Install

```bash
sudo apt-get update
sudo apt-get install -y espeak-ng espeak-ng-data speech-dispatcher
```

如果只验证 DeepSeek 文本生成，不需要先安装语音后端。

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

如果默认设备没有声音，可以指定 ALSA 设备。当前项目使用 HDMI 音频，推荐：

```bash
export VOICE_ALSA_DEVICE="plughw:2,0"
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --text "语音模块测试成功" --backend espeak-ng
```

也可以先用 ALSA 测试扬声器：

```bash
speaker-test -D hw:2,0 -c 2 -t sine -f 800 -l 1
aplay -D plughw:2,0 /usr/share/sounds/alsa/Front_Center.wav
```

如果改用板载 3.5mm/喇叭输出，再切回 `plughw:1,0`。

## Qt Integration

后续 Qt 中可在单个芒果检测完成后调用：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --once
```

如果需要批量模式，建议在开始检测时启动：

```bash
python3 /home/elf/projects/src/software/voice_assistant/voice_assistant.py --watch
```

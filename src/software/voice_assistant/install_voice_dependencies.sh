#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found. Please install espeak-ng and speech-dispatcher manually." >&2
    exit 1
fi

sudo apt-get update
sudo apt-get install -y espeak-ng espeak-ng-data speech-dispatcher mpv
python3 -m pip install --user edge-tts

echo "Voice dependencies installed."
echo "Set DeepSeek key before API use:"
echo 'export DEEPSEEK_API_KEY="your_api_key"'
echo "Recommended neural TTS backend:"
echo 'export VOICE_BACKEND="edge-tts"'

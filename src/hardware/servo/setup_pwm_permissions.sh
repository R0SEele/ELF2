#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${1:-/home/elf/projects/config/servo.yaml}"
USER_NAME="${SUDO_USER:-${USER:-elf}}"

read_pwm_field() {
    local field="$1"
    local fallback="$2"
    python3 - "$CONFIG_FILE" "$field" "$fallback" <<'PY'
import sys
import yaml

config_path, field, fallback = sys.argv[1:4]
try:
    with open(config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    value = data.get("servo", {}).get("pwm", {}).get(field, fallback)
except Exception:
    value = fallback
print(value)
PY
}

PWM_CHIP="$(read_pwm_field chip 0)"
PWM_CHANNEL="$(read_pwm_field channel 0)"
PWM_BASE="$(read_pwm_field base_path /sys/class/pwm)"
PWM_CHIP_PATH="${PWM_BASE}/pwmchip${PWM_CHIP}"
PWM_PATH="${PWM_CHIP_PATH}/pwm${PWM_CHANNEL}"

if [[ ! -d "$PWM_CHIP_PATH" ]]; then
    echo "PWM chip not found: $PWM_CHIP_PATH" >&2
    exit 1
fi

if [[ ! -d "$PWM_PATH" ]]; then
    echo "$PWM_CHANNEL" > "${PWM_CHIP_PATH}/export" || true
    for _ in $(seq 1 100); do
        [[ -d "$PWM_PATH" ]] && break
        sleep 0.01
    done
fi

if [[ ! -d "$PWM_PATH" ]]; then
    echo "PWM channel export failed: $PWM_PATH" >&2
    exit 1
fi

chown "$USER_NAME:$USER_NAME" \
    "${PWM_PATH}/period" \
    "${PWM_PATH}/duty_cycle" \
    "${PWM_PATH}/enable" \
    "${PWM_PATH}/polarity" 2>/dev/null || true

chmod u+rw \
    "${PWM_PATH}/period" \
    "${PWM_PATH}/duty_cycle" \
    "${PWM_PATH}/enable" \
    "${PWM_PATH}/polarity" 2>/dev/null || true

echo "PWM permission ready: ${PWM_PATH} user=${USER_NAME}"

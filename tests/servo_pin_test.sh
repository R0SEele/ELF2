#!/usr/bin/env bash
# Sweep a standard 50Hz servo signal on one PWM chip to find which physical
# pin the servo is actually wired to. Export needs root, so run with sudo:
#   sudo bash tests/servo_pin_test.sh 1
#   sudo bash tests/servo_pin_test.sh 2
# Whichever chip makes the servo swing is the one to put in config/servo.yaml.
# 用 sudo 逐个测试 PWM 路;哪个让舵机来回摆动,就把 servo.yaml 的 chip 改成它。
set -u

chip="${1:?usage: sudo bash servo_pin_test.sh <chip-number>}"
base="/sys/class/pwm/pwmchip${chip}/pwm0"
chipdir="/sys/class/pwm/pwmchip${chip}"

[ -d "$chipdir" ] || { echo "pwmchip${chip} does not exist"; exit 1; }
[ -d "$base" ] || echo 0 > "${chipdir}/export"
sleep 0.2

echo 20000000 > "${base}/period"        # 20 ms period = 50 Hz
echo 1        > "${base}/enable"
echo "sweeping pwmchip${chip} (watch the servo)..."
for _ in 1 2 3 4; do
  echo 500000  > "${base}/duty_cycle"; sleep 0.6   # ~0 deg
  echo 2500000 > "${base}/duty_cycle"; sleep 0.6   # ~180 deg
done
echo 1500000 > "${base}/duty_cycle"; sleep 0.4     # center
echo 0       > "${base}/enable"
echo "done. If the servo moved on pwmchip${chip}, set 'chip: ${chip}' in config/servo.yaml."

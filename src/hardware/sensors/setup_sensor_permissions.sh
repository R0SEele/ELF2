#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${1:-${SUDO_USER:-$USER}}"
RULE_FILE="/etc/udev/rules.d/99-elf-hardware-permissions.rules"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "请使用 sudo 运行：sudo $0 [用户名]" >&2
    exit 1
fi

if ! id "${TARGET_USER}" >/dev/null 2>&1; then
    echo "用户不存在：${TARGET_USER}" >&2
    exit 1
fi

for group in i2c spi gpio pwm; do
    if ! getent group "${group}" >/dev/null; then
        groupadd --system "${group}"
    fi
done

usermod -aG i2c,spi,gpio,pwm,dialout,video,input "${TARGET_USER}"

cat > "${RULE_FILE}" <<'EOF'
# ELF hardware permissions for Qt environment display and control.
SUBSYSTEM=="i2c-dev", GROUP="i2c", MODE="0660"
KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"

# SARADC / MQ135 IIO node. The driver also exposes readable sysfs files,
# but the character node is locked down by default on some images.
SUBSYSTEM=="iio", GROUP="i2c", MODE="0660"
KERNEL=="iio:device*", GROUP="i2c", MODE="0660"

# WS2812B LED strip on SPI4 MOSI.
SUBSYSTEM=="spidev", GROUP="spi", MODE="0660"
KERNEL=="spidev[0-9]*.[0-9]*", GROUP="spi", MODE="0660"

# GPIO character devices for future hardware controls.
SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"
KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"

# PWM sysfs devices for servo/LED helpers on images that expose PWM through sysfs.
SUBSYSTEM=="pwm", GROUP="pwm", MODE="0660"

# Motor/serial helpers use ttyS9; keep this explicit for images without dialout defaults.
KERNEL=="ttyS[0-9]*", GROUP="dialout", MODE="0660"
KERNEL=="ttyUSB[0-9]*", GROUP="dialout", MODE="0660"
KERNEL=="ttyACM[0-9]*", GROUP="dialout", MODE="0660"
EOF

udevadm control --reload-rules
udevadm trigger --subsystem-match=i2c-dev || true
udevadm trigger --subsystem-match=iio || true
udevadm trigger --subsystem-match=spidev || true
udevadm trigger --subsystem-match=gpio || true
udevadm trigger --subsystem-match=pwm || true
udevadm trigger --subsystem-match=tty || true

# Apply immediately for already-created nodes; udev will keep it persistent after reboot.
chgrp i2c /dev/i2c-* 2>/dev/null || true
chmod 0660 /dev/i2c-* 2>/dev/null || true
chgrp i2c /dev/iio:device* 2>/dev/null || true
chmod 0660 /dev/iio:device* 2>/dev/null || true
chgrp spi /dev/spidev* 2>/dev/null || true
chmod 0660 /dev/spidev* 2>/dev/null || true
chgrp gpio /dev/gpiochip* 2>/dev/null || true
chmod 0660 /dev/gpiochip* 2>/dev/null || true

echo "已安装硬件权限规则：${RULE_FILE}"
echo "已将 ${TARGET_USER} 加入 i2c/spi/gpio/pwm/dialout/video/input 组。"
echo "请注销并重新登录，或重启系统，使新增用户组对 Qt 生效。"

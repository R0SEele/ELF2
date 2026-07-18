#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import os
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "led.yaml"


class WS2812BError(Exception):
    pass


SPI_IOC_WR_MODE = 0x40016B01
SPI_IOC_WR_BITS_PER_WORD = 0x40016B03
SPI_IOC_WR_MAX_SPEED_HZ = 0x40046B04


def _load_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
            return data.get("led", {}).get("ws2812b", {})
    except FileNotFoundError:
        return {}


def _clamp_pct(value):
    return max(0.0, min(100.0, float(value)))


def _write_state(state_file, brightness_pct, enabled):
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("enabled", "brightness_pct"))
        writer.writeheader()
        writer.writerow(
            {
                "enabled": 1 if enabled else 0,
                "brightness_pct": "{:.1f}".format(brightness_pct),
            }
        )


def _expand_byte(value, bit0_pattern, bit1_pattern):
    bits = []
    for bit in range(7, -1, -1):
        bits.extend(bit1_pattern if (value & (1 << bit)) else bit0_pattern)
    return bits


def _pack_bits(bits):
    output = bytearray()
    current = 0
    used = 0
    for bit in bits:
        current = (current << 1) | (1 if bit else 0)
        used += 1
        if used == 8:
            output.append(current)
            current = 0
            used = 0

    if used:
        output.append(current << (8 - used))

    return output


def _scale_channel(value, gain):
    return max(0, min(255, int(round(value * _clamp_gain(gain)))))


def _clamp_gain(value):
    return max(0.0, min(1.0, float(value)))


def _white_frame(count, value, color_order, bit0_pattern, bit1_pattern, white_balance=None):
    wb = white_balance or {}
    channels = {
        "R": _scale_channel(value, wb.get("r", 1.0)),
        "G": _scale_channel(value, wb.get("g", 1.0)),
        "B": _scale_channel(value, wb.get("b", 1.0)),
    }
    bits = []
    for _ in range(count):
        for channel in color_order:
            bits.extend(_expand_byte(channels[channel], bit0_pattern, bit1_pattern))
    # A low reset interval longer than 50 us. Extra zero bytes are safe on MOSI.
    bits.extend([0] * 240)
    return _pack_bits(bits)


def _parse_pattern(pattern, name):
    if not pattern or any(ch not in "01" for ch in pattern):
        raise WS2812BError(f"{name} must be a binary string")
    return [1 if ch == "1" else 0 for ch in pattern]


def _apply_white(cfg, brightness_pct, enabled, count_override=None):
    count = int(cfg.get("count", 24) if count_override is None else count_override)
    device = str(cfg.get("device", "/dev/spidev4.0"))
    spi_speed_hz = int(cfg.get("spi_speed_hz", 2400000))
    bit0_pattern = _parse_pattern(str(cfg.get("bit0_pattern", "100")), "bit0_pattern")
    bit1_pattern = _parse_pattern(str(cfg.get("bit1_pattern", "110")), "bit1_pattern")
    color_order = str(cfg.get("color_order", "GRB")).upper()
    white_balance = cfg.get("white_balance") or {}
    max_brightness_pct = _clamp_pct(cfg.get("max_brightness_pct", 100))
    if count <= 0:
        raise WS2812BError("count must be > 0")
    if sorted(color_order) != ["B", "G", "R"]:
        raise WS2812BError("color_order must contain R, G and B once")
    if not Path(device).exists():
        raise WS2812BError(f"SPI device not found: {device}")

    brightness_pct = _clamp_pct(brightness_pct)
    brightness_pct = min(brightness_pct, max_brightness_pct)
    value = int(round(255.0 * brightness_pct / 100.0)) if enabled else 0
    value = max(0, min(255, value))

    frame = _white_frame(count, value, color_order, bit0_pattern, bit1_pattern, white_balance)
    fd = None
    try:
        fd = os.open(device, os.O_WRONLY)
        fcntl.ioctl(fd, SPI_IOC_WR_MODE, bytes([0]))
        fcntl.ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, bytes([8]))
        fcntl.ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, int(spi_speed_hz).to_bytes(4, "little"))
        written = 0
        while written < len(frame):
            written += os.write(fd, frame[written:])
    except PermissionError as exc:
        raise WS2812BError(f"no permission to access {device}") from exc
    except OSError as exc:
        raise WS2812BError(f"SPI write failed on {device}: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(description="Control a WS2812B strip as white-only light")
    parser.add_argument("command", choices=("set", "off"))
    parser.add_argument("--brightness", type=float, default=None, help="Brightness percent, 0~100")
    parser.add_argument("--count", type=int, default=None, help="Override LED count for this command")
    args = parser.parse_args()

    try:
        cfg = _load_config()
        default_brightness = float(cfg.get("default_brightness_pct", 40))
        state_file = cfg.get("state_file", str(PROJECT_ROOT / "datas" / "csv" / "led_state.csv"))

        enabled = args.command == "set"
        brightness_pct = default_brightness if args.brightness is None else args.brightness
        brightness_pct = _clamp_pct(brightness_pct)
        if not enabled:
            brightness_pct = 0.0

        _apply_white(cfg, brightness_pct, enabled, count_override=args.count)
        _write_state(state_file, brightness_pct, enabled)
        print("enabled={} brightness={:.1f}%".format(int(enabled), brightness_pct))
        return 0
    except Exception as exc:
        print(f"ws2812b error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

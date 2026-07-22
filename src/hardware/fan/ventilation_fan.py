#!/usr/bin/env python3
"""Control the ventilation fan connected to RK3588 GPIO3_B3."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

try:
    import gpiod
except ImportError:  # Keep status/automatic decision logic usable without GPIO packages.
    gpiod = None


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "fan.yaml"
DEFAULT_STATE_PATH = PROJECT_ROOT / "datas" / "csv" / "tuya_proxy_control_state.json"
DEFAULT_SENSOR_PATH = PROJECT_ROOT / "datas" / "csv" / "sensor_realtime.csv"

DEFAULT_STATE: dict[str, Any] = {
    "fan_switch": False,
    "fan_auto_enable": False,
    "fan_temperature_threshold": 30,
    "fan_humidity_threshold": 75,
    "fan_auto_reason": "手动模式",
}


class FanControlError(RuntimeError):
    """Raised when the fan GPIO cannot be controlled or configuration is invalid."""


def load_config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return (yaml.safe_load(handle) or {}).get("fan", {}) or {}
    except FileNotFoundError as exc:
        raise FanControlError(f"Fan config not found: {CONFIG_PATH}") from exc
    except yaml.YAMLError as exc:
        raise FanControlError(f"Fan config parse error: {exc}") from exc


def _state_path(config: dict[str, Any]) -> Path:
    return Path(str(config.get("state_file", DEFAULT_STATE_PATH)))


def _sensor_path(config: dict[str, Any]) -> Path:
    return Path(str(config.get("sensor_file", DEFAULT_SENSOR_PATH)))


def read_state(path: Path) -> dict[str, Any]:
    state = dict(DEFAULT_STATE)
    try:
        with path.open("r", encoding="utf-8") as handle:
            saved = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        saved = {}
    if isinstance(saved, dict):
        state.update({key: saved[key] for key in DEFAULT_STATE if key in saved})
    return state


def update_state(path: Path, patch: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    state.update(patch)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return state


def _gpio_level(logical_on: bool, active_high: bool) -> int:
    return int(logical_on if active_high else not logical_on)


def set_gpio(enabled: bool, config: dict[str, Any]) -> None:
    if not config.get("enabled", True):
        raise FanControlError("Fan GPIO control is disabled in config")
    if gpiod is None:
        raise FanControlError("python3-gpiod is not installed")

    chip_path = str(config.get("chip", "/dev/gpiochip3"))
    line_offset = int(config.get("line_offset", 11))
    consumer = str(config.get("consumer", "fruit-quality-ventilation-fan"))
    active_high = bool(config.get("active_high", True))
    chip = None
    line = None
    try:
        chip = gpiod.Chip(chip_path)
        line = chip.get_line(line_offset)
        line.request(
            consumer=consumer,
            type=gpiod.LINE_REQ_DIR_OUT,
            default_vals=[_gpio_level(enabled, active_high)],
        )
        line.set_value(_gpio_level(enabled, active_high))
    except (OSError, ValueError, TypeError) as exc:
        gpio_name = config.get("gpio_name", "GPIO3_B3")
        raise FanControlError(f"Unable to set {gpio_name} on {chip_path}:{line_offset}: {exc}") from exc
    finally:
        if line is not None:
            try:
                line.release()
            except OSError:
                pass
        if chip is not None:
            close = getattr(chip, "close", None)
            if close is not None:
                close()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def latest_sensor_values(path: Path) -> tuple[float | None, float | None]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (FileNotFoundError, OSError, csv.Error):
        return None, None
    if not rows:
        return None, None
    row = rows[-1]
    return _number(row.get("temperature_c")), _number(row.get("humidity_rh"))


def thresholds(config: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    auto = config.get("auto", {}) or {}
    temperature_on = _number(state.get("fan_temperature_threshold"))
    humidity_on = _number(state.get("fan_humidity_threshold"))
    temperature_on = temperature_on if temperature_on is not None else float(auto.get("temperature_on_c", 30.0))
    humidity_on = humidity_on if humidity_on is not None else float(auto.get("humidity_on_rh", 75.0))
    temperature_off = float(auto.get("temperature_off_c", temperature_on - 1.0))
    humidity_off = float(auto.get("humidity_off_rh", humidity_on - 3.0))
    return {
        "temperature_on": temperature_on,
        "humidity_on": humidity_on,
        "temperature_off": min(temperature_off, temperature_on),
        "humidity_off": min(humidity_off, humidity_on),
    }


def automatic_control(config: dict[str, Any], temperature: float | None = None,
                      humidity: float | None = None) -> dict[str, Any] | None:
    state_path = _state_path(config)
    state = read_state(state_path)
    if not bool(state.get("fan_auto_enable")):
        return None

    if temperature is None or humidity is None:
        temperature, humidity = latest_sensor_values(_sensor_path(config))
    if temperature is None and humidity is None:
        update_state(state_path, {"fan_auto_reason": "自动模式，等待环境数据"})
        return None

    limit = thresholds(config, state)
    current = bool(state.get("fan_switch"))
    temperature_high = temperature is not None and temperature >= limit["temperature_on"]
    humidity_high = humidity is not None and humidity >= limit["humidity_on"]
    temperature_low = temperature is not None and temperature <= limit["temperature_off"]
    humidity_low = humidity is not None and humidity <= limit["humidity_off"]

    if current:
        enabled = not (temperature_low and humidity_low)
    else:
        enabled = temperature_high or humidity_high

    reasons = []
    if temperature_high:
        reasons.append(f"温度 {temperature:.1f}℃ >= {limit['temperature_on']:.1f}℃")
    if humidity_high:
        reasons.append(f"湿度 {humidity:.1f}%RH >= {limit['humidity_on']:.1f}%RH")
    reason = "、".join(reasons) if enabled and reasons else ("环境已恢复" if not enabled else "自动通风")
    if enabled != current:
        set_gpio(enabled, config)
    update_state(state_path, {"fan_switch": enabled, "fan_auto_reason": reason})
    return {
        "enabled": enabled,
        "temperature": temperature,
        "humidity": humidity,
        "reason": reason,
        "thresholds": limit,
    }


def manual_control(enabled: bool, config: dict[str, Any]) -> None:
    set_gpio(enabled, config)
    update_state(_state_path(config), {
        "fan_switch": enabled,
        "fan_auto_enable": False,
        "fan_auto_reason": "手动开启" if enabled else "手动关闭",
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Control ventilation fan on GPIO3_B3")
    parser.add_argument("command", choices=("on", "off", "auto", "status"))
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--humidity", type=float, default=None)
    args = parser.parse_args()

    try:
        config = load_config()
        if args.command == "status":
            print(json.dumps(read_state(_state_path(config)), ensure_ascii=False))
        elif args.command == "on":
            manual_control(True, config)
            print("fan on")
        elif args.command == "off":
            manual_control(False, config)
            print("fan off")
        else:
            result = automatic_control(config, args.temperature, args.humidity)
            if result is not None:
                print(json.dumps(result, ensure_ascii=False))
        return 0
    except (FanControlError, OSError, ValueError) as exc:
        print(f"fan control error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

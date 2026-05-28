#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

try:
    from .controller import ZDTMotorController
    from .serial_bus import SerialConfig
except ImportError:
    from controller import ZDTMotorController
    from serial_bus import SerialConfig


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "motor.yaml"
MIN_SPEED_MS = 0.1
MAX_SPEED_MS = 0.5


class ConveyorCommandError(Exception):
    pass


def _read_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return (yaml.safe_load(handle) or {}).get("motor", {})
    except FileNotFoundError as exc:
        raise ConveyorCommandError(f"config not found: {CONFIG_PATH}") from exc


def _to_int_addr(value):
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _speed_ms_to_rpm(speed_ms, conveyor_cfg):
    if "rpm_per_ms" in conveyor_cfg:
        return speed_ms * float(conveyor_cfg["rpm_per_ms"])
    if "roller_diameter_m" in conveyor_cfg:
        diameter = float(conveyor_cfg["roller_diameter_m"])
        if diameter <= 0:
            raise ConveyorCommandError("roller_diameter_m must be > 0")
        return speed_ms * 60.0 / (3.141592653589793 * diameter)

    min_rpm = float(conveyor_cfg.get("min_speed_rpm", 10.0))
    max_rpm = float(conveyor_cfg.get("max_speed_rpm", 2000.0))
    ratio = (speed_ms - MIN_SPEED_MS) / (MAX_SPEED_MS - MIN_SPEED_MS)
    return min_rpm + ratio * (max_rpm - min_rpm)


def _make_controller(cfg):
    serial_cfg = cfg.get("serial", {})
    driver_cfg = cfg.get("driver", {})

    return ZDTMotorController(
        address=_to_int_addr(driver_cfg.get("address", "0x01")),
        serial_config=SerialConfig(
            port=str(serial_cfg.get("port", "/dev/ttyS9")),
            baudrate=int(serial_cfg.get("baudrate", 115200)),
            timeout_s=float(serial_cfg.get("timeout_s", 0.8)),
            write_timeout_s=float(serial_cfg.get("write_timeout_s", 0.8)),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Single-shot conveyor command for Qt UI")
    parser.add_argument("command", choices=("forward", "reverse", "stop"))
    parser.add_argument("--speed-ms", type=float, default=0.3, help="Conveyor speed, 0.1 to 0.5 m/s")
    args = parser.parse_args()

    try:
        cfg = _read_config()
        driver_cfg = cfg.get("driver", {})
        kctrl_cfg = cfg.get("kctrl", {})
        conveyor_cfg = cfg.get("conveyor", {})

        sync = int(driver_cfg.get("sync", 0))
        wait_ack = bool(kctrl_cfg.get("wait_ack", False))
        accel = int(kctrl_cfg.get("accel", 10))
        forward_direction = int(kctrl_cfg.get("forward_direction", 0))
        reverse_direction = int(kctrl_cfg.get("reverse_direction", 1))
        min_rpm = float(kctrl_cfg.get("min_speed_rpm", 10.0))
        max_rpm = float(kctrl_cfg.get("max_speed_rpm", 2000.0))

        speed_ms = _clamp(args.speed_ms, MIN_SPEED_MS, MAX_SPEED_MS)
        speed_rpm = _clamp(_speed_ms_to_rpm(speed_ms, conveyor_cfg or kctrl_cfg), min_rpm, max_rpm)

        ctrl = _make_controller(cfg)
        try:
            if args.command == "stop":
                ctrl.stop(wait_ack=wait_ack)
                try:
                    ctrl.enable(False, sync=sync, wait_ack=False)
                except Exception:
                    pass
                print("stopped")
                return 0

            ctrl.enable(True, sync=sync, wait_ack=wait_ack)
            ctrl.run_speed(
                direction=forward_direction if args.command == "forward" else reverse_direction,
                speed_rpm=speed_rpm,
                accel=accel,
                sync=sync,
                wait_ack=wait_ack,
            )
            print(f"{args.command} speed={speed_ms:.1f}m/s rpm={speed_rpm:.1f}")
            return 0
        finally:
            ctrl.close()
    except Exception as exc:
        print(f"conveyor command error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

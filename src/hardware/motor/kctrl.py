#!/usr/bin/env python3

from __future__ import annotations

import sys
import termios
import tty
from pathlib import Path

import yaml

try:
    from .controller import ZDTMotorController
    from .serial_bus import SerialConfig
except ImportError:
    from controller import ZDTMotorController
    from serial_bus import SerialConfig


def _resolve_config_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "config" / "motor.yaml"
        if candidate.exists():
            return candidate
    # Fallback to project-root style path.
    return current.parents[3] / "config" / "motor.yaml"


CONFIG_PATH = _resolve_config_path()


class KeyboardControllerError(Exception):
    pass


def _read_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
            return data.get("motor", {})
    except FileNotFoundError as exc:
        raise KeyboardControllerError(f"config not found: {CONFIG_PATH}") from exc


def _to_int_addr(value):
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def _getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    cfg = _read_config()
    serial_cfg = cfg.get("serial", {})
    driver_cfg = cfg.get("driver", {})
    kctrl_cfg = cfg.get("kctrl", {})

    port = str(serial_cfg.get("port", "/dev/ttyS9"))
    baudrate = int(serial_cfg.get("baudrate", 115200))
    timeout_s = float(serial_cfg.get("timeout_s", 0.8))
    write_timeout_s = float(serial_cfg.get("write_timeout_s", 0.8))

    addr = _to_int_addr(driver_cfg.get("address", "0x01"))
    sync = int(driver_cfg.get("sync", 0))

    speed_rpm = float(kctrl_cfg.get("default_speed_rpm", 100.0))
    speed_step_rpm = float(kctrl_cfg.get("speed_step_rpm", 10.0))
    min_speed_rpm = float(kctrl_cfg.get("min_speed_rpm", 10.0))
    max_speed_rpm = float(kctrl_cfg.get("max_speed_rpm", 500.0))
    accel = int(kctrl_cfg.get("accel", 10))
    forward_direction = int(kctrl_cfg.get("forward_direction", 0))
    reverse_direction = int(kctrl_cfg.get("reverse_direction", 1))
    wait_ack = bool(kctrl_cfg.get("wait_ack", False))

    speed_rpm = _clamp(speed_rpm, min_speed_rpm, max_speed_rpm)

    ctrl = ZDTMotorController(
        address=addr,
        serial_config=SerialConfig(
            port=port,
            baudrate=baudrate,
            timeout_s=timeout_s,
            write_timeout_s=write_timeout_s,
        ),
    )

    print("Keyboard motor control started")
    print("keys: q=forward, e=reverse, 1=speed-, 2=speed+, space=estop, x=exit, Ctrl+C=exit")
    print(f"speed={speed_rpm:.1f} rpm, accel={accel}, addr=0x{addr:02X}, port={port}")
    print(f"wait_ack={wait_ack}")

    try:
        ctrl.enable(True, sync=sync, wait_ack=wait_ack)
        while True:
            key = _getch()

            if key == "\x03":
                print("exit by Ctrl+C")
                break
            if key == "x":
                print("exit")
                break
            if key == "1":
                speed_rpm = _clamp(speed_rpm - speed_step_rpm, min_speed_rpm, max_speed_rpm)
                print(f"speed={speed_rpm:.1f} rpm")
                continue
            if key == "2":
                speed_rpm = _clamp(speed_rpm + speed_step_rpm, min_speed_rpm, max_speed_rpm)
                print(f"speed={speed_rpm:.1f} rpm")
                continue
            if key == " ":
                ctrl.stop(wait_ack=wait_ack)
                print("estop")
                continue
            if key == "q":
                ctrl.run_speed(
                    direction=forward_direction,
                    speed_rpm=speed_rpm,
                    accel=accel,
                    sync=sync,
                    wait_ack=wait_ack,
                )
                print(f"forward @ {speed_rpm:.1f} rpm")
                continue
            if key == "e":
                ctrl.run_speed(
                    direction=reverse_direction,
                    speed_rpm=speed_rpm,
                    accel=accel,
                    sync=sync,
                    wait_ack=wait_ack,
                )
                print(f"reverse @ {speed_rpm:.1f} rpm")
                continue
    finally:
        try:
            ctrl.stop(wait_ack=False)
        except Exception:
            pass
        try:
            ctrl.enable(False, sync=sync, wait_ack=False)
        except Exception:
            pass
        ctrl.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

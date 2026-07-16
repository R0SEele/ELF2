#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import yaml

try:
    from .driver import PWMConfig, ServoCalibration, ServoDriver, ServoError
except ImportError:
    from driver import PWMConfig, ServoCalibration, ServoDriver, ServoError


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "servo.yaml"
SERVO_LOCK_PATH = Path("/tmp/elf-mango-sorter-servo.lock")
SERVO_LOCK_TIMEOUT_S = 2.0


class SorterServoError(Exception):
    pass


@contextmanager
def _servo_lock(path: Path = SERVO_LOCK_PATH, timeout_s: float = SERVO_LOCK_TIMEOUT_S):
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o666)
    deadline = time.monotonic() + max(0.0, timeout_s)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SorterServoError("servo is busy: another command is still running")
                time.sleep(0.02)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


@dataclass(frozen=True)
class SorterPositions:
    center_deg: float = 0.0
    left_deg: float = -45.0
    right_deg: float = 45.0


class SorterServo:
    def __init__(
        self,
        driver: ServoDriver,
        positions: SorterPositions | None = None,
        settle_s: float = 0.35,
    ):
        self.driver = driver
        self.positions = positions or SorterPositions()
        self.settle_s = max(0.0, float(settle_s))

    def close(self, disable: bool = True) -> None:
        self.driver.close(disable=disable)

    def move_to(self, angle_deg: float, wait: bool = True) -> float:
        actual = self.driver.set_angle(angle_deg)
        if wait and self.settle_s > 0:
            time.sleep(self.settle_s)
        return actual

    def center(self, wait: bool = True) -> float:
        return self.move_to(self.positions.center_deg, wait=wait)

    def left(self, wait: bool = True) -> float:
        return self.move_to(self.positions.left_deg, wait=wait)

    def right(self, wait: bool = True) -> float:
        return self.move_to(self.positions.right_deg, wait=wait)

    def sort_to(self, position: str, wait: bool = True) -> float:
        normalized = position.strip().lower()
        if normalized in ("left", "-45", "1", "pos1", "position1"):
            return self.left(wait=wait)
        if normalized in ("center", "middle", "0", "2", "pos2", "position2"):
            return self.center(wait=wait)
        if normalized in ("right", "45", "3", "pos3", "position3"):
            return self.right(wait=wait)
        raise SorterServoError(f"unknown sorter position: {position}")


def _load_config(path: Path = CONFIG_PATH) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return (yaml.safe_load(handle) or {}).get("servo", {})
    except FileNotFoundError as exc:
        raise SorterServoError(f"config not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise SorterServoError(f"config parse failed: {exc}") from exc


def _as_path(value) -> Path:
    return value if isinstance(value, Path) else Path(str(value))


def load_sorter_servo(config_path: Path = CONFIG_PATH) -> SorterServo:
    cfg = _load_config(config_path)
    pwm_cfg = cfg.get("pwm", {})
    timing_cfg = cfg.get("timing", {})
    angle_cfg = cfg.get("angle", {})
    sorter_cfg = cfg.get("sorter", {})

    pwm = PWMConfig(
        chip=int(pwm_cfg.get("chip", 2)),
        channel=int(pwm_cfg.get("channel", 0)),
        base_path=_as_path(pwm_cfg.get("base_path", "/sys/class/pwm")),
        polarity=str(pwm_cfg.get("polarity", "normal")),
    )
    calibration = ServoCalibration(
        period_ns=int(timing_cfg.get("period_ns", 20_000_000)),
        min_pulse_us=int(timing_cfg.get("min_pulse_us", 500)),
        neutral_pulse_us=int(timing_cfg.get("neutral_pulse_us", 1500)),
        max_pulse_us=int(timing_cfg.get("max_pulse_us", 2500)),
        min_deg=float(angle_cfg.get("min_deg", -90.0)),
        neutral_deg=float(angle_cfg.get("neutral_deg", 0.0)),
        max_deg=float(angle_cfg.get("max_deg", 90.0)),
    )
    positions = SorterPositions(
        center_deg=float(sorter_cfg.get("center_deg", 0.0)),
        left_deg=float(sorter_cfg.get("left_deg", -45.0)),
        right_deg=float(sorter_cfg.get("right_deg", 45.0)),
    )
    settle_s = float(angle_cfg.get("settle_s", 0.35))

    return SorterServo(driver=ServoDriver(pwm=pwm, calibration=calibration), positions=positions, settle_s=settle_s)


def startup_angle(config_path: Path = CONFIG_PATH) -> float:
    cfg = _load_config(config_path)
    return float(cfg.get("angle", {}).get("startup_deg", 0.0))


def step_angle(config_path: Path = CONFIG_PATH) -> float:
    cfg = _load_config(config_path)
    return float(cfg.get("angle", {}).get("step_deg", 30.0))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move sorter servo to a configured position.")
    parser.add_argument(
        "position",
        choices=("1", "2", "3", "left", "center", "right", "-45", "0", "45"),
        help="Sorter position mapped by servo.yaml: 1/left, 2/center, 3/right.",
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_PATH),
        help="Path to servo.yaml.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait for the configured settle time after moving.",
    )
    parser.add_argument(
        "--hold-after-move",
        action="store_true",
        help="Keep PWM enabled after the move so the servo actively holds position.",
    )
    parser.add_argument(
        "--disable-after-move",
        action="store_true",
        help="Deprecated compatibility flag. PWM is disabled after moves by default.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        with _servo_lock():
            servo = load_sorter_servo(Path(args.config))
            try:
                actual = servo.sort_to(args.position, wait=not args.no_wait)
                print(f"position={args.position} angle={actual:.1f}deg")
                return 0
            finally:
                disable_after_move = args.disable_after_move or not args.hold_after_move
                servo.close(disable=disable_after_move)
    except (SorterServoError, ServoError, OSError, ValueError) as exc:
        print(f"servo command failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3

from __future__ import annotations

import sys
import termios
import tty
from pathlib import Path

try:
    from .sorter import load_sorter_servo, startup_angle, step_angle
except ImportError:
    from sorter import load_sorter_servo, startup_angle, step_angle


def _getch() -> str:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _diagnose_pwm() -> int:
    base_path = Path("/sys/class/pwm")
    print(f"PWM sysfs: {base_path}")
    if not base_path.exists():
        print("not found")
        return 1

    for chip_path in sorted(base_path.glob("pwmchip*")):
        npwm_path = chip_path / "npwm"
        uevent_path = chip_path / "device" / "uevent"
        npwm = npwm_path.read_text(encoding="ascii").strip() if npwm_path.exists() else "unknown"
        print(f"{chip_path.name}: npwm={npwm} target={chip_path.resolve()}")
        if uevent_path.exists():
            for line in uevent_path.read_text(encoding="ascii").splitlines():
                if line.startswith(("DRIVER=", "OF_FULLNAME=")):
                    print(f"  {line}")
        exported = sorted(path for path in chip_path.glob("pwm[0-9]*") if path.is_dir())
        exported_names = [path.name for path in exported]
        for pwm_path in exported:
            fields = []
            for name in ("period", "duty_cycle", "enable", "polarity"):
                field_path = pwm_path / name
                if field_path.exists():
                    fields.append(f"{name}={field_path.read_text(encoding='ascii').strip()}")
            print(f"  {pwm_path.name}: {' '.join(fields)}")
        print(f"  exported={exported_names if exported_names else 'none'}")

    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--diagnose":
        return _diagnose_pwm()

    servo = load_sorter_servo()
    calibration = servo.driver.calibration
    step_deg = abs(step_angle())
    angle = _clamp(startup_angle(), calibration.min_deg, calibration.max_deg)

    print("Keyboard servo test started")
    print("keys: Q/q=-step, E/e=+step, A=left(0deg), S=center(120deg), D=right(240deg), X/x=exit")
    print(
        "pwm=pwmchip{} pwm{} range={:.1f}..{:.1f}deg step={:.1f}deg".format(
            servo.driver.pwm.chip,
            servo.driver.pwm.channel,
            calibration.min_deg,
            calibration.max_deg,
            step_deg,
        )
    )

    try:
        actual = servo.move_to(angle)
        print(f"angle={actual:.1f}deg")

        while True:
            key = _getch()
            if key == "\x03":
                print("exit by Ctrl+C")
                break
            if key in ("x", "X"):
                print("exit")
                break
            if key in ("q", "Q"):
                angle = _clamp(angle - step_deg, calibration.min_deg, calibration.max_deg)
                actual = servo.move_to(angle)
                print(f"angle={actual:.1f}deg")
                continue
            if key in ("e", "E"):
                angle = _clamp(angle + step_deg, calibration.min_deg, calibration.max_deg)
                actual = servo.move_to(angle)
                print(f"angle={actual:.1f}deg")
                continue
            if key in ("s", "S"):
                actual = servo.center()
                angle = actual
                print(f"center angle={actual:.1f}deg")
                continue
            if key in ("a", "A"):
                actual = servo.left()
                angle = actual
                print(f"left angle={actual:.1f}deg")
                continue
            if key in ("d", "D"):
                actual = servo.right()
                angle = actual
                print(f"right angle={actual:.1f}deg")
                continue
    finally:
        servo.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

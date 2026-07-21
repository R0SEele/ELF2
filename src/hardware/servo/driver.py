#!/usr/bin/env python3

from __future__ import annotations

import errno
import sys
import time
from dataclasses import dataclass
from pathlib import Path


class ServoError(Exception):
    pass


@dataclass(frozen=True)
class PWMConfig:
    chip: int = 2
    channel: int = 0
    base_path: Path = Path("/sys/class/pwm")
    polarity: str = "normal"

    @property
    def chip_path(self) -> Path:
        return self.base_path / f"pwmchip{self.chip}"

    @property
    def pwm_path(self) -> Path:
        return self.chip_path / f"pwm{self.channel}"


@dataclass(frozen=True)
class ServoCalibration:
    period_ns: int = 20_000_000
    min_pulse_us: int = 500
    neutral_pulse_us: int = 1000
    max_pulse_us: int = 1500
    min_deg: float = 0.0
    neutral_deg: float = 135.0
    max_deg: float = 270.0

    def validate(self) -> None:
        if self.period_ns <= 0:
            raise ServoError("period_ns must be > 0")
        if not (0 < self.min_pulse_us < self.neutral_pulse_us < self.max_pulse_us):
            raise ServoError("pulse widths must satisfy min < neutral < max")
        if not (self.min_deg < self.neutral_deg < self.max_deg):
            raise ServoError("angles must satisfy min < neutral < max")
        if self.max_pulse_us * 1000 >= self.period_ns:
            raise ServoError("max pulse width must be shorter than PWM period")

    def angle_to_pulse_us(self, angle_deg: float) -> int:
        self.validate()
        angle_deg = self.clamp_angle(angle_deg)

        if angle_deg >= self.neutral_deg:
            span_deg = self.max_deg - self.neutral_deg
            span_pulse = self.max_pulse_us - self.neutral_pulse_us
            ratio = (angle_deg - self.neutral_deg) / span_deg
            return int(round(self.neutral_pulse_us + ratio * span_pulse))

        span_deg = self.neutral_deg - self.min_deg
        span_pulse = self.neutral_pulse_us - self.min_pulse_us
        ratio = (self.neutral_deg - angle_deg) / span_deg
        return int(round(self.neutral_pulse_us - ratio * span_pulse))

    def pulse_us_to_angle(self, pulse_us: int) -> float:
        self.validate()
        pulse_us = max(self.min_pulse_us, min(self.max_pulse_us, int(pulse_us)))

        if pulse_us >= self.neutral_pulse_us:
            span_pulse = self.max_pulse_us - self.neutral_pulse_us
            span_deg = self.max_deg - self.neutral_deg
            ratio = (pulse_us - self.neutral_pulse_us) / span_pulse
            return self.neutral_deg + ratio * span_deg

        span_pulse = self.neutral_pulse_us - self.min_pulse_us
        span_deg = self.neutral_deg - self.min_deg
        ratio = (self.neutral_pulse_us - pulse_us) / span_pulse
        return self.neutral_deg - ratio * span_deg

    def clamp_angle(self, angle_deg: float) -> float:
        return max(self.min_deg, min(self.max_deg, float(angle_deg)))


class ServoDriver:
    def __init__(self, pwm: PWMConfig | None = None, calibration: ServoCalibration | None = None):
        self.pwm = pwm or PWMConfig()
        self.calibration = calibration or ServoCalibration()
        self._opened = False
        self._enabled = False
        self._current_angle: float | None = None
        self._actual_polarity = ""

    @property
    def current_angle(self) -> float | None:
        return self._current_angle

    def open(self) -> None:
        self.calibration.validate()
        if self._opened and self.pwm.pwm_path.exists():
            return

        if not self.pwm.chip_path.exists():
            raise ServoError(f"PWM chip not found: {self.pwm.chip_path}")

        if not self.pwm.pwm_path.exists():
            self._write_file(self.pwm.chip_path / "export", str(self.pwm.channel))
            self._wait_for_pwm_path()

        if self.pwm.polarity:
            polarity_path = self.pwm.pwm_path / "polarity"
            if polarity_path.exists():
                self._actual_polarity = self._set_polarity(polarity_path, self.pwm.polarity)

        self._write_period_safely(self.calibration.period_ns)
        self._opened = True

    def close(self, disable: bool = True) -> None:
        if disable:
            try:
                self.disable()
            except ServoError:
                pass

    def enable(self) -> None:
        self.open()
        self._write_file(self.pwm.pwm_path / "enable", "1")
        self._enabled = True

    def disable(self) -> None:
        if self.pwm.pwm_path.exists():
            self._write_file(self.pwm.pwm_path / "enable", "0")
        self._enabled = False

    def set_angle(self, angle_deg: float) -> float:
        pulse_us = self.calibration.angle_to_pulse_us(angle_deg)
        return self.set_pulse_us(pulse_us)

    def set_pulse_us(self, pulse_us: int) -> float:
        self.open()
        pulse_us = max(self.calibration.min_pulse_us, min(self.calibration.max_pulse_us, int(pulse_us)))
        duty_ns = self._pulse_us_to_duty_ns(pulse_us)
        self._write_file(self.pwm.pwm_path / "duty_cycle", str(duty_ns))
        if not self._enabled:
            self.enable()

        self._current_angle = self.calibration.pulse_us_to_angle(pulse_us)
        return self._current_angle

    def _wait_for_pwm_path(self, timeout_s: float = 1.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.pwm.pwm_path.exists():
                return
            time.sleep(0.01)
        raise ServoError(f"PWM channel export timeout: {self.pwm.pwm_path}")

    def _write_period_safely(self, period_ns: int) -> None:
        enable_path = self.pwm.pwm_path / "enable"
        period_path = self.pwm.pwm_path / "period"
        try:
            current_period = int(period_path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            current_period = None
        if current_period == period_ns:
            return

        was_enabled = False
        if enable_path.exists():
            try:
                was_enabled = enable_path.read_text(encoding="ascii").strip() == "1"
            except OSError:
                was_enabled = False
        if was_enabled:
            self._write_file(enable_path, "0")
            self._enabled = False

        self._write_file(period_path, str(period_ns))

        if was_enabled:
            self._write_file(enable_path, "1")
            self._enabled = True

    def _pulse_us_to_duty_ns(self, pulse_us: int) -> int:
        high_ns = pulse_us * 1000
        if self._actual_polarity == "inversed":
            return max(0, self.calibration.period_ns - high_ns)
        return high_ns

    def _set_polarity(self, path: Path, polarity: str) -> str:
        polarity = polarity.strip()
        if not polarity:
            return ""

        try:
            current = path.read_text(encoding="ascii").strip()
        except OSError:
            current = ""
        if current == polarity:
            return current

        try:
            self._write_file(path, polarity)
            return polarity
        except ServoError as exc:
            print(f"warning: skip unsupported PWM polarity setting: {exc}", file=sys.stderr)
            return current

    def _write_file(self, path: Path, value: str) -> None:
        try:
            path.write_text(value, encoding="ascii")
        except OSError as exc:
            if path.name == "export" and exc.errno == errno.EBUSY and self.pwm.pwm_path.exists():
                return
            if path.name == "export" and exc.errno == errno.EBUSY:
                raise ServoError(
                    f"PWM channel is busy or requested by another driver: {self.pwm.pwm_path}"
                ) from exc
            raise ServoError(f"write {path} failed: {exc}") from exc

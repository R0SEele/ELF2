#!/usr/bin/env python3

import argparse
import fcntl
import os
import sys
import time
import yaml
from pathlib import Path


class GY302Error(Exception):
    pass


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sensors.yaml"
I2C_SLAVE = 0x0703

GY302_MODES = {
    "continuous_high_res_1": 0x10,
    "continuous_high_res_2": 0x11,
    "continuous_low_res": 0x13,
    "one_time_high_res_1": 0x20,
    "one_time_high_res_2": 0x21,
    "one_time_low_res": 0x23,
}


def _read_optional_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
            return config.get("sensors", {}).get("gy302", {})
    except FileNotFoundError:
        return {}


def _cfg_or_default(args_value, cfg, key, default, cast):
    if args_value is not None:
        return args_value
    if key not in cfg:
        return default
    return cast(cfg[key])


class GY302:
    def __init__(self, bus, address=0x23, mode="one_time_high_res_1", measure_delay_s=0.18):
        self._bus = bus
        self._address = address
        self._mode = mode
        self._measure_delay_s = measure_delay_s
        self._dev_path = Path(f"/dev/i2c-{bus}")

        if mode not in GY302_MODES:
            raise GY302Error(f"Unsupported mode: {mode}")
        if not self._dev_path.exists():
            raise GY302Error(f"I2C bus not found: {self._dev_path}")

    def _read_raw(self):
        fd = None
        try:
            fd = os.open(str(self._dev_path), os.O_RDWR)
            fcntl.ioctl(fd, I2C_SLAVE, self._address)

            os.write(fd, bytes((GY302_MODES[self._mode],)))
            time.sleep(self._measure_delay_s)

            frame = os.read(fd, 2)
        except OSError as exc:
            raise GY302Error(f"I2C transaction failed: {exc}") from exc
        finally:
            if fd is not None:
                os.close(fd)

        if len(frame) != 2:
            raise GY302Error(f"Invalid frame length: {len(frame)}")

        return (frame[0] << 8) | frame[1]

    def read_once(self):
        raw = self._read_raw()
        lux = raw / 1.2
        return raw, lux

    def read_with_retry(self, max_retries=3, retry_interval_s=0.05):
        last_error = None
        for _ in range(max_retries):
            try:
                return self.read_once()
            except GY302Error as exc:
                last_error = exc
                time.sleep(retry_interval_s)

        raise GY302Error(f"All attempts failed: {last_error}")


def main():
    parser = argparse.ArgumentParser(description="Read GY-302/BH1750 light sensor via I2C")
    parser.add_argument("--bus", type=int, default=None, help="I2C bus number, override YAML")
    parser.add_argument("--address", type=lambda x: int(x, 0), default=None, help="I2C address (e.g. 0x23)")
    parser.add_argument("--mode", default=None, choices=sorted(GY302_MODES.keys()), help="Measurement mode")
    parser.add_argument("--delay", type=float, default=None, help="Measurement delay in seconds")
    parser.add_argument("--interval", type=float, default=None, help="Read interval in seconds")
    parser.add_argument("--count", type=int, default=None, help="Read count, 0 means infinite")
    parser.add_argument("--max-retries", type=int, default=None, help="Max retries per sample")
    parser.add_argument("--retry-interval", type=float, default=None, help="Retry interval in seconds")
    args = parser.parse_args()

    try:
        cfg = _read_optional_config()

        bus = _cfg_or_default(args.bus, cfg, "bus", 4, int)
        address = _cfg_or_default(args.address, cfg, "address", 0x23, lambda x: int(x, 0) if isinstance(x, str) else int(x))
        mode = _cfg_or_default(args.mode, cfg, "mode", "one_time_high_res_1", str)
        measure_delay_s = _cfg_or_default(args.delay, cfg, "measure_delay_s", 0.18, float)
        interval_s = _cfg_or_default(args.interval, cfg, "read_interval_s", 1.0, float)
        count = _cfg_or_default(args.count, cfg, "sample_count", 0, int)
        max_retries = _cfg_or_default(args.max_retries, cfg, "max_retries", 3, int)
        retry_interval_s = _cfg_or_default(args.retry_interval, cfg, "retry_interval_s", 0.05, float)

        if mode not in GY302_MODES:
            raise GY302Error(f"Unsupported mode: {mode}")
        if measure_delay_s < 0:
            raise GY302Error("delay must be >= 0")
        if interval_s < 0:
            raise GY302Error("interval must be >= 0")
        if count < 0:
            raise GY302Error("count must be >= 0")
        if max_retries <= 0:
            raise GY302Error("max-retries must be > 0")
        if retry_interval_s < 0:
            raise GY302Error("retry-interval must be >= 0")

        sensor = GY302(bus=bus, address=address, mode=mode, measure_delay_s=measure_delay_s)
        print(f"GY-302 on /dev/i2c-{bus}, address=0x{address:02X}, mode={mode}")

        idx = 0
        while True:
            idx += 1
            raw, lux = sensor.read_with_retry(max_retries=max_retries, retry_interval_s=retry_interval_s)
            print(f"raw={raw:5d}  illuminance={lux:8.2f} lux")

            if count > 0 and idx >= count:
                break
            time.sleep(interval_s)

    except GY302Error as exc:
        print(f"GY302 error: {exc}")
        return 1
    except yaml.YAMLError as exc:
        print(f"Config parse error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

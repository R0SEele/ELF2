#!/usr/bin/env python3

import argparse
import fcntl
import os
import sys
import time
import yaml
from pathlib import Path


class SCD40Error(Exception):
    pass


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sensors.yaml"
I2C_SLAVE = 0x0703

CMD_START_PERIODIC_MEASURE = 0x21B1
CMD_STOP_PERIODIC_MEASURE = 0x3F86
CMD_GET_DATA_READY = 0xE4B8
CMD_READ_MEASUREMENT = 0xEC05
DEFAULT_MEASUREMENT_PERIOD_S = 5.0


def _crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def _read_optional_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
            return config.get("sensors", {}).get("scd40", {})
    except FileNotFoundError:
        return {}


def _cfg_or_default(args_value, cfg, key, default, cast):
    if args_value is not None:
        return args_value
    if key not in cfg:
        return default
    return cast(cfg[key])


class SCD40:
    def __init__(self, bus, address=0x62, warmup_s=5.0):
        self._bus = bus
        self._address = address
        self._warmup_s = warmup_s
        self._started_at = None
        self._dev_path = Path(f"/dev/i2c-{bus}")

        if not self._dev_path.exists():
            raise SCD40Error(f"I2C bus not found: {self._dev_path}")

    def _open_fd(self):
        try:
            fd = os.open(str(self._dev_path), os.O_RDWR)
            fcntl.ioctl(fd, I2C_SLAVE, self._address)
            return fd
        except OSError as exc:
            raise SCD40Error(f"I2C open/ioctl failed: {exc}") from exc

    def _write_command(self, command):
        payload = bytes(((command >> 8) & 0xFF, command & 0xFF))
        fd = None
        try:
            fd = self._open_fd()
            os.write(fd, payload)
        except OSError as exc:
            raise SCD40Error(f"I2C write failed: {exc}") from exc
        finally:
            if fd is not None:
                os.close(fd)

    def _read_response(self, command, length, delay_s):
        fd = None
        try:
            fd = self._open_fd()
            os.write(fd, bytes(((command >> 8) & 0xFF, command & 0xFF)))
            if delay_s > 0:
                time.sleep(delay_s)
            return os.read(fd, length)
        except OSError as exc:
            raise SCD40Error(f"I2C read failed: {exc}") from exc
        finally:
            if fd is not None:
                os.close(fd)

    def start_periodic_measurement(self):
        self._write_command(CMD_START_PERIODIC_MEASURE)
        self._started_at = time.monotonic()

    def stop_periodic_measurement(self):
        self._write_command(CMD_STOP_PERIODIC_MEASURE)
        self._started_at = None
        time.sleep(0.5)

    def restart_periodic_measurement(self):
        try:
            self.stop_periodic_measurement()
        except SCD40Error:
            self._started_at = None
            time.sleep(0.5)
        self.start_periodic_measurement()

    def data_ready(self):
        frame = self._read_response(CMD_GET_DATA_READY, 3, delay_s=0.001)
        if len(frame) != 3:
            raise SCD40Error(f"Invalid data-ready frame length: {len(frame)}")

        payload = frame[:2]
        crc = frame[2]
        if _crc8(payload) != crc:
            raise SCD40Error("Data-ready CRC check failed")

        status = (payload[0] << 8) | payload[1]
        return (status & 0x07FF) != 0

    def wait_data_ready(self, timeout_s=2.0, poll_interval_s=0.2):
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if self.data_ready():
                return True
            time.sleep(poll_interval_s)
        return False

    def read_once(self):
        if self._started_at is None:
            raise SCD40Error("Periodic measurement is not started")

        if time.monotonic() - self._started_at < self._warmup_s:
            raise SCD40Error("Sensor is warming up")

        frame = self._read_response(CMD_READ_MEASUREMENT, 9, delay_s=0.001)
        if len(frame) != 9:
            raise SCD40Error(f"Invalid measurement frame length: {len(frame)}")

        words = []
        for offset in (0, 3, 6):
            payload = frame[offset : offset + 2]
            crc = frame[offset + 2]
            if _crc8(payload) != crc:
                raise SCD40Error("Measurement CRC check failed")
            words.append((payload[0] << 8) | payload[1])

        co2_ppm = int(words[0])
        temperature_c = -45.0 + 175.0 * words[1] / 65535.0
        humidity_rh = 100.0 * words[2] / 65535.0
        humidity_rh = max(0.0, min(100.0, humidity_rh))
        return co2_ppm, temperature_c, humidity_rh

    def read_with_retry(self, max_retries=3, ready_timeout_s=2.0, poll_interval_s=0.2):
        last_error = None
        for attempt in range(max_retries):
            try:
                if self._started_at is None:
                    self.start_periodic_measurement()

                warmup_remaining_s = self._warmup_s - (time.monotonic() - self._started_at)
                if warmup_remaining_s > 0:
                    time.sleep(warmup_remaining_s)

                ready_timeout_s = max(ready_timeout_s, DEFAULT_MEASUREMENT_PERIOD_S + 1.0)
                if not self.wait_data_ready(timeout_s=ready_timeout_s, poll_interval_s=poll_interval_s):
                    raise SCD40Error("No fresh data within timeout")
                return self.read_once()
            except SCD40Error as exc:
                last_error = exc
                if attempt + 1 < max_retries:
                    self.restart_periodic_measurement()
        raise SCD40Error(f"All attempts failed: {last_error}")


def main():
    parser = argparse.ArgumentParser(description="Read SCD40 CO2/temperature/humidity via I2C")
    parser.add_argument("--bus", type=int, default=None, help="I2C bus number, override YAML")
    parser.add_argument("--address", type=lambda x: int(x, 0), default=None, help="I2C address (e.g. 0x62)")
    parser.add_argument("--interval", type=float, default=None, help="Read interval in seconds")
    parser.add_argument("--count", type=int, default=None, help="Read count, 0 means infinite")
    parser.add_argument("--warmup", type=float, default=None, help="Warmup time after start periodic measurement")
    parser.add_argument("--max-retries", type=int, default=None, help="Max retries per sample")
    parser.add_argument("--ready-timeout", type=float, default=None, help="Ready wait timeout in seconds")
    parser.add_argument("--poll-interval", type=float, default=None, help="Ready poll interval in seconds")
    args = parser.parse_args()

    sensor = None
    try:
        cfg = _read_optional_config()

        bus = _cfg_or_default(args.bus, cfg, "bus", 4, int)
        address = _cfg_or_default(args.address, cfg, "address", 0x62, lambda x: int(x, 0) if isinstance(x, str) else int(x))
        interval_s = _cfg_or_default(args.interval, cfg, "read_interval_s", 2.0, float)
        count = _cfg_or_default(args.count, cfg, "sample_count", 0, int)
        warmup_s = _cfg_or_default(args.warmup, cfg, "warmup_s", 5.0, float)
        max_retries = _cfg_or_default(args.max_retries, cfg, "max_retries", 3, int)
        ready_timeout_s = _cfg_or_default(args.ready_timeout, cfg, "ready_timeout_s", 2.0, float)
        poll_interval_s = _cfg_or_default(args.poll_interval, cfg, "poll_interval_s", 0.2, float)

        if interval_s < 0:
            raise SCD40Error("interval must be >= 0")
        if count < 0:
            raise SCD40Error("count must be >= 0")
        if warmup_s < 0:
            raise SCD40Error("warmup must be >= 0")
        if max_retries <= 0:
            raise SCD40Error("max-retries must be > 0")
        if ready_timeout_s <= 0:
            raise SCD40Error("ready-timeout must be > 0")
        if poll_interval_s <= 0:
            raise SCD40Error("poll-interval must be > 0")

        sensor = SCD40(bus=bus, address=address, warmup_s=warmup_s)
        sensor.start_periodic_measurement()

        print(f"SCD40 on /dev/i2c-{bus}, address=0x{address:02X}")

        idx = 0
        while True:
            idx += 1
            co2_ppm, temperature_c, humidity_rh = sensor.read_with_retry(
                max_retries=max_retries,
                ready_timeout_s=ready_timeout_s,
                poll_interval_s=poll_interval_s,
            )
            print(
                "CO2={:5d} ppm  Temperature={:6.2f} C  Humidity={:6.2f} %RH".format(
                    co2_ppm,
                    temperature_c,
                    humidity_rh,
                )
            )

            if count > 0 and idx >= count:
                break
            time.sleep(interval_s)

    except SCD40Error as exc:
        print(f"SCD40 error: {exc}")
        return 1
    except yaml.YAMLError as exc:
        print(f"Config parse error: {exc}")
        return 1
    finally:
        if sensor is not None:
            try:
                sensor.stop_periodic_measurement()
            except SCD40Error:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

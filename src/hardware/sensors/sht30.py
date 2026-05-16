#!/usr/bin/env python3

import argparse
import fcntl
import os
import sys
import time
import yaml

from pathlib import Path


class SHT30Error(Exception):
	pass


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sensors.yaml"
I2C_SLAVE = 0x0703
SHT30_MEASURE_HIGHREP = bytes((0x24, 0x00))


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
			return config.get("sensors", {}).get("sht30", {})
	except FileNotFoundError:
		return {}


def _cfg_or_default(args_value, cfg, key, default, cast):
	if args_value is not None:
		return args_value
	if key not in cfg:
		return default
	return cast(cfg[key])


class SHT30:
	def __init__(self, bus, address, measure_delay_s=0.02):
		self._bus = bus
		self._address = address
		self._measure_delay_s = measure_delay_s
		self._dev_path = Path(f"/dev/i2c-{bus}")

		if not self._dev_path.exists():
			raise SHT30Error(f"I2C bus not found: {self._dev_path}")

	def _read_frame(self):
		fd = None
		try:
			fd = os.open(str(self._dev_path), os.O_RDWR)
			fcntl.ioctl(fd, I2C_SLAVE, self._address)

			os.write(fd, SHT30_MEASURE_HIGHREP)
			time.sleep(self._measure_delay_s)

			frame = os.read(fd, 6)
		except OSError as exc:
			raise SHT30Error(f"I2C transaction failed: {exc}") from exc
		finally:
			if fd is not None:
				os.close(fd)

		if len(frame) != 6:
			raise SHT30Error(f"Invalid frame length: {len(frame)}")

		temp_msb, temp_lsb, temp_crc, hum_msb, hum_lsb, hum_crc = frame
		temp_raw = bytes((temp_msb, temp_lsb))
		hum_raw = bytes((hum_msb, hum_lsb))

		if _crc8(temp_raw) != temp_crc:
			raise SHT30Error("Temperature CRC check failed")
		if _crc8(hum_raw) != hum_crc:
			raise SHT30Error("Humidity CRC check failed")

		raw_t = (temp_msb << 8) | temp_lsb
		raw_h = (hum_msb << 8) | hum_lsb
		return raw_t, raw_h

	def read_once(self):
		raw_t, raw_h = self._read_frame()
		temperature_c = -45.0 + (175.0 * raw_t / 65535.0)
		humidity_rh = 100.0 * raw_h / 65535.0
		humidity_rh = max(0.0, min(100.0, humidity_rh))
		return temperature_c, humidity_rh

	def read_with_retry(self, max_retries, retry_interval_s):
		last_error = None
		for _ in range(max_retries):
			try:
				return self.read_once()
			except SHT30Error as exc:
				last_error = exc
				time.sleep(retry_interval_s)

		raise SHT30Error(f"All attempts failed: {last_error}")


def main():
	parser = argparse.ArgumentParser(description="Read SHT30 humidity and temperature via I2C")
	parser.add_argument("--bus", type=int, default=None, help="I2C bus number, override YAML")
	parser.add_argument("--address", type=lambda x: int(x, 0), default=None, help="I2C address (e.g. 0x44)")
	parser.add_argument("--interval", type=float, default=None, help="Read interval in seconds")
	parser.add_argument("--count", type=int, default=None, help="Read count, 0 means infinite")
	parser.add_argument("--max-retries", type=int, default=None, help="Max retries per sample")
	parser.add_argument("--retry-interval", type=float, default=None, help="Retry interval in seconds")
	args = parser.parse_args()

	try:
		cfg = _read_optional_config()

		bus = _cfg_or_default(args.bus, cfg, "bus", 4, int)
		address = _cfg_or_default(args.address, cfg, "address", 0x44, lambda x: int(x, 0) if isinstance(x, str) else int(x))
		interval_s = _cfg_or_default(args.interval, cfg, "read_interval_s", 1.0, float)
		count = _cfg_or_default(args.count, cfg, "sample_count", 0, int)
		max_retries = _cfg_or_default(args.max_retries, cfg, "max_retries", 3, int)
		retry_interval_s = _cfg_or_default(args.retry_interval, cfg, "retry_interval_s", 0.05, float)

		if interval_s < 0:
			raise SHT30Error("interval must be >= 0")
		if count < 0:
			raise SHT30Error("count must be >= 0")
		if max_retries <= 0:
			raise SHT30Error("max-retries must be > 0")

		sensor = SHT30(bus=bus, address=address)
		print(f"SHT30 on /dev/i2c-{bus}, address=0x{address:02X}")

		idx = 0
		while True:
			idx += 1
			temperature_c, humidity_rh = sensor.read_with_retry(max_retries=max_retries, retry_interval_s=retry_interval_s)
			print(f"Temperature={temperature_c:6.2f} C  Humidity={humidity_rh:6.2f} %RH")

			if count > 0 and idx >= count:
				break
			time.sleep(interval_s)

	except SHT30Error as exc:
		print(f"SHT30 error: {exc}")
		return 1
	except yaml.YAMLError as exc:
		print(f"Config parse error: {exc}")
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())

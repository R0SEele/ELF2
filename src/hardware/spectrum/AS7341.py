#!/usr/bin/env python3

import argparse
import fcntl
import os
import sys
import time
import yaml
from pathlib import Path


class AS7341Error(Exception):
	pass


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sensors.yaml"
I2C_SLAVE = 0x0703

REG_WHOAMI = 0x92
REG_ENABLE = 0x80
REG_ATIME = 0x81
REG_CFG0 = 0xA9
REG_CFG1 = 0xAA
REG_CFG6 = 0xAF
REG_STATUS2 = 0xA3
REG_ASTATUS = 0x94
REG_ASTEP_L = 0xCA

ENABLE_PON = 0x01
ENABLE_SP_EN = 0x02
ENABLE_SMUXEN = 0x10
STATUS2_AVALID = 0x40

EXPECTED_DEVICE_ID = 0x09

GAIN_TO_CODE = {
	0.5: 0,
	1.0: 1,
	2.0: 2,
	4.0: 3,
	8.0: 4,
	16.0: 5,
	32.0: 6,
	64.0: 7,
	128.0: 8,
	256.0: 9,
	512.0: 10,
}

SMUX_OUT_DISABLED = 0
SMUX_OUT_ADC0 = 1
SMUX_OUT_ADC1 = 2
SMUX_OUT_ADC2 = 3
SMUX_OUT_ADC3 = 4
SMUX_OUT_ADC4 = 5
SMUX_OUT_ADC5 = 6

# SMUX register addresses are 0x00..0x13 on RAM bank 0.
SMUX_F1F4_CLEAR_NIR = [
	(0, SMUX_OUT_DISABLED, SMUX_OUT_ADC2),
	(1, SMUX_OUT_ADC0, SMUX_OUT_DISABLED),
	(2, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(3, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(4, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(5, SMUX_OUT_ADC1, SMUX_OUT_ADC3),
	(6, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(7, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(8, SMUX_OUT_DISABLED, SMUX_OUT_ADC4),
	(9, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(10, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(11, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(12, SMUX_OUT_DISABLED, SMUX_OUT_ADC1),
	(13, SMUX_OUT_ADC3, SMUX_OUT_DISABLED),
	(14, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(15, SMUX_OUT_DISABLED, SMUX_OUT_ADC2),
	(16, SMUX_OUT_ADC0, SMUX_OUT_DISABLED),
	(17, SMUX_OUT_DISABLED, SMUX_OUT_ADC4),
	(18, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(19, SMUX_OUT_ADC5, SMUX_OUT_DISABLED),
]

SMUX_F5F8_CLEAR_NIR = [
	(0, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(1, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(2, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(3, SMUX_OUT_DISABLED, SMUX_OUT_ADC3),
	(4, SMUX_OUT_ADC1, SMUX_OUT_DISABLED),
	(5, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(6, SMUX_OUT_DISABLED, SMUX_OUT_ADC0),
	(7, SMUX_OUT_ADC2, SMUX_OUT_DISABLED),
	(8, SMUX_OUT_DISABLED, SMUX_OUT_ADC4),
	(9, SMUX_OUT_DISABLED, SMUX_OUT_ADC0),
	(10, SMUX_OUT_ADC2, SMUX_OUT_DISABLED),
	(11, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(12, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(13, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(14, SMUX_OUT_ADC3, SMUX_OUT_ADC1),
	(15, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(16, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(17, SMUX_OUT_DISABLED, SMUX_OUT_ADC4),
	(18, SMUX_OUT_DISABLED, SMUX_OUT_DISABLED),
	(19, SMUX_OUT_ADC5, SMUX_OUT_DISABLED),
]


def _read_optional_config():
	try:
		with CONFIG_PATH.open("r", encoding="utf-8") as handle:
			config = yaml.safe_load(handle) or {}
			return config.get("sensors", {}).get("as7341", {})
	except FileNotFoundError:
		return {}


def _cfg_or_default(args_value, cfg, key, default, cast):
	if args_value is not None:
		return args_value
	if key not in cfg:
		return default
	return cast(cfg[key])


def _to_i2c_addr(value):
	if isinstance(value, str):
		return int(value, 0)
	return int(value)


class AS7341:
	def __init__(self, bus, address=0x39, atime=100, astep=999, gain=128.0):
		self._bus = int(bus)
		self._address = int(address)
		self._atime = int(atime)
		self._astep = int(astep)
		self._gain = float(gain)
		self._dev_path = Path(f"/dev/i2c-{self._bus}")

		if not self._dev_path.exists():
			raise AS7341Error(f"I2C bus not found: {self._dev_path}")
		if self._gain not in GAIN_TO_CODE:
			raise AS7341Error(f"Unsupported gain: {self._gain}")
		if not (0 <= self._atime <= 0xFF):
			raise AS7341Error("atime out of range: 0..255")
		if not (0 <= self._astep <= 0xFFFF):
			raise AS7341Error("astep out of range: 0..65535")

		self._active_mode = None

	@property
	def integration_time_ms(self):
		return (self._atime + 1) * (self._astep + 1) * 2.78e-3

	def _open_fd(self):
		try:
			fd = os.open(str(self._dev_path), os.O_RDWR)
			fcntl.ioctl(fd, I2C_SLAVE, self._address)
			return fd
		except OSError as exc:
			raise AS7341Error(f"I2C open/ioctl failed: {exc}") from exc

	def _write_u8(self, reg, value):
		fd = None
		try:
			fd = self._open_fd()
			os.write(fd, bytes((reg & 0xFF, value & 0xFF)))
		except OSError as exc:
			raise AS7341Error(f"I2C write failed (reg=0x{reg:02X}): {exc}") from exc
		finally:
			if fd is not None:
				os.close(fd)

	def _read_u8(self, reg):
		fd = None
		try:
			fd = self._open_fd()
			os.write(fd, bytes((reg & 0xFF,)))
			data = os.read(fd, 1)
		except OSError as exc:
			raise AS7341Error(f"I2C read failed (reg=0x{reg:02X}): {exc}") from exc
		finally:
			if fd is not None:
				os.close(fd)

		if len(data) != 1:
			raise AS7341Error(f"Invalid read length at reg 0x{reg:02X}: {len(data)}")
		return data[0]

	def _read_block(self, reg, length):
		fd = None
		try:
			fd = self._open_fd()
			os.write(fd, bytes((reg & 0xFF,)))
			data = os.read(fd, length)
		except OSError as exc:
			raise AS7341Error(f"I2C block read failed (reg=0x{reg:02X}): {exc}") from exc
		finally:
			if fd is not None:
				os.close(fd)

		if len(data) != length:
			raise AS7341Error(
				f"Invalid block length at reg 0x{reg:02X}: {len(data)} (expect {length})"
			)
		return data

	def _update_bits(self, reg, mask, value):
		cur = self._read_u8(reg)
		nxt = (cur & (~mask & 0xFF)) | (value & mask)
		if nxt != cur:
			self._write_u8(reg, nxt)

	def _set_ram_bank0(self):
		# CFG0 bit4 = 0 selects RAM bank 0 for SMUX registers 0x00..0x7F.
		self._update_bits(REG_CFG0, 0x10, 0x00)

	def _set_smux_table(self, table):
		for reg, out1, out2 in table:
			packed = (out1 & 0x0F) | ((out2 & 0x0F) << 4)
			self._write_u8(reg, packed)

	def _trigger_smux_command(self, timeout_s=1.0):
		# CFG6[4:3] = 0b10 means "write SMUX config".
		self._update_bits(REG_CFG6, 0x18, 0x10)
		self._update_bits(REG_ENABLE, ENABLE_SMUXEN, ENABLE_SMUXEN)

		start = time.monotonic()
		while True:
			if (self._read_u8(REG_ENABLE) & ENABLE_SMUXEN) == 0:
				return
			if time.monotonic() - start > timeout_s:
				raise AS7341Error("Timeout waiting SMUX command completion")
			time.sleep(0.001)

	def _wait_data_ready(self, timeout_s=1.0):
		start = time.monotonic()
		while True:
			if self._read_u8(REG_STATUS2) & STATUS2_AVALID:
				return
			if time.monotonic() - start > timeout_s:
				raise AS7341Error("Timeout waiting spectral data ready")
			time.sleep(0.001)

	def initialize(self):
		chip_id_raw = self._read_u8(REG_WHOAMI)
		# Datasheet/driver convention: device id is WHOAMI[7:2].
		chip_id = (chip_id_raw >> 2) & 0x3F
		if chip_id != EXPECTED_DEVICE_ID:
			raise AS7341Error(
				"Unexpected AS7341 chip id: raw=0x{:02X} decoded=0x{:02X}, expected=0x{:02X}".format(
					chip_id_raw,
					chip_id,
					EXPECTED_DEVICE_ID,
				)
			)

		self._update_bits(REG_ENABLE, ENABLE_PON, ENABLE_PON)
		time.sleep(0.01)

		self._write_u8(REG_ATIME, self._atime)
		self._write_u8(REG_ASTEP_L, self._astep & 0xFF)
		self._write_u8(REG_ASTEP_L + 1, (self._astep >> 8) & 0xFF)
		self._write_u8(REG_CFG1, GAIN_TO_CODE[self._gain] & 0x1F)

	def _read_adc6(self):
		# Reading ASTATUS latches all six ADC channel values.
		frame = self._read_block(REG_ASTATUS, 13)
		channels = []
		for idx in range(6):
			offset = 1 + idx * 2
			channels.append(int.from_bytes(frame[offset : offset + 2], "little"))
		return channels

	def _configure_mode(self, mode, ready_timeout_s):
		if mode == self._active_mode:
			self._wait_data_ready(timeout_s=ready_timeout_s)
			return

		self._update_bits(REG_ENABLE, ENABLE_SP_EN, 0x00)
		self._set_ram_bank0()

		if mode == "f1f4":
			self._set_smux_table(SMUX_F1F4_CLEAR_NIR)
		elif mode == "f5f8":
			self._set_smux_table(SMUX_F5F8_CLEAR_NIR)
		else:
			raise AS7341Error(f"Unsupported mode: {mode}")

		self._trigger_smux_command(timeout_s=ready_timeout_s)
		self._update_bits(REG_ENABLE, ENABLE_SP_EN, ENABLE_SP_EN)
		self._wait_data_ready(timeout_s=ready_timeout_s)
		self._active_mode = mode

	def read_once(self, ready_timeout_s=1.0):
		self._configure_mode("f1f4", ready_timeout_s=ready_timeout_s)
		low = self._read_adc6()

		self._configure_mode("f5f8", ready_timeout_s=ready_timeout_s)
		high = self._read_adc6()

		clear_avg = int(round((low[4] + high[4]) / 2.0))
		nir_avg = int(round((low[5] + high[5]) / 2.0))

		return {
			"f1_415": low[0],
			"f2_445": low[1],
			"f3_480": low[2],
			"f4_515": low[3],
			"f5_555": high[0],
			"f6_590": high[1],
			"f7_630": high[2],
			"f8_680": high[3],
			"clear": clear_avg,
			"nir": nir_avg,
			"clear_low": low[4],
			"nir_low": low[5],
			"clear_high": high[4],
			"nir_high": high[5],
			"integration_time_ms": self.integration_time_ms,
			"gain": self._gain,
		}

	def read_with_retry(self, max_retries=3, retry_interval_s=0.05, ready_timeout_s=1.0):
		last_error = None
		for _ in range(max_retries):
			try:
				return self.read_once(ready_timeout_s=ready_timeout_s)
			except AS7341Error as exc:
				last_error = exc
				time.sleep(retry_interval_s)
		raise AS7341Error(f"All attempts failed: {last_error}")


def main():
	parser = argparse.ArgumentParser(description="Read AS7341 spectral data via I2C")
	parser.add_argument("--bus", type=int, default=None, help="I2C bus number, override YAML")
	parser.add_argument("--address", type=lambda x: int(x, 0), default=None, help="I2C address (e.g. 0x39)")
	parser.add_argument("--atime", type=int, default=None, help="Integration step count (0..255)")
	parser.add_argument("--astep", type=int, default=None, help="Integration step size (0..65535)")
	parser.add_argument("--gain", type=float, default=None, help="Sensor gain (0.5,1,2,...,512)")
	parser.add_argument("--ready-timeout", type=float, default=None, help="Timeout waiting data-ready")
	parser.add_argument("--interval", type=float, default=None, help="Read interval in seconds")
	parser.add_argument("--count", type=int, default=None, help="Read count, 0 means infinite")
	parser.add_argument("--max-retries", type=int, default=None, help="Max retries per sample")
	parser.add_argument("--retry-interval", type=float, default=None, help="Retry interval in seconds")
	args = parser.parse_args()

	try:
		cfg = _read_optional_config()

		bus = _cfg_or_default(args.bus, cfg, "bus", 7, int)
		address = _cfg_or_default(args.address, cfg, "address", 0x39, _to_i2c_addr)
		atime = _cfg_or_default(args.atime, cfg, "atime", 100, int)
		astep = _cfg_or_default(args.astep, cfg, "astep", 999, int)
		gain = _cfg_or_default(args.gain, cfg, "gain", 128.0, float)
		ready_timeout_s = _cfg_or_default(args.ready_timeout, cfg, "ready_timeout_s", 1.0, float)
		interval_s = _cfg_or_default(args.interval, cfg, "read_interval_s", 1.0, float)
		count = _cfg_or_default(args.count, cfg, "sample_count", 0, int)
		max_retries = _cfg_or_default(args.max_retries, cfg, "max_retries", 3, int)
		retry_interval_s = _cfg_or_default(args.retry_interval, cfg, "retry_interval_s", 0.05, float)

		if interval_s < 0:
			raise AS7341Error("interval must be >= 0")
		if count < 0:
			raise AS7341Error("count must be >= 0")
		if max_retries <= 0:
			raise AS7341Error("max-retries must be > 0")
		if retry_interval_s < 0:
			raise AS7341Error("retry-interval must be >= 0")
		if ready_timeout_s <= 0:
			raise AS7341Error("ready-timeout must be > 0")

		sensor = AS7341(bus=bus, address=address, atime=atime, astep=astep, gain=gain)
		sensor.initialize()

		print(
			"AS7341 on /dev/i2c-{} address=0x{:02X} atime={} astep={} gain={}x tint={:.3f}ms".format(
				bus,
				address,
				atime,
				astep,
				gain,
				sensor.integration_time_ms,
			)
		)

		idx = 0
		while True:
			idx += 1
			data = sensor.read_with_retry(
				max_retries=max_retries,
				retry_interval_s=retry_interval_s,
				ready_timeout_s=ready_timeout_s,
			)

			print(
				"F1={:5d} F2={:5d} F3={:5d} F4={:5d} F5={:5d} F6={:5d} F7={:5d} F8={:5d} CLEAR={:5d} NIR={:5d}".format(
					data["f1_415"],
					data["f2_445"],
					data["f3_480"],
					data["f4_515"],
					data["f5_555"],
					data["f6_590"],
					data["f7_630"],
					data["f8_680"],
					data["clear"],
					data["nir"],
				)
			)

			if count > 0 and idx >= count:
				break
			time.sleep(interval_s)

	except AS7341Error as exc:
		print(f"AS7341 error: {exc}")
		return 1
	except yaml.YAMLError as exc:
		print(f"Config parse error: {exc}")
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())

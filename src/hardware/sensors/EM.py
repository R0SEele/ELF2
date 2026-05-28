#!/usr/bin/env python3

import argparse
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path

try:
	from .gy302 import GY302, GY302Error
	from .mq135 import MQ135, MQ135ADC, MQ135Error
	from .scd40 import SCD40, SCD40Error
	from .sht30 import SHT30, SHT30Error
except ImportError:
	from gy302 import GY302, GY302Error
	from mq135 import MQ135, MQ135ADC, MQ135Error
	from scd40 import SCD40, SCD40Error
	from sht30 import SHT30, SHT30Error


class EMError(Exception):
	pass


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sensors.yaml"


def _cfg_or_default(args_value, cfg, key, default, cast):
	if args_value is not None:
		return args_value
	if key not in cfg:
		return default
	return cast(cfg[key])


def _load_sensor_config():
	try:
		with CONFIG_PATH.open("r", encoding="utf-8") as handle:
			config = yaml.safe_load(handle) or {}
			return config.get("sensors", {})
	except FileNotFoundError as exc:
		raise EMError(f"Config not found: {CONFIG_PATH}") from exc
	except yaml.YAMLError as exc:
		raise EMError(f"Config parse error: {exc}") from exc


def _as_i2c_address(value, default):
	if value is None:
		return default
	if isinstance(value, str):
		return int(value, 0)
	return int(value)


class EnvironmentMonitor:
	def __init__(self, sensors_cfg):
		self._sensors_cfg = sensors_cfg
		self._init_errors = {}
		self._sht30 = None
		self._scd40 = None
		self._gy302 = None
		self._mq135 = None

		sht_cfg = sensors_cfg.get("sht30", {})
		self._sht30_max_retries = int(sht_cfg.get("max_retries", 3))
		self._sht30_retry_interval_s = float(sht_cfg.get("retry_interval_s", 0.05))
		try:
			self._sht30 = SHT30(
				bus=int(sht_cfg.get("bus", 4)),
				address=_as_i2c_address(sht_cfg.get("address", "0x44"), 0x44),
			)
		except SHT30Error as exc:
			self._init_errors["sht30"] = str(exc)

		scd_cfg = sensors_cfg.get("scd40", {})
		self._scd40_max_retries = int(scd_cfg.get("max_retries", 3))
		self._scd40_ready_timeout_s = float(scd_cfg.get("ready_timeout_s", 2.0))
		self._scd40_poll_interval_s = float(scd_cfg.get("poll_interval_s", 0.2))
		try:
			self._scd40 = SCD40(
				bus=int(scd_cfg.get("bus", 4)),
				address=_as_i2c_address(scd_cfg.get("address", "0x62"), 0x62),
				warmup_s=float(scd_cfg.get("warmup_s", 5.0)),
			)
			self._scd40.start_periodic_measurement()
		except SCD40Error as exc:
			self._init_errors["scd40"] = str(exc)

		gy_cfg = sensors_cfg.get("gy302", {})
		self._gy302_max_retries = int(gy_cfg.get("max_retries", 3))
		self._gy302_retry_interval_s = float(gy_cfg.get("retry_interval_s", 0.05))
		try:
			self._gy302 = GY302(
				bus=int(gy_cfg.get("bus", 4)),
				address=_as_i2c_address(gy_cfg.get("address", "0x23"), 0x23),
				mode=str(gy_cfg.get("mode", "one_time_high_res_1")),
				measure_delay_s=float(gy_cfg.get("measure_delay_s", 0.18)),
			)
		except GY302Error as exc:
			self._init_errors["gy302"] = str(exc)

		mq_cfg = sensors_cfg.get("mq135", {})
		try:
			self._mq135 = MQ135(
				adc=MQ135ADC(
					iio_device=str(mq_cfg.get("iio_device", "iio:device0")),
					channel=int(mq_cfg.get("channel", 4)),
				),
				adc_reference_mv=float(mq_cfg.get("adc_reference_mv", 1800.0)),
				adc_raw_max=float(mq_cfg.get("adc_raw_max", 4095.0)),
				load_resistance_kohm=float(mq_cfg.get("load_resistance_kohm", 10.0)),
				calibration_r0_kohm=float(mq_cfg.get("calibration_r0_kohm", 76.63)),
				gas_curve_a=float(mq_cfg.get("gas_curve_a", 116.6020682)),
				gas_curve_b=float(mq_cfg.get("gas_curve_b", -2.769034857)),
				ppm_scale=float(mq_cfg.get("ppm_scale", 0.01)),
			)
		except MQ135Error as exc:
			self._init_errors["mq135"] = str(exc)

	def close(self):
		if self._scd40 is not None:
			try:
				self._scd40.stop_periodic_measurement()
			except SCD40Error:
				pass

	def read_all(self):
		readings = {}

		if self._sht30 is None:
			readings["sht30"] = {"ok": False, "error": self._init_errors.get("sht30", "not initialized")}
		else:
			try:
				temperature_c, humidity_rh = self._sht30.read_with_retry(
					max_retries=self._sht30_max_retries,
					retry_interval_s=self._sht30_retry_interval_s,
				)
				readings["sht30"] = {
					"ok": True,
					"temperature_c": temperature_c,
					"humidity_rh": humidity_rh,
				}
			except SHT30Error as exc:
				readings["sht30"] = {"ok": False, "error": str(exc)}

		if self._scd40 is None:
			readings["scd40"] = {"ok": False, "error": self._init_errors.get("scd40", "not initialized")}
		else:
			try:
				co2_ppm, temperature_c, humidity_rh = self._scd40.read_with_retry(
					max_retries=self._scd40_max_retries,
					ready_timeout_s=self._scd40_ready_timeout_s,
					poll_interval_s=self._scd40_poll_interval_s,
				)
				readings["scd40"] = {
					"ok": True,
					"co2_ppm": co2_ppm,
					"temperature_c": temperature_c,
					"humidity_rh": humidity_rh,
				}
			except SCD40Error as exc:
				readings["scd40"] = {"ok": False, "error": str(exc)}

		if self._gy302 is None:
			readings["gy302"] = {"ok": False, "error": self._init_errors.get("gy302", "not initialized")}
		else:
			try:
				raw, lux = self._gy302.read_with_retry(
					max_retries=self._gy302_max_retries,
					retry_interval_s=self._gy302_retry_interval_s,
				)
				readings["gy302"] = {"ok": True, "raw": raw, "lux": lux}
			except GY302Error as exc:
				readings["gy302"] = {"ok": False, "error": str(exc)}

		if self._mq135 is None:
			readings["mq135"] = {"ok": False, "error": self._init_errors.get("mq135", "not initialized")}
		else:
			try:
				readings["mq135"] = {"ok": True, **self._mq135.read_once()}
			except MQ135Error as exc:
				readings["mq135"] = {"ok": False, "error": str(exc)}

		return readings


def _print_sensor_line(title, payload, formatter):
	if not payload["ok"]:
		print(f"{title:<6}: ERROR {payload['error']}")
		return False
	print(f"{title:<6}: {formatter(payload)}")
	return True


def _render_readings(readings):
	ok = True
	ok = _print_sensor_line(
		"SHT30",
		readings["sht30"],
		lambda p: "temp={:6.2f} C  humidity={:6.2f} %RH".format(p["temperature_c"], p["humidity_rh"]),
	) and ok

	ok = _print_sensor_line(
		"SCD40",
		readings["scd40"],
		lambda p: "co2={:5d} ppm  temp={:6.2f} C  humidity={:6.2f} %RH".format(
			p["co2_ppm"],
			p["temperature_c"],
			p["humidity_rh"],
		),
	) and ok

	ok = _print_sensor_line(
		"GY302",
		readings["gy302"],
		lambda p: "raw={:5d}  illuminance={:8.2f} lux".format(p["raw"], p["lux"]),
	) and ok

	ok = _print_sensor_line(
		"MQ135",
		readings["mq135"],
		lambda p: "raw={:4d}  level={:6.2f}%  voltage={:7.2f} mV  ratio={:7.4f}  est_ppm={:8.2f}".format(
			p["raw"],
			p["level_pct"],
			p["voltage_mv"],
			p["ratio"],
			p["ppm_est"],
		),
	) and ok

	return ok


def main():
	parser = argparse.ArgumentParser(description="Display all environment sensors on ELF RK3588")
	parser.add_argument("--count", type=int, default=None, help="Display cycles, 0 means infinite")
	parser.add_argument("--interval", type=float, default=None, help="Display interval seconds")
	parser.add_argument("--fail-fast", action="store_true", help="Exit immediately when any sensor read fails")
	args = parser.parse_args()

	monitor = None
	try:
		sensors_cfg = _load_sensor_config()
		em_cfg = sensors_cfg.get("em", {})

		count = _cfg_or_default(args.count, em_cfg, "sample_count", 0, int)
		interval_s = _cfg_or_default(args.interval, em_cfg, "read_interval_s", 2.0, float)

		if count < 0:
			raise EMError("count must be >= 0")
		if interval_s < 0:
			raise EMError("interval must be >= 0")

		monitor = EnvironmentMonitor(sensors_cfg=sensors_cfg)

		idx = 0
		while True:
			idx += 1
			print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] cycle={idx}")
			all_ok = _render_readings(monitor.read_all())
			print("")

			if args.fail_fast and not all_ok:
				return 1
			if count > 0 and idx >= count:
				break
			time.sleep(interval_s)

	except (EMError, SHT30Error, SCD40Error, GY302Error, MQ135Error) as exc:
		print(f"EM error: {exc}")
		return 1
	finally:
		if monitor is not None:
			monitor.close()

	return 0


if __name__ == "__main__":
	sys.exit(main())

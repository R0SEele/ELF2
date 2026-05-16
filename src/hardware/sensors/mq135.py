#!/usr/bin/env python3

import argparse
import sys
import time
import yaml
from pathlib import Path


class MQ135Error(Exception):
    pass


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sensors.yaml"


def _read_optional_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
            return config.get("sensors", {}).get("mq135", {})
    except FileNotFoundError:
        return {}


def _cfg_or_default(args_value, cfg, key, default, cast):
    if args_value is not None:
        return args_value
    if key not in cfg:
        return default
    return cast(cfg[key])


class MQ135ADC:
    def __init__(self, iio_device, channel):
        self._base = Path("/sys/bus/iio/devices") / iio_device
        self._channel = channel
        self._raw_path = self._base / f"in_voltage{channel}_raw"
        self._scale_path = self._base / "in_voltage_scale"
        self._name_path = self._base / "name"

        if not self._base.exists():
            raise MQ135Error(f"IIO device not found: {self._base}")
        if not self._raw_path.exists():
            raise MQ135Error(f"ADC channel file not found: {self._raw_path}")
        if not self._scale_path.exists():
            raise MQ135Error(f"ADC scale file not found: {self._scale_path}")

    def device_name(self):
        try:
            return self._name_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise MQ135Error(f"Failed to read device name: {exc}") from exc

    def read_raw(self):
        try:
            return int(self._raw_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            raise MQ135Error(f"Failed to read raw ADC value: {exc}") from exc

    def read_scale_mv(self):
        try:
            return float(self._scale_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            raise MQ135Error(f"Failed to read ADC scale: {exc}") from exc


class MQ135:
    def __init__(
        self,
        adc,
        adc_reference_mv=1800.0,
        adc_raw_max=4095.0,
        load_resistance_kohm=10.0,
        calibration_r0_kohm=76.63,
        gas_curve_a=116.6020682,
        gas_curve_b=-2.769034857,
        ppm_scale=0.01,
    ):
        self._adc = adc
        self._adc_reference_mv = adc_reference_mv
        self._adc_raw_max = adc_raw_max
        self._load_resistance_kohm = load_resistance_kohm
        self._calibration_r0_kohm = calibration_r0_kohm
        self._gas_curve_a = gas_curve_a
        self._gas_curve_b = gas_curve_b
        self._ppm_scale = ppm_scale

        if adc_reference_mv <= 0:
            raise MQ135Error("adc_reference_mv must be > 0")
        if adc_raw_max <= 0:
            raise MQ135Error("adc_raw_max must be > 0")
        if load_resistance_kohm <= 0:
            raise MQ135Error("load_resistance_kohm must be > 0")
        if calibration_r0_kohm <= 0:
            raise MQ135Error("calibration_r0_kohm must be > 0")
        if ppm_scale <= 0:
            raise MQ135Error("ppm_scale must be > 0")

    def _estimate_sensor_resistance(self, voltage_mv):
        if voltage_mv <= 0:
            return float("inf")
        return self._load_resistance_kohm * (self._adc_reference_mv - voltage_mv) / voltage_mv

    def read_once(self):
        raw = self._adc.read_raw()
        scale_mv = self._adc.read_scale_mv()
        voltage_mv = raw * scale_mv

        level_pct = max(0.0, min(100.0, (raw / self._adc_raw_max) * 100.0))
        rs_kohm = self._estimate_sensor_resistance(voltage_mv)
        ratio = rs_kohm / self._calibration_r0_kohm

        # Empirical estimate with configurable scaling for board-level calibration.
        ppm_est = self._gas_curve_a * (ratio ** self._gas_curve_b) * self._ppm_scale

        return {
            "raw": raw,
            "scale_mv": scale_mv,
            "voltage_mv": voltage_mv,
            "level_pct": level_pct,
            "rs_kohm": rs_kohm,
            "ratio": ratio,
            "ppm_est": ppm_est,
        }


def main():
    parser = argparse.ArgumentParser(description="Read MQ-135 gas sensor via SARADC (IIO)")
    parser.add_argument("--device", default=None, help="IIO device name, override YAML")
    parser.add_argument("--channel", type=int, default=None, help="ADC channel number, override YAML")
    parser.add_argument("--interval", type=float, default=None, help="Read interval (s), override YAML")
    parser.add_argument("--count", type=int, default=None, help="Read count, override YAML; 0 means infinite")
    parser.add_argument("--adc-ref-mv", type=float, default=None, help="ADC reference full-scale millivolts")
    parser.add_argument("--adc-raw-max", type=float, default=None, help="ADC max raw code")
    parser.add_argument("--rl-kohm", type=float, default=None, help="MQ-135 load resistance (kOhm)")
    parser.add_argument("--r0-kohm", type=float, default=None, help="MQ-135 calibration R0 (kOhm)")
    parser.add_argument("--curve-a", type=float, default=None, help="Gas curve coefficient A")
    parser.add_argument("--curve-b", type=float, default=None, help="Gas curve coefficient B")
    parser.add_argument("--ppm-scale", type=float, default=None, help="Estimated ppm scaling factor")
    args = parser.parse_args()

    try:
        cfg = _read_optional_config()

        device = _cfg_or_default(args.device, cfg, "iio_device", "iio:device0", str)
        channel = _cfg_or_default(args.channel, cfg, "channel", 4, int)
        interval_s = _cfg_or_default(args.interval, cfg, "read_interval_s", 1.0, float)
        count = _cfg_or_default(args.count, cfg, "sample_count", 0, int)

        adc_ref_mv = _cfg_or_default(args.adc_ref_mv, cfg, "adc_reference_mv", 1800.0, float)
        adc_raw_max = _cfg_or_default(args.adc_raw_max, cfg, "adc_raw_max", 4095.0, float)
        rl_kohm = _cfg_or_default(args.rl_kohm, cfg, "load_resistance_kohm", 10.0, float)
        r0_kohm = _cfg_or_default(args.r0_kohm, cfg, "calibration_r0_kohm", 76.63, float)
        curve_a = _cfg_or_default(args.curve_a, cfg, "gas_curve_a", 116.6020682, float)
        curve_b = _cfg_or_default(args.curve_b, cfg, "gas_curve_b", -2.769034857, float)
        ppm_scale = _cfg_or_default(args.ppm_scale, cfg, "ppm_scale", 0.01, float)

        if interval_s < 0:
            raise MQ135Error("interval must be >= 0")
        if count < 0:
            raise MQ135Error("count must be >= 0")

        adc = MQ135ADC(iio_device=device, channel=channel)
        sensor = MQ135(
            adc=adc,
            adc_reference_mv=adc_ref_mv,
            adc_raw_max=adc_raw_max,
            load_resistance_kohm=rl_kohm,
            calibration_r0_kohm=r0_kohm,
            gas_curve_a=curve_a,
            gas_curve_b=curve_b,
            ppm_scale=ppm_scale,
        )
        print(f"MQ-135 on {device} ({adc.device_name()}), channel=VIN{channel}")

        idx = 0
        while True:
            idx += 1
            sample = sensor.read_once()
            print(
                "raw={raw:4d}  level={level_pct:6.2f}%  voltage={voltage_mv:7.2f} mV  ratio={ratio:7.4f}  est_ppm={ppm_est:8.2f}".format(
                    **sample
                )
            )

            if count > 0 and idx >= count:
                break
            time.sleep(interval_s)

    except MQ135Error as exc:
        print(f"MQ135 error: {exc}")
        return 1
    except yaml.YAMLError as exc:
        print(f"Config parse error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

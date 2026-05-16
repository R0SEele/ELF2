#!/usr/bin/env python3

import argparse
import colorsys
import json
import sys
import time

try:
	from .AS7341 import AS7341, AS7341Error, _cfg_or_default, _read_optional_config, _to_i2c_addr
except ImportError:
	from AS7341 import AS7341, AS7341Error, _cfg_or_default, _read_optional_config, _to_i2c_addr


WAVELENGTHS_NM = {
	"f1_415": 415,
	"f2_445": 445,
	"f3_480": 480,
	"f4_515": 515,
	"f5_555": 555,
	"f6_590": 590,
	"f7_630": 630,
	"f8_680": 680,
}


SPECTRAL_BANDS = [
	"f1_415",
	"f2_445",
	"f3_480",
	"f4_515",
	"f5_555",
	"f6_590",
	"f7_630",
	"f8_680",
]


# CIE 1931 2-deg CMF values sampled at 5nm, sourced from specrend.c table.
CIE1931_2DEG_XYZ = {
	415: (0.0776, 0.0022, 0.3713),
	445: (0.3481, 0.0298, 1.7826),
	480: (0.0956, 0.1390, 0.8130),
	515: (0.0291, 0.6082, 0.1117),
	555: (0.5121, 1.0000, 0.0057),
	590: (1.0263, 0.7570, 0.0011),
	630: (0.6424, 0.2650, 0.0000),
	680: (0.0468, 0.0170, 0.0000),
}


def _clip(v, lo, hi):
	return max(lo, min(hi, v))


def _srgb_gamma_encode(c):
	c = max(0.0, c)
	if c <= 0.0031308:
		return 12.92 * c
	return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _xyz_chromaticity_to_srgb(x, y, z):
	if y <= 1e-9:
		return 0, 0, 0

	# Reconstruct XYZ with Y fixed to 1 for hue-dominant rendering.
	X = x / y
	Y = 1.0
	Z = z / y

	# D65 XYZ -> linear sRGB.
	r_lin = (3.2406 * X) + (-1.5372 * Y) + (-0.4986 * Z)
	g_lin = (-0.9689 * X) + (1.8758 * Y) + (0.0415 * Z)
	b_lin = (0.0557 * X) + (-0.2040 * Y) + (1.0570 * Z)

	# If out of gamut, desaturate by adding white (Fourmilab approach).
	min_c = min(r_lin, g_lin, b_lin)
	if min_c < 0.0:
		w = -min_c
		r_lin += w
		g_lin += w
		b_lin += w

	max_lin = max(r_lin, g_lin, b_lin, 1e-9)
	r_lin /= max_lin
	g_lin /= max_lin
	b_lin /= max_lin

	r = _clip(int(round(255.0 * _srgb_gamma_encode(r_lin))), 0, 255)
	g = _clip(int(round(255.0 * _srgb_gamma_encode(g_lin))), 0, 255)
	b = _clip(int(round(255.0 * _srgb_gamma_encode(b_lin))), 0, 255)
	return r, g, b


def _load_reference(cfg, key):
	ref = cfg.get(key)
	if ref is None:
		return None
	if not isinstance(ref, dict):
		raise AS7341Error(f"{key} must be a mapping in sensors.yaml")

	out = {}
	for band in SPECTRAL_BANDS:
		if band not in ref:
			raise AS7341Error(f"{key} missing required band: {band}")
		out[band] = float(ref[band])
	return out


def _calibrate_bands(raw, dark_ref=None, white_ref=None):
	corrected = {}
	for band in SPECTRAL_BANDS:
		value = float(raw[band])
		dark = 0.0 if dark_ref is None else float(dark_ref[band])
		value = max(0.0, value - dark)

		if white_ref is not None:
			den = max(1e-6, float(white_ref[band]) - dark)
			value = value / den

		corrected[band] = value
	return corrected


def _compute_xyz(corrected):
	X = 0.0
	Y = 0.0
	Z = 0.0
	for band in SPECTRAL_BANDS:
		nm = WAVELENGTHS_NM[band]
		xb, yb, zb = CIE1931_2DEG_XYZ[nm]
		v = corrected[band]
		X += v * xb
		Y += v * yb
		Z += v * zb

	xyz_sum = X + Y + Z
	if xyz_sum <= 1e-12:
		raise AS7341Error("Invalid XYZ sum: 0")

	x = X / xyz_sum
	y = Y / xyz_sum
	z = Z / xyz_sum
	return X, Y, Z, x, y, z


def _compute_energy(corrected):
	blue = float(corrected["f1_415"] + corrected["f2_445"] + corrected["f3_480"])
	green = float(corrected["f4_515"] + corrected["f5_555"])
	red = float(corrected["f6_590"] + corrected["f7_630"] + corrected["f8_680"])
	return red, green, blue


def _name_from_hsv(h_deg, s, v, centroid_nm):
	if v < 0.08:
		return "black"
	if s < 0.12:
		if v > 0.85:
			return "white"
		if v > 0.45:
			return "gray"
		return "dark_gray"
	if 15 <= h_deg < 45 and v < 0.65:
		return "brown"

	if h_deg < 15 or h_deg >= 345:
		return "red"
	if h_deg < 40:
		return "orange"
	if h_deg < 70:
		return "yellow"
	if h_deg < 165:
		return "green"
	if h_deg < 200:
		return "cyan"
	if h_deg < 255:
		return "blue"
	if h_deg < 290:
		return "purple"
	if h_deg < 345:
		return "magenta"
	if centroid_nm >= 600:
		return "warm"
	return "unknown"


def analyze_spectrum(raw, dark_ref=None, white_ref=None):
	corrected = _calibrate_bands(raw, dark_ref=dark_ref, white_ref=white_ref)
	channels = [(band, corrected[band]) for band in SPECTRAL_BANDS]

	total = float(sum(v for _, v in channels))
	if total <= 1e-12:
		raise AS7341Error("Invalid spectral sum: 0")

	dominant_band, dominant_value = max(channels, key=lambda x: x[1])
	dominant_nm = WAVELENGTHS_NM[dominant_band]
	centroid_nm = sum(WAVELENGTHS_NM[k] * v for k, v in channels) / total
	peak_ratio = dominant_value / total

	_, _, _, x, y, z = _compute_xyz(corrected)
	r, g, b = _xyz_chromaticity_to_srgb(x, y, z)
	red, green, blue = _compute_energy(corrected)
	h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
	h_deg = h * 360.0
	color_name = _name_from_hsv(h_deg, s, v, centroid_nm)
	confidence = _clip((0.55 * s) + (0.45 * min(1.0, peak_ratio * 3.0)), 0.0, 1.0)

	clear = float(raw["clear"])
	nir = float(raw["nir"])
	nir_ratio = nir / max(clear, 1.0)

	return {
		"dominant_band": dominant_band,
		"dominant_wavelength_nm": dominant_nm,
		"dominant_value": round(dominant_value, 4),
		"spectral_centroid_nm": round(centroid_nm, 2),
		"cie_xy": {"x": round(x, 5), "y": round(y, 5)},
		"srgb": {"r": r, "g": g, "b": b},
		"hsv": {
			"h_deg": round(h_deg, 2),
			"s": round(s, 4),
			"v": round(v, 4),
		},
		"color_name": color_name,
		"confidence": round(confidence, 4),
		"energy": {
			"red_sum": round(red, 2),
			"green_sum": round(green, 2),
			"blue_sum": round(blue, 2),
		},
		"calibrated": {
			"white_reference_used": white_ref is not None,
			"dark_reference_used": dark_ref is not None,
		},
		"nir_ratio": round(nir_ratio, 4),
	}


def _print_human(raw, result):
	print(
		"RAW  F1={:5d} F2={:5d} F3={:5d} F4={:5d} F5={:5d} F6={:5d} F7={:5d} F8={:5d} CLEAR={:5d} NIR={:5d}".format(
			raw["f1_415"],
			raw["f2_445"],
			raw["f3_480"],
			raw["f4_515"],
			raw["f5_555"],
			raw["f6_590"],
			raw["f7_630"],
			raw["f8_680"],
			raw["clear"],
			raw["nir"],
		)
	)
	print(
		"ANL  dominant={}({}nm) centroid={}nm cie_xy=({:.4f},{:.4f}) rgb=({}, {}, {}) hsv=({:.1f}deg, {:.3f}, {:.3f}) color={} conf={:.2f} nir_ratio={}".format(
			result["dominant_band"],
			result["dominant_wavelength_nm"],
			result["spectral_centroid_nm"],
			result["cie_xy"]["x"],
			result["cie_xy"]["y"],
			result["srgb"]["r"],
			result["srgb"]["g"],
			result["srgb"]["b"],
			result["hsv"]["h_deg"],
			result["hsv"]["s"],
			result["hsv"]["v"],
			result["color_name"],
			result["confidence"],
			result["nir_ratio"],
		)
	)


def main():
	parser = argparse.ArgumentParser(description="Analyze AS7341 spectrum and output color information")
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
	parser.add_argument(
		"--disable-reference-calibration",
		action="store_true",
		help="Ignore white_reference/dark_reference in YAML",
	)
	parser.add_argument("--json", action="store_true", help="Output compact JSON per sample")
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
		dark_ref = None if args.disable_reference_calibration else _load_reference(cfg, "dark_reference")
		white_ref = None if args.disable_reference_calibration else _load_reference(cfg, "white_reference")

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
			"AS7341-color on /dev/i2c-{} address=0x{:02X} atime={} astep={} gain={}x tint={:.3f}ms".format(
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
			raw = sensor.read_with_retry(
				max_retries=max_retries,
				retry_interval_s=retry_interval_s,
				ready_timeout_s=ready_timeout_s,
			)
			result = analyze_spectrum(raw, dark_ref=dark_ref, white_ref=white_ref)

			if args.json:
				print(json.dumps({"sample": idx, "raw": raw, "analysis": result}, ensure_ascii=True))
			else:
				print(f"sample={idx}")
				_print_human(raw, result)

			if count > 0 and idx >= count:
				break
			time.sleep(interval_s)

	except AS7341Error as exc:
		print(f"AS7341-color error: {exc}")
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())

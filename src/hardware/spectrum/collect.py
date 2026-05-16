#!/usr/bin/env python3

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
	from .AS7341 import AS7341, AS7341Error, _cfg_or_default, _read_optional_config, _to_i2c_addr
	from .color import analyze_spectrum, _load_reference
except ImportError:
	from AS7341 import AS7341, AS7341Error, _cfg_or_default, _read_optional_config, _to_i2c_addr
	from color import analyze_spectrum, _load_reference


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = PROJECT_ROOT / "datas" / "spectrum_quality_samples.csv"


CSV_COLUMNS = [
	"timestamp_iso",
	"timestamp_ms",
	"sample_index",
	"sample_id",
	"fruit_type_manual",
	"fruit_variety_manual",
	"yolo_fruit_type",
	"yolo_fruit_type_conf",
	"yolo_maturity",
	"yolo_maturity_conf",
	"yolo_defect",
	"yolo_defect_conf",
	"yolo_bbox_xyxy",
	"fruit_type_final",
	"maturity_final",
	"defect_final",
	"quality_grade",
	"brix_label",
	"quality_label",
	"note",
	"sensor_bus",
	"sensor_address",
	"atime",
	"astep",
	"gain",
	"integration_time_ms",
	"f1_415",
	"f2_445",
	"f3_480",
	"f4_515",
	"f5_555",
	"f6_590",
	"f7_630",
	"f8_680",
	"clear",
	"nir",
	"nir_ratio",
	"dominant_band",
	"dominant_wavelength_nm",
	"dominant_value",
	"spectral_centroid_nm",
	"cie_x",
	"cie_y",
	"srgb_r",
	"srgb_g",
	"srgb_b",
	"hsv_h_deg",
	"hsv_s",
	"hsv_v",
	"color_name",
	"confidence",
	"red_sum",
	"green_sum",
	"blue_sum",
	"calib_white_ref",
	"calib_dark_ref",
	"raw_json",
	"analysis_json",
]


def _clean_text(value, fallback=""):
	text = str(value or "").strip()
	if text:
		return text
	return fallback


def _as_optional_float(value):
	text = _clean_text(value)
	if not text:
		return ""
	return float(text)


def _sample_id_for_sample(base_id, prefix, sample_index):
	if base_id:
		return base_id
	if prefix:
		return f"{prefix}-{sample_index:04d}"
	return f"sample-{sample_index:04d}"


def _pick_final(yolo_value, manual_value, unknown="unknown"):
	if _clean_text(yolo_value):
		return _clean_text(yolo_value)
	if _clean_text(manual_value):
		return _clean_text(manual_value)
	return unknown


def _infer_quality_grade(defect_final, maturity_final, brix_label, quality_label):
	if _clean_text(quality_label):
		return _clean_text(quality_label)

	defect = _clean_text(defect_final).lower()
	maturity = _clean_text(maturity_final).lower()
	brix = brix_label if isinstance(brix_label, float) else None

	defect_bad = {
		"defect",
		"bad",
		"damaged",
		"rotten",
		"bruise",
		"blemish",
		"有缺陷",
		"损伤",
		"腐烂",
	}
	if defect in defect_bad:
		return "reject"

	ripe_set = {"ripe", "成熟"}
	unripe_set = {"unripe", "未熟", "生"}

	if maturity in unripe_set:
		return "not_ready"
	if maturity in ripe_set and brix is not None:
		if brix >= 14.0:
			return "premium"
		if brix >= 12.0:
			return "good"
		return "normal"
	if maturity in ripe_set:
		return "normal"
	return "unknown"


def _build_row(
	raw,
	analysis,
	sample_index,
	sample_id,
	fruit_type_manual,
	fruit_variety_manual,
	yolo_fruit_type,
	yolo_fruit_type_conf,
	yolo_maturity,
	yolo_maturity_conf,
	yolo_defect,
	yolo_defect_conf,
	yolo_bbox_xyxy,
	maturity_manual,
	defect_manual,
	brix_label,
	quality_label,
	note,
	bus,
	address,
	atime,
	astep,
	gain,
	integration_time_ms,
):
	now = datetime.now()
	timestamp_iso = now.isoformat(timespec="milliseconds")
	timestamp_ms = int(now.timestamp() * 1000)

	fruit_type_final = _pick_final(yolo_fruit_type, fruit_type_manual)
	maturity_final = _pick_final(yolo_maturity, maturity_manual)
	defect_final = _pick_final(yolo_defect, defect_manual, unknown="none")
	quality_grade = _infer_quality_grade(defect_final, maturity_final, brix_label, quality_label)

	return {
		"timestamp_iso": timestamp_iso,
		"timestamp_ms": timestamp_ms,
		"sample_index": sample_index,
		"sample_id": sample_id,
		"fruit_type_manual": fruit_type_manual,
		"fruit_variety_manual": fruit_variety_manual,
		"yolo_fruit_type": yolo_fruit_type,
		"yolo_fruit_type_conf": yolo_fruit_type_conf,
		"yolo_maturity": yolo_maturity,
		"yolo_maturity_conf": yolo_maturity_conf,
		"yolo_defect": yolo_defect,
		"yolo_defect_conf": yolo_defect_conf,
		"yolo_bbox_xyxy": yolo_bbox_xyxy,
		"fruit_type_final": fruit_type_final,
		"maturity_final": maturity_final,
		"defect_final": defect_final,
		"quality_grade": quality_grade,
		"brix_label": "" if brix_label == "" else brix_label,
		"quality_label": quality_label,
		"note": note,
		"sensor_bus": bus,
		"sensor_address": f"0x{address:02X}",
		"atime": atime,
		"astep": astep,
		"gain": gain,
		"integration_time_ms": round(float(integration_time_ms), 4),
		"f1_415": raw["f1_415"],
		"f2_445": raw["f2_445"],
		"f3_480": raw["f3_480"],
		"f4_515": raw["f4_515"],
		"f5_555": raw["f5_555"],
		"f6_590": raw["f6_590"],
		"f7_630": raw["f7_630"],
		"f8_680": raw["f8_680"],
		"clear": raw["clear"],
		"nir": raw["nir"],
		"nir_ratio": analysis["nir_ratio"],
		"dominant_band": analysis["dominant_band"],
		"dominant_wavelength_nm": analysis["dominant_wavelength_nm"],
		"dominant_value": analysis["dominant_value"],
		"spectral_centroid_nm": analysis["spectral_centroid_nm"],
		"cie_x": analysis["cie_xy"]["x"],
		"cie_y": analysis["cie_xy"]["y"],
		"srgb_r": analysis["srgb"]["r"],
		"srgb_g": analysis["srgb"]["g"],
		"srgb_b": analysis["srgb"]["b"],
		"hsv_h_deg": analysis["hsv"]["h_deg"],
		"hsv_s": analysis["hsv"]["s"],
		"hsv_v": analysis["hsv"]["v"],
		"color_name": analysis["color_name"],
		"confidence": analysis["confidence"],
		"red_sum": analysis["energy"]["red_sum"],
		"green_sum": analysis["energy"]["green_sum"],
		"blue_sum": analysis["energy"]["blue_sum"],
		"calib_white_ref": analysis["calibrated"]["white_reference_used"],
		"calib_dark_ref": analysis["calibrated"]["dark_reference_used"],
		"raw_json": json.dumps(raw, ensure_ascii=True, separators=(",", ":")),
		"analysis_json": json.dumps(analysis, ensure_ascii=True, separators=(",", ":")),
	}


def main():
	parser = argparse.ArgumentParser(description="Capture spectrum dataset for multi-fruit quality detection")
	parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="CSV output path")
	parser.add_argument("--append", action="store_true", help="Append to existing CSV file")

	parser.add_argument("--sample-id", default="", help="Fixed sample id for all rows")
	parser.add_argument("--sample-id-prefix", default="fruit", help="Prefix for auto-generated sample id")

	# Manual fields (available before YOLO is integrated).
	parser.add_argument("--fruit-type", default="", help="Manual fruit type, e.g. apple, orange")
	parser.add_argument("--fruit-variety", default="", help="Manual fruit variety, e.g. fuji")
	parser.add_argument("--maturity", default="", help="Manual maturity label")
	parser.add_argument("--defect", default="", help="Manual defect label")

	# YOLO placeholder fields (to be filled when visual module is ready).
	parser.add_argument("--yolo-fruit-type", default="", help="YOLO detected fruit type")
	parser.add_argument("--yolo-fruit-type-conf", default="", help="YOLO fruit type confidence")
	parser.add_argument("--yolo-maturity", default="", help="YOLO detected maturity label")
	parser.add_argument("--yolo-maturity-conf", default="", help="YOLO maturity confidence")
	parser.add_argument("--yolo-defect", default="", help="YOLO detected defect label")
	parser.add_argument("--yolo-defect-conf", default="", help="YOLO defect confidence")
	parser.add_argument("--yolo-bbox", default="", help="YOLO bbox in x1,y1,x2,y2")

	parser.add_argument("--brix-label", type=float, default=None, help="Optional Brix label")
	parser.add_argument("--quality-label", default="", help="Optional manual quality label")
	parser.add_argument("--note", default="", help="Optional note")

	# Backward-compatible aliases.
	parser.add_argument("--apple-id", default="", help=argparse.SUPPRESS)
	parser.add_argument("--apple-id-prefix", default="", help=argparse.SUPPRESS)
	parser.add_argument("--apple-variety", default="", help=argparse.SUPPRESS)

	parser.add_argument("--bus", type=int, default=None, help="I2C bus number, override YAML")
	parser.add_argument("--address", type=lambda x: int(x, 0), default=None, help="I2C address (e.g. 0x39)")
	parser.add_argument("--atime", type=int, default=None, help="Integration step count (0..255)")
	parser.add_argument("--astep", type=int, default=None, help="Integration step size (0..65535)")
	parser.add_argument("--gain", type=float, default=None, help="Sensor gain (0.5,1,2,...,512)")
	parser.add_argument("--ready-timeout", type=float, default=None, help="Timeout waiting data-ready")
	parser.add_argument("--interval", type=float, default=None, help="Read interval in seconds")
	parser.add_argument("--count", type=int, default=1, help="Read count, 0 means infinite")
	parser.add_argument("--max-retries", type=int, default=None, help="Max retries per sample")
	parser.add_argument("--retry-interval", type=float, default=None, help="Retry interval in seconds")
	parser.add_argument(
		"--disable-reference-calibration",
		action="store_true",
		help="Ignore white_reference/dark_reference in YAML",
	)
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
		count = int(args.count)
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

		output_path = Path(args.output).expanduser()
		if not output_path.is_absolute():
			output_path = PROJECT_ROOT / output_path
		output_path.parent.mkdir(parents=True, exist_ok=True)

		write_header = True
		mode = "w"
		if args.append and output_path.exists() and output_path.stat().st_size > 0:
			mode = "a"
			write_header = False

		sensor = AS7341(bus=bus, address=address, atime=atime, astep=astep, gain=gain)
		sensor.initialize()

		print(
			"spectrum-collect on /dev/i2c-{} address=0x{:02X} -> {}".format(
				bus,
				address,
				output_path,
			)
		)

		sample_id_base = _clean_text(args.sample_id) or _clean_text(args.apple_id)
		sample_prefix = _clean_text(args.sample_id_prefix) or _clean_text(args.apple_id_prefix) or "fruit"
		fruit_type_manual = _clean_text(args.fruit_type)
		fruit_variety_manual = _clean_text(args.fruit_variety) or _clean_text(args.apple_variety)
		maturity_manual = _clean_text(args.maturity)
		defect_manual = _clean_text(args.defect)

		with output_path.open(mode, encoding="utf-8", newline="") as fp:
			writer = csv.DictWriter(fp, fieldnames=CSV_COLUMNS)
			if write_header:
				writer.writeheader()

			sample_index = 0
			while True:
				sample_index += 1
				raw = sensor.read_with_retry(
					max_retries=max_retries,
					retry_interval_s=retry_interval_s,
					ready_timeout_s=ready_timeout_s,
				)
				analysis = analyze_spectrum(raw, dark_ref=dark_ref, white_ref=white_ref)

				sample_id = _sample_id_for_sample(sample_id_base, sample_prefix, sample_index)
				row = _build_row(
					raw=raw,
					analysis=analysis,
					sample_index=sample_index,
					sample_id=sample_id,
					fruit_type_manual=fruit_type_manual,
					fruit_variety_manual=fruit_variety_manual,
					yolo_fruit_type=_clean_text(args.yolo_fruit_type),
					yolo_fruit_type_conf=_as_optional_float(args.yolo_fruit_type_conf),
					yolo_maturity=_clean_text(args.yolo_maturity),
					yolo_maturity_conf=_as_optional_float(args.yolo_maturity_conf),
					yolo_defect=_clean_text(args.yolo_defect),
					yolo_defect_conf=_as_optional_float(args.yolo_defect_conf),
					yolo_bbox_xyxy=_clean_text(args.yolo_bbox),
					maturity_manual=maturity_manual,
					defect_manual=defect_manual,
					brix_label="" if args.brix_label is None else float(args.brix_label),
					quality_label=_clean_text(args.quality_label),
					note=_clean_text(args.note),
					bus=bus,
					address=address,
					atime=atime,
					astep=astep,
					gain=gain,
					integration_time_ms=sensor.integration_time_ms,
				)
				writer.writerow(row)
				fp.flush()

				print(
					"sample={} id={} fruit={} maturity={} defect={} grade={} color={} conf={}".format(
						sample_index,
						sample_id,
						row["fruit_type_final"],
						row["maturity_final"],
						row["defect_final"],
						row["quality_grade"],
						analysis["color_name"],
						analysis["confidence"],
					)
				)

				if count > 0 and sample_index >= count:
					break
				time.sleep(interval_s)

		print("CSV saved: {}".format(output_path))

	except AS7341Error as exc:
		print(f"spectrum-collect error: {exc}")
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())

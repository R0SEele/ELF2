#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "datas" / "csv" / "sensor_realtime.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "datas" / "import" / "environment_history_7d.json"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "tuya_cloud.json"
VALUE_FIELDS = (
    "temperature_c",
    "humidity_rh",
    "co2_ppm",
    "light_lux",
    "air_quality_ppm",
)
STATUS_MAP = {
    "正常": "normal",
    "部分异常": "partial_error",
    "异常": "error",
    "未知": "unknown",
    "normal": "normal",
    "partial_error": "partial_error",
    "error": "error",
    "unknown": "unknown",
}


def parse_number(value):
    text = str(value or "").strip()
    if not text or text == "--":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_device_id(config_path):
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    device_id = str(config.get("device_id") or "").strip()
    if not device_id:
        raise ValueError(f"device_id is missing in {config_path}")
    return device_id


def load_records(csv_path, device_id, timezone):
    records_by_timestamp = {}
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            timestamp_text = str(row.get("timestamp") or "").strip()
            try:
                local_time = datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone
                )
            except ValueError:
                continue

            values = {}
            for field in VALUE_FIELDS:
                value = parse_number(row.get(field))
                if value is not None:
                    values[field] = value
            if not values:
                continue

            timestamp = int(local_time.timestamp() * 1000)
            record_id = "env_" + hashlib.sha1(
                f"{device_id}:{timestamp}".encode("utf-8")
            ).hexdigest()[:20]
            record = {
                "_id": record_id,
                "device_id": device_id,
                "timestamp": timestamp,
                "values": values,
                "env_status": STATUS_MAP.get(
                    str(row.get("env_status") or "").strip(), "unknown"
                ),
                "source": "rk3588_csv_import",
            }
            sensor_errors = str(row.get("sensor_errors") or "").strip()
            if sensor_errors:
                record["sensor_errors"] = sensor_errors
            records_by_timestamp[timestamp] = record
    return [records_by_timestamp[key] for key in sorted(records_by_timestamp)]


def main():
    parser = argparse.ArgumentParser(
        description="Convert RK3588 environment CSV to CloudBase JSON Lines"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device-id", default="")
    parser.add_argument("--days", type=float, default=7.0)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    if args.days <= 0:
        parser.error("--days must be greater than zero")
    timezone = ZoneInfo(args.timezone)
    device_id = args.device_id.strip() or load_device_id(args.config)
    records = load_records(args.input, device_id, timezone)
    if not records:
        raise SystemExit(f"no valid environment records found in {args.input}")

    latest_timestamp = records[-1]["timestamp"]
    cutoff = latest_timestamp - int(timedelta(days=args.days).total_seconds() * 1000)
    records = [record for record in records if record["timestamp"] >= cutoff]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    temporary_path.replace(args.output)

    first_time = datetime.fromtimestamp(records[0]["timestamp"] / 1000, timezone)
    last_time = datetime.fromtimestamp(records[-1]["timestamp"] / 1000, timezone)
    print(f"wrote {len(records)} records to {args.output}")
    print(f"range: {first_time.isoformat()} -> {last_time.isoformat()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import argparse
import csv
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from .EM import EMError, EnvironmentMonitor, _load_sensor_config
except ImportError:
    from EM import EMError, EnvironmentMonitor, _load_sensor_config


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "datas" / "csv"
DEFAULT_FILE_NAME = "sensor_realtime.csv"
CSV_FIELDS = [
    "temperature_c",
    "humidity_rh",
    "co2_ppm",
    "light_lux",
    "air_quality_ppm",
    "env_status",
    "timestamp",
    "sensor_errors",
]

_running = True


def _handle_signal(_signum, _frame):
    global _running
    _running = False


def _fmt(value, digits=2):
    if value is None:
        return "--"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _payload(readings, name):
    return readings.get(name, {"ok": False, "error": "missing reading"})


def _build_row(readings, scd40_cache=None, scd40_cache_max_age_s=20.0):
    now_monotonic = time.monotonic()
    sht30 = _payload(readings, "sht30")
    scd40 = _payload(readings, "scd40")
    gy302 = _payload(readings, "gy302")
    mq135 = _payload(readings, "mq135")

    scd40_for_row = scd40
    scd40_using_cache = False
    if scd40.get("ok"):
        if scd40_cache is not None:
            scd40_cache["payload"] = dict(scd40)
            scd40_cache["updated_at"] = now_monotonic
    elif scd40_cache is not None and "payload" in scd40_cache:
        cached_age_s = now_monotonic - float(scd40_cache.get("updated_at", 0.0))
        if cached_age_s <= scd40_cache_max_age_s:
            scd40_for_row = dict(scd40_cache["payload"])
            scd40_using_cache = True

    temperature_c = None
    humidity_rh = None
    if sht30.get("ok"):
        temperature_c = sht30.get("temperature_c")
        humidity_rh = sht30.get("humidity_rh")
    elif scd40_for_row.get("ok"):
        temperature_c = scd40_for_row.get("temperature_c")
        humidity_rh = scd40_for_row.get("humidity_rh")

    errors = []
    for name, payload in readings.items():
        if name == "scd40" and scd40_using_cache:
            continue
        if not payload.get("ok"):
            errors.append(f"{name}:{payload.get('error', 'unknown error')}")

    return {
        "temperature_c": _fmt(temperature_c),
        "humidity_rh": _fmt(humidity_rh),
        "co2_ppm": _fmt(scd40_for_row.get("co2_ppm") if scd40_for_row.get("ok") else None, digits=0),
        "light_lux": _fmt(gy302.get("lux") if gy302.get("ok") else None),
        "air_quality_ppm": _fmt(mq135.get("level_pct") if mq135.get("ok") else None),
        "env_status": "正常" if not errors else "部分异常",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sensor_errors": "; ".join(errors),
    }


def _ensure_header(csv_path):
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())


def _append_row(csv_path, row):
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def _parent_is_alive(parent_pid):
    if parent_pid <= 0:
        return True
    if os.getppid() != parent_pid:
        return False
    try:
        os.kill(parent_pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def main():
    parser = argparse.ArgumentParser(description="Continuously write environment sensor readings to CSV")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="CSV output directory")
    parser.add_argument("--file-name", default=DEFAULT_FILE_NAME, help="CSV file name")
    parser.add_argument("--interval", type=float, default=None, help="Sample interval in seconds")
    parser.add_argument("--count", type=int, default=0, help="Sample count, 0 means infinite")
    parser.add_argument("--parent-pid", type=int, default=0, help="Exit when this parent process is gone")
    args = parser.parse_args()

    if args.count < 0:
        print("count must be >= 0", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / args.file_name

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    monitor = None
    try:
        sensors_cfg = _load_sensor_config()
        em_cfg = sensors_cfg.get("em", {})
        interval_s = args.interval
        if interval_s is None:
            interval_s = float(em_cfg.get("read_interval_s", 5.0))
        scd40_cache_max_age_s = float(em_cfg.get("co2_cache_max_age_s", 20.0))
        if interval_s < 0:
            print("interval must be >= 0", file=sys.stderr)
            return 1
        if scd40_cache_max_age_s < 0:
            print("co2_cache_max_age_s must be >= 0", file=sys.stderr)
            return 1

        monitor = EnvironmentMonitor(sensors_cfg=sensors_cfg)
        _ensure_header(csv_path)
        scd40_cache = {}

        sample_index = 0
        while _running:
            if not _parent_is_alive(args.parent_pid):
                break

            sample_index += 1
            row = _build_row(
                monitor.read_all(),
                scd40_cache=scd40_cache,
                scd40_cache_max_age_s=scd40_cache_max_age_s,
            )
            _append_row(csv_path, row)
            print(f"updated {csv_path} #{sample_index}", file=sys.stderr, flush=True)

            if args.count > 0 and sample_index >= args.count:
                break
            sleep_until = time.monotonic() + interval_s
            while _running and time.monotonic() < sleep_until:
                if not _parent_is_alive(args.parent_pid):
                    return 0
                time.sleep(min(0.2, max(0.0, sleep_until - time.monotonic())))
    except EMError as exc:
        print(f"sensor csv logger error: {exc}", file=sys.stderr)
        return 1
    finally:
        if monitor is not None:
            monitor.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

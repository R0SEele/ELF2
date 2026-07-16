import csv
import queue
import subprocess
import threading
import time
from pathlib import Path

import yaml


PROJECT_ROOT = Path("/home/elf/projects")
DEFAULT_SERVO_CONFIG = PROJECT_ROOT / "config" / "servo.yaml"
DEFAULT_SORTER_SCRIPT = PROJECT_ROOT / "src" / "hardware" / "servo" / "sorter.py"
DEFAULT_EVENT_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_sorter_events.csv"

EVENT_FIELDS = [
    "timestamp",
    "mango_id",
    "position",
    "quality_grade",
    "suggested_channel",
    "final_status",
    "delay_s",
    "result",
    "message",
]


def _load_auto_sort_config(config_path=DEFAULT_SERVO_CONFIG):
    try:
        with Path(config_path).open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    return data.get("servo", {}).get("auto_sort", {}) or {}


def _append_event(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in EVENT_FIELDS})


class AutoSorter:
    def __init__(self, config_path=DEFAULT_SERVO_CONFIG, sorter_script=DEFAULT_SORTER_SCRIPT):
        self.config_path = Path(config_path)
        self.sorter_script = Path(sorter_script)
        self.config = _load_auto_sort_config(self.config_path)
        self.enabled = bool(self.config.get("enabled", False))
        self.delay_s = max(0.0, float(self.config.get("delay_s", 0.8)))
        self.reset_to_center = bool(self.config.get("reset_to_center", True))
        self.reset_delay_s = max(0.0, float(self.config.get("reset_delay_s", 0.45)))
        self.default_position = str(self.config.get("default_position", "2"))
        self.log_csv = Path(self.config.get("log_csv", DEFAULT_EVENT_CSV))
        self.channel_positions = {
            str(key): str(value) for key, value in (self.config.get("channel_positions") or {}).items()
        }
        self.grade_positions = {
            str(key): str(value) for key, value in (self.config.get("grade_positions") or {}).items()
        }
        self.sorted_ids = set()
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker = None
        if self.enabled:
            self._worker = threading.Thread(target=self._run_worker, name="mango-auto-sorter", daemon=True)
            self._worker.start()

    def position_for(self, assessment):
        channel = str(getattr(assessment, "suggested_channel", "") or "")
        grade = str(getattr(assessment, "quality_grade", "") or "")
        if channel in self.channel_positions:
            return self.channel_positions[channel]
        if grade in self.grade_positions:
            return self.grade_positions[grade]
        return self.default_position

    def sort_once(self, assessment):
        if not self.enabled:
            return False

        mango_id = str(getattr(assessment, "mango_id", "") or "").strip()
        if not mango_id or mango_id == "--" or mango_id in self.sorted_ids:
            return False

        self.sorted_ids.add(mango_id)
        position = self.position_for(assessment)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "timestamp": timestamp,
            "mango_id": mango_id,
            "position": position,
            "quality_grade": getattr(assessment, "quality_grade", ""),
            "suggested_channel": getattr(assessment, "suggested_channel", ""),
            "final_status": getattr(assessment, "final_status", ""),
            "delay_s": "{:.2f}".format(self.delay_s),
        }
        execute_at = time.monotonic() + self.delay_s
        self._queue.put((execute_at, position, row))
        return True

    def _run_worker(self):
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                execute_at, position, row = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._execute_sort(position, row, execute_at)
            finally:
                self._queue.task_done()

    def _execute_sort(self, position, row, execute_at=None):
        if execute_at is not None:
            remaining = execute_at - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)

        cmd = ["python3", str(self.sorter_script), position, "--config", str(self.config_path)]
        if self.reset_to_center and position != "2":
            cmd.append("--hold-after-move")
        try:
            result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=5)
            message = (result.stdout or result.stderr or "").strip()
            row["result"] = "ok" if result.returncode == 0 else "failed"
            row["message"] = message[:180]
        except Exception as exc:
            row["result"] = "failed"
            row["message"] = str(exc)[:180]
            _append_event(self.log_csv, row)
            return False

        if result.returncode != 0:
            _append_event(self.log_csv, row)
            return False

        if self.reset_to_center and position != "2":
            if self.reset_delay_s > 0:
                time.sleep(self.reset_delay_s)
            try:
                reset_result = subprocess.run(
                    ["python3", str(self.sorter_script), "2", "--config", str(self.config_path)],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception as exc:
                row["result"] = "reset_failed"
                row["message"] = str(exc)[:180]
                _append_event(self.log_csv, row)
                return False
            if reset_result.returncode != 0:
                row["result"] = "reset_failed"
                row["message"] = (reset_result.stderr or reset_result.stdout or "").strip()[:180]
                _append_event(self.log_csv, row)
                return False

        _append_event(self.log_csv, row)
        return True

    def close(self, drain=True, timeout_s=8.0):
        if drain and self.enabled:
            deadline = time.time() + max(0.0, timeout_s)
            while not self._queue.empty() and time.time() < deadline:
                time.sleep(0.05)
        self._stop_event.set()
        if self._worker is not None:
            remaining = max(0.0, timeout_s)
            self._worker.join(timeout=remaining)

import csv
import queue
import importlib.util
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
YOLO_DIR = PROJECT_ROOT / "deeplearning" / "yolo11_demo"
QUALITY_DIR = PROJECT_ROOT / "src" / "software" / "mango_quality"
for path in (YOLO_DIR, QUALITY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import camera_detect
import mango_quality_cli
import rknn_pool
from auto_sorter import AutoSorter
from fusion import BatchAccumulator, QualityAssessment, write_assessment_history_csv


PROXY_SPEC = importlib.util.spec_from_file_location(
    "tuya_proxy_test_module", PROJECT_ROOT / "cloud" / "tuya_proxy" / "tuya_proxy.py"
)
tuya_proxy = importlib.util.module_from_spec(PROXY_SPEC)
PROXY_SPEC.loader.exec_module(tuya_proxy)


def mango_feature(center_x, center_y=200):
    return {
        "x1": center_x - 25,
        "y1": center_y - 25,
        "x2": center_x + 25,
        "y2": center_y + 25,
        "area_px": 2500,
        "label": "mango_ripe",
        "confidence": 0.9,
    }


class MangoTrackerTests(unittest.TestCase):
    frame_shape = (600, 1000, 3)

    def run_track(self, tracker, positions, missed_frames=8):
        completed = []
        frame_index = 0
        for position in positions:
            frame_index += 1
            completed.extend(
                tracker.update([mango_feature(position)], frame_index, self.frame_shape)
            )
        for _ in range(missed_frames):
            frame_index += 1
            completed.extend(tracker.update([], frame_index, self.frame_shape))
        return completed

    def test_crossing_mango_is_counted_only_once(self):
        tracker = camera_detect.MangoTracker(
            min_frames=4,
            max_missed=6,
            count_axis="x",
            count_direction="positive",
            exit_count=True,
        )
        completed = self.run_track(tracker, (600, 650, 700, 760, 800, 840, 880, 920))

        self.assertEqual([item["mango_id"] for item in completed], [1])
        self.assertEqual(tracker.completed_count, 1)

    def test_stationary_disappearing_mango_is_not_counted(self):
        tracker = camera_detect.MangoTracker(
            min_frames=4,
            max_missed=6,
            count_axis="x",
            count_direction="positive",
            exit_count=True,
        )
        completed = self.run_track(tracker, (100, 100, 100, 100))

        self.assertEqual(completed, [])
        self.assertEqual(tracker.completed_count, 0)

    def test_mango_already_past_line_can_use_gated_exit_count(self):
        tracker = camera_detect.MangoTracker(
            min_frames=4,
            max_missed=6,
            count_axis="x",
            count_direction="positive",
            exit_count=True,
        )
        completed = self.run_track(tracker, (800, 850, 900, 940))

        self.assertEqual(len(completed), 1)
        self.assertEqual(tracker.completed_count, 1)

    def test_moving_mango_is_counted_when_detection_is_lost_before_edge(self):
        tracker = camera_detect.MangoTracker(
            min_frames=4,
            max_missed=6,
            count_axis="x",
            count_direction="positive",
            exit_count=True,
        )
        completed = self.run_track(tracker, (180, 200, 220, 240))

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["stable_frames"], 4)
        self.assertEqual(tracker.completed_count, 1)


class LatestQtFrameWriterTests(unittest.TestCase):
    def test_slow_preview_consumer_does_not_block_frame_submission(self):
        first_write_started = threading.Event()
        allow_writes = threading.Event()
        latest_write_finished = threading.Event()
        written = []

        def slow_write(_output, frame, _quality):
            first_write_started.set()
            allow_writes.wait(1.0)
            written.append(frame)
            if frame == "frame-19":
                latest_write_finished.set()
            return True

        with mock.patch.object(camera_detect, "write_qt_frame", side_effect=slow_write):
            writer = camera_detect.LatestQtFrameWriter(mock.Mock(), 82)
            try:
                self.assertTrue(writer.submit("frame-1"))
                self.assertTrue(first_write_started.wait(0.5))
                started_at = time.monotonic()
                for index in range(2, 20):
                    self.assertTrue(writer.submit("frame-{}".format(index)))
                self.assertLess(time.monotonic() - started_at, 0.1)
                allow_writes.set()
                self.assertTrue(latest_write_finished.wait(0.5))
            finally:
                writer.close(timeout=1.0)

        self.assertEqual(written, ["frame-1", "frame-19"])


class QualityPipelineTests(unittest.TestCase):
    def test_model_label_order_matches_exported_class_channels(self):
        labels = camera_detect.load_labels(YOLO_DIR / "labels.txt")
        self.assertEqual(labels, ["mango_overripe", "mango_ripe", "mango_unripe"])

    def test_batch_uses_short_sequential_ids_and_restores_source_mapping(self):
        first = QualityAssessment(
            timestamp="2026-07-16 10:38:03",
            vision_timestamp="2026-07-16 10:38:02",
            mango_id="20",
            final_status="可接受",
            reason="芒果#20连续检测40帧",
        )
        batch = BatchAccumulator("test-batch")
        self.assertEqual(batch.assign_mango_id(first), "1")
        self.assertTrue(batch.add(first))
        self.assertEqual(first.reason, "芒果#1连续检测40帧")

        repeated = QualityAssessment(
            timestamp="2026-07-16 10:38:04",
            vision_timestamp="2026-07-16 10:38:02",
            mango_id="20",
            final_status="可接受",
        )
        self.assertEqual(batch.assign_mango_id(repeated), "1")
        self.assertFalse(batch.add(repeated))

        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "batch.json"
            batch.save(state_path)
            restored = BatchAccumulator.load(state_path)

        after_restart = QualityAssessment(
            timestamp="2026-07-16 10:38:05",
            vision_timestamp="2026-07-16 10:38:02",
            mango_id="20",
            final_status="可接受",
        )
        self.assertEqual(restored.assign_mango_id(after_restart), "1")
        self.assertFalse(restored.add(after_restart))

        second = QualityAssessment(
            timestamp="2026-07-16 10:39:05",
            vision_timestamp="2026-07-16 10:39:05",
            mango_id="21",
            final_status="可接受",
        )
        self.assertEqual(restored.assign_mango_id(second), "2")
        self.assertTrue(restored.add(second))

    def test_same_short_id_from_different_batches_keeps_both_history_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "history.csv"
            first = QualityAssessment(
                timestamp="2026-07-16 10:00:00",
                mango_id="1",
                final_status="可接受",
            )
            second = QualityAssessment(
                timestamp="2026-07-16 11:00:00",
                mango_id="1",
                final_status="可接受",
            )
            self.assertTrue(write_assessment_history_csv(history_path, first))
            self.assertTrue(write_assessment_history_csv(history_path, second))
            with history_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual([row["mango_id"] for row in rows], ["1", "1"])
        self.assertEqual(len(rows), 2)

    def test_completed_track_updates_history_and_batch(self):
        frame_shape = (600, 1000, 3)
        tracker = camera_detect.MangoTracker(
            min_frames=4,
            max_missed=2,
            count_axis="x",
            count_direction="positive",
            exit_count=True,
        )
        completed = []
        frame_index = 0
        for position in (180, 200, 220, 240):
            frame_index += 1
            completed.extend(tracker.update([mango_feature(position)], frame_index, frame_shape))
        for _ in range(3):
            frame_index += 1
            completed.extend(tracker.update([], frame_index, frame_shape))

        self.assertEqual(len(completed), 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            object_csv = root / "object.csv"
            object_json = root / "object.json"
            history_csv = root / "history.csv"
            batch_csv = root / "batch.csv"
            camera_detect.write_object_result(object_csv, object_json, completed[0])

            args = SimpleNamespace(
                object_csv=str(object_csv),
                vision_csv=str(root / "vision.csv"),
                spectrum_csv=str(root / "spectrum.csv"),
                vision_stale_seconds=5.0,
                spectrum_stale_seconds=30.0,
                output_csv=str(root / "quality.csv"),
                output_json=str(root / "quality.json"),
                history_csv=str(history_csv),
                batch_csv=str(batch_csv),
                batch_json=str(root / "batch.json"),
                batch_state_json=str(root / "batch_state.json"),
                control_state_json=str(root / "control.json"),
                no_json=False,
            )
            batch = BatchAccumulator("test-batch")
            assessment = mango_quality_cli.run_once(args, batch=batch, sorter=None)

            self.assertNotEqual(assessment.final_status, "无有效检测")
            with history_csv.open("r", encoding="utf-8", newline="") as handle:
                history_rows = list(csv.DictReader(handle))
            with batch_csv.open("r", encoding="utf-8", newline="") as handle:
                batch_rows = list(csv.DictReader(handle))

        self.assertEqual(len(history_rows), 1)
        self.assertEqual(history_rows[0]["mango_id"], "1")
        self.assertEqual(batch_rows[0]["total_count"], "1")
        self.assertEqual(batch_rows[0]["last_mango_id"], "1")


class RKNNPoolTests(unittest.TestCase):
    def test_each_rknn_context_is_used_serially(self):
        class FakeRKNN:
            def __init__(self, index):
                self.index = index

            def release(self):
                pass

        active = {0: 0, 1: 0, 2: 0}
        overlaps = []
        lock = threading.Lock()

        def infer(handle, frame):
            with lock:
                active[handle.index] += 1
                if active[handle.index] > 1:
                    overlaps.append((handle.index, frame))
            time.sleep(0.05 if frame == 0 else 0.005)
            with lock:
                active[handle.index] -= 1
            return frame

        factory = lambda _path, index=-1: FakeRKNN(index)
        with mock.patch.object(rknn_pool, "init_rknn", side_effect=factory):
            pool = rknn_pool.RKNNPoolExecutor("fake.rknn", 3, infer)
            try:
                for frame in range(6):
                    pool.put(frame)
                results = [pool.get()[0] for _ in range(6)]
            finally:
                pool.release()

        self.assertEqual(results, list(range(6)))
        self.assertEqual(overlaps, [])


class AutoSorterTests(unittest.TestCase):
    def test_sort_deadline_is_calculated_when_enqueued(self):
        sorter = AutoSorter.__new__(AutoSorter)
        sorter.enabled = True
        sorter.delay_s = 0.8
        sorter.sorted_ids = set()
        sorter._queue = queue.Queue()
        sorter.channel_positions = {"sales": "2"}
        sorter.grade_positions = {}
        sorter.default_position = "2"

        assessment = type(
            "Assessment",
            (),
            {
                "mango_id": "mango-1",
                "suggested_channel": "sales",
                "quality_grade": "A",
                "final_status": "ok",
            },
        )()

        with mock.patch("auto_sorter.time.monotonic", return_value=10.0):
            self.assertTrue(sorter.sort_once(assessment))

        execute_at, position, _row = sorter._queue.get_nowait()
        self.assertAlmostEqual(execute_at, 10.8)
        self.assertEqual(position, "2")

    def test_non_center_move_holds_pwm_until_reset(self):
        sorter = AutoSorter.__new__(AutoSorter)
        sorter.delay_s = 0.8
        sorter.sorter_script = Path("sorter.py")
        sorter.config_path = Path("servo.yaml")
        sorter.log_csv = Path("/tmp/auto-sorter-test.csv")
        sorter.reset_to_center = True
        sorter.reset_delay_s = 0.45

        result = type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        row = {"mango_id": "mango-1"}
        with mock.patch("auto_sorter.subprocess.run", return_value=result) as run:
            with mock.patch("auto_sorter._append_event"):
                with mock.patch("auto_sorter.time.monotonic", return_value=10.0):
                    with mock.patch("auto_sorter.time.sleep"):
                        sorter._execute_sort("1", row, execute_at=10.0)

        first_command = run.call_args_list[0].args[0]
        self.assertIn("--hold-after-move", first_command)
        self.assertEqual(run.call_args_list[1].args[0][2], "2")

    def test_move_does_not_return_to_center_when_reset_is_disabled(self):
        sorter = AutoSorter.__new__(AutoSorter)
        sorter.delay_s = 0.8
        sorter.sorter_script = Path("sorter.py")
        sorter.config_path = Path("servo.yaml")
        sorter.log_csv = Path("/tmp/auto-sorter-test.csv")
        sorter.reset_to_center = False
        sorter.reset_delay_s = 0.45

        command_result = type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        row = {"mango_id": "mango-1"}
        with mock.patch("auto_sorter.subprocess.run", return_value=command_result) as run:
            with mock.patch("auto_sorter._append_event"):
                with mock.patch("auto_sorter.time.monotonic", return_value=10.0):
                    sorter._execute_sort("1", row, execute_at=10.0)

        run.assert_called_once()
        self.assertNotIn("--hold-after-move", run.call_args.args[0])
        self.assertEqual(row["result"], "ok")

    def test_reset_failure_is_logged_without_escaping_worker(self):
        sorter = AutoSorter.__new__(AutoSorter)
        sorter.delay_s = 0.8
        sorter.sorter_script = Path("sorter.py")
        sorter.config_path = Path("servo.yaml")
        sorter.log_csv = Path("/tmp/auto-sorter-test.csv")
        sorter.reset_to_center = True
        sorter.reset_delay_s = 0.45

        move_result = type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        row = {"mango_id": "mango-1"}
        with mock.patch(
            "auto_sorter.subprocess.run",
            side_effect=[move_result, RuntimeError("reset timeout")],
        ):
            with mock.patch("auto_sorter._append_event") as append_event:
                with mock.patch("auto_sorter.time.monotonic", return_value=10.0):
                    with mock.patch("auto_sorter.time.sleep"):
                        result = sorter._execute_sort("1", row, execute_at=10.0)

        self.assertFalse(result)
        self.assertEqual(row["result"], "reset_failed")
        append_event.assert_called_once()


class CloudMappingTests(unittest.TestCase):
    def test_yolo_probability_uses_percent_dp_scale(self):
        self.assertEqual(tuya_proxy.scaled_number(0.938, 3), 938)

    def test_fusion_sugar_labels_map_to_cloud_enums(self):
        mapping = {
            "\u65e0\u6cd5": "unable",
            "\u4e0d\u53ef\u9760": "unable",
            "\u504f\u4f4e": "low",
            "\u4f4e": "low",
            "\u4e2d\u7b49": "normal",
            "\u6b63\u5e38": "normal",
            "\u9002\u4e2d": "normal",
            "\u504f\u9ad8": "high",
            "\u8f83\u9ad8": "high",
            "\u9ad8": "high",
        }
        self.assertEqual(tuya_proxy.enum_code("\u4e2d\u7b49", mapping, "unknown"), "normal")
        self.assertEqual(
            tuya_proxy.enum_code(
                "\u8fc7\u719f\u5f02\u5e38\uff0c\u7cd6\u5ea6\u53c2\u8003\u4e0d\u53ef\u9760",
                mapping,
                "unknown",
            ),
            "unable",
        )

    def test_detect_command_gets_a_unique_request_id(self):
        with mock.patch.object(tuya_proxy.time, "time_ns", return_value=123456):
            state = tuya_proxy.apply_control_commands(
                dict(tuya_proxy.DEFAULT_CONTROL_STATUS),
                [{"code": "detect_cmd", "value": "stop"}],
            )

        self.assertEqual(state["detect_cmd"], "stop")
        self.assertEqual(state["detect_request_id"], "123456")

    def test_control_state_persists_detect_request_and_auto_sort(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "control.json"
            with mock.patch.object(tuya_proxy, "CONTROL_STATE_JSON", state_path):
                state = dict(tuya_proxy.DEFAULT_CONTROL_STATUS)
                state.update(
                    {
                        "detect_cmd": "start",
                        "detect_request_id": "request-1",
                        "auto_sort_enable": False,
                    }
                )
                tuya_proxy.write_control_state(state)
                loaded = tuya_proxy.read_control_state()

        self.assertEqual(loaded["detect_cmd"], "start")
        self.assertEqual(loaded["detect_request_id"], "request-1")
        self.assertFalse(loaded["auto_sort_enable"])


if __name__ == "__main__":
    unittest.main()

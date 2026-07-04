import argparse
import csv
import json
import os
import signal
from pathlib import Path
import struct
import sys
import time

import cv2
import yaml

from rknn_pool import RKNNPoolExecutor
from yolo11_rknn import YOLO11RKNNDetector, load_labels


DEFAULT_CONFIG = "/home/elf/projects/config/yolo11.yaml"
DEFAULT_COLOR_CSV = "/home/elf/projects/datas/csv/vision_color_realtime.csv"
DEFAULT_OBJECT_CSV = "/home/elf/projects/datas/csv/mango_object_realtime.csv"
DEFAULT_OBJECT_JSON = "/home/elf/projects/datas/csv/mango_object_realtime.json"


DEFAULTS = {
    "model": "/home/elf/projects/deeplearning/mango_yolo11_rk3588_i8.rknn",
    "labels": "/home/elf/projects/deeplearning/yolo11_demo/labels.txt",
    "camera": "/dev/video21",
    "img_size": 640,
    "conf": 0.25,
    "iou": 0.45,
    "workers": 3,
    "input_format": "nhwc",
    "objectness": False,
    "sigmoid": False,
    "max_det": 100,
    "pre_nms_topk": 1000,
    "width": 0,
    "height": 0,
    "fps": 0,
    "display_width": 0,
    "display_height": 0,
    "no_display": False,
    "display": "",
    "xauthority": "",
    "window": "yolo11_rknn_camera",
    "jpeg_quality": 82,
}

RUNNING = True


def handle_signal(_signum, _frame):
    global RUNNING
    RUNNING = False


def parse_camera(value):
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def load_config(path):
    config = DEFAULTS.copy()
    if path and Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        config.update(data.get("yolo11", {}))
    return config


def parse_args():
    base = argparse.ArgumentParser(add_help=False)
    base.add_argument("--config", default=DEFAULT_CONFIG, help="Path to YOLO11 YAML config")
    config_args, _ = base.parse_known_args()
    config = load_config(config_args.config)

    parser = argparse.ArgumentParser(
        description="Run YOLO11 RKNN real-time detection on a camera.",
        parents=[base],
    )
    parser.add_argument("--model", default=config["model"], help="Path to .rknn model")
    parser.add_argument(
        "--camera",
        default=config["camera"],
        help="Camera index or device path, e.g. 0 or /dev/video21",
    )
    parser.add_argument("--labels", default=config["labels"], help="Optional class labels txt file")
    parser.add_argument("--img-size", type=int, default=config["img_size"], help="Model input size")
    parser.add_argument("--conf", type=float, default=config["conf"], help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=config["iou"], help="NMS IoU threshold")
    parser.add_argument("--workers", type=int, default=config["workers"], help="RKNN worker count")
    parser.add_argument("--max-det", type=int, default=config["max_det"], help="Maximum detections kept after NMS")
    parser.add_argument(
        "--pre-nms-topk",
        type=int,
        default=config["pre_nms_topk"],
        help="Maximum high-confidence boxes kept before NMS, 0 disables the cap",
    )
    parser.add_argument(
        "--input-format",
        choices=("nhwc", "nchw"),
        default=config["input_format"],
        help="Input tensor layout sent to RKNNLite",
    )
    parser.add_argument(
        "--objectness",
        action="store_true",
        default=config["objectness"],
        help="Use if model output is xywh + objectness + class scores",
    )
    parser.add_argument(
        "--sigmoid",
        action="store_true",
        default=config["sigmoid"],
        help="Apply sigmoid to class/objectness outputs before thresholding",
    )
    parser.add_argument("--width", type=int, default=config["width"], help="Optional camera width")
    parser.add_argument("--height", type=int, default=config["height"], help="Optional camera height")
    parser.add_argument("--fps", type=int, default=config["fps"], help="Optional camera FPS")
    parser.add_argument("--display-width", type=int, default=config["display_width"], help="Optional display width")
    parser.add_argument("--display-height", type=int, default=config["display_height"], help="Optional display height")
    parser.add_argument("--no-display", action="store_true", default=config["no_display"], help="Do not show OpenCV window")
    parser.add_argument(
        "--display",
        default=config["display"],
        help="Optional X11 DISPLAY value used when DISPLAY is not already set",
    )
    parser.add_argument(
        "--xauthority",
        default=config["xauthority"],
        help="Optional XAUTHORITY path used when XAUTHORITY is not already set",
    )
    parser.add_argument("--window", default=config["window"], help="OpenCV window name")
    parser.add_argument(
        "--qt-stream",
        action="store_true",
        help="Write annotated frames to stdout as length-prefixed JPEG for Qt embedding",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=config["jpeg_quality"],
        help="JPEG quality used by --qt-stream",
    )
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=0,
        help="Exit when this parent process is gone",
    )
    parser.add_argument(
        "--color-csv",
        default=DEFAULT_COLOR_CSV,
        help="CSV path for latest RGB/HSV detection features",
    )
    parser.add_argument(
        "--color-log-interval",
        type=int,
        default=5,
        help="Write color features every N frames, 0 disables CSV output",
    )
    parser.add_argument(
        "--object-csv",
        default=DEFAULT_OBJECT_CSV,
        help="CSV path for latest completed mango object result",
    )
    parser.add_argument(
        "--object-json",
        default=DEFAULT_OBJECT_JSON,
        help="JSON path for latest completed mango object result",
    )
    parser.add_argument("--enter-line-ratio", type=float, default=0.20, help="Top-to-bottom tracking enter line")
    parser.add_argument("--count-line-ratio", type=float, default=0.75, help="Top-to-bottom counting line")
    parser.add_argument("--show-count-lines", action="store_true", help="Draw debug enter/count lines on the video")
    parser.add_argument("--track-min-frames", type=int, default=4, help="Min stable frames before counting a mango")
    parser.add_argument("--track-max-missed", type=int, default=6, help="Frames to keep a temporarily lost mango ID")
    return parser.parse_args()


def parent_is_alive(parent_pid):
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


def open_camera(args):
    cap = cv2.VideoCapture(parse_camera(args.camera))
    if args.width > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    if args.height > 0:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if args.fps > 0:
        cap.set(cv2.CAP_PROP_FPS, args.fps)
    if not cap.isOpened():
        raise RuntimeError("open camera failed: {}".format(args.camera))
    return cap


def maybe_resize_for_display(frame, width, height):
    if width <= 0 and height <= 0:
        return frame
    h, w = frame.shape[:2]
    if width <= 0:
        width = int(w * height / h)
    if height <= 0:
        height = int(h * width / w)
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)


def configure_display_environment(args):
    if args.no_display:
        return
    if args.display and not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = args.display
    if args.xauthority and not os.environ.get("XAUTHORITY"):
        os.environ["XAUTHORITY"] = args.xauthority


def setup_qt_frame_output():
    frame_fd = os.dup(sys.stdout.fileno())
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    return os.fdopen(frame_fd, "wb", buffering=0)


def write_qt_frame(output, frame, jpeg_quality):
    quality = max(30, min(95, int(jpeg_quality)))
    ok, payload = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return False

    data = payload.tobytes()
    output.write(struct.pack(">I", len(data)))
    output.write(data)
    return True


COLOR_CSV_FIELDS = [
    "timestamp",
    "frame_index",
    "detection_id",
    "label",
    "confidence",
    "x1",
    "y1",
    "x2",
    "y2",
    "area_px",
    "rgb_r_mean",
    "rgb_g_mean",
    "rgb_b_mean",
    "hsv_h_mean_deg",
    "hsv_s_mean_pct",
    "hsv_v_mean_pct",
    "green_ratio",
    "yellow_orange_ratio",
    "dark_spot_ratio",
    "brown_area_ratio",
]

OBJECT_CSV_FIELDS = [
    "timestamp",
    "frame_index",
    "mango_id",
    "track_id",
    "label",
    "confidence",
    "x1",
    "y1",
    "x2",
    "y2",
    "center_x",
    "center_y",
    "area_px",
    "stable_frames",
    "first_frame",
    "last_frame",
    "consistency_score",
    "consistency_label",
    "rgb_r_mean",
    "rgb_g_mean",
    "rgb_b_mean",
    "hsv_h_mean_deg",
    "hsv_s_mean_pct",
    "hsv_v_mean_pct",
    "green_ratio",
    "yellow_orange_ratio",
    "dark_spot_ratio",
    "brown_area_ratio",
]


def write_color_features(csv_path, frame_index, features):
    if not csv_path:
        return

    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLOR_CSV_FIELDS)
        writer.writeheader()
        for feature in features:
            row = {
                "timestamp": timestamp,
                "frame_index": frame_index,
                **feature,
            }
            for key in (
                "confidence",
                "rgb_r_mean",
                "rgb_g_mean",
                "rgb_b_mean",
                "hsv_h_mean_deg",
                "hsv_s_mean_pct",
                "hsv_v_mean_pct",
                "green_ratio",
                "yellow_orange_ratio",
                "dark_spot_ratio",
                "brown_area_ratio",
            ):
                row[key] = "{:.4f}".format(float(row[key]))
            writer.writerow(row)

    os.replace(str(temp_path), str(path))


def _box_center(feature):
    return (
        (float(feature["x1"]) + float(feature["x2"])) * 0.5,
        (float(feature["y1"]) + float(feature["y2"])) * 0.5,
    )


def _box_area(feature):
    return max(1.0, float(feature.get("area_px", 1.0)))


def _iou(a, b):
    ax1, ay1, ax2, ay2 = float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"])
    bx1, by1, bx2, by2 = float(b["x1"]), float(b["y1"]), float(b["x2"]), float(b["y2"])
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
    return inter / max(1.0, area_a + area_b - inter)


def _mean_feature(samples, key, default=0.0):
    values = []
    for sample in samples:
        try:
            values.append(float(sample.get(key, default)))
        except (TypeError, ValueError):
            pass
    if not values:
        return default
    return sum(values) / len(values)


def _vote_label(samples):
    votes = {}
    for sample in samples:
        label = str(sample.get("label", "")).strip()
        if not label:
            continue
        try:
            weight = max(0.01, float(sample.get("confidence", 0.0)))
        except (TypeError, ValueError):
            weight = 0.01
        votes[label] = votes.get(label, 0.0) + weight
    if not votes:
        return "", 0.0
    label, score = max(votes.items(), key=lambda item: item[1])
    total = sum(votes.values())
    return label, score / max(total, 1e-6)


def _consistency_label(score):
    if score >= 0.80:
        return "高"
    if score >= 0.60:
        return "中"
    return "低"


class MangoTrack:
    def __init__(self, track_id, feature, frame_index):
        self.track_id = track_id
        self.first_frame = frame_index
        self.last_frame = frame_index
        self.last_feature = dict(feature)
        self.prev_center_y = _box_center(feature)[1]
        self.center_y = self.prev_center_y
        self.missed = 0
        self.counted = False
        self.samples = []
        self.add_sample(feature, frame_index)

    def add_sample(self, feature, frame_index):
        self.prev_center_y = self.center_y
        self.center_y = _box_center(feature)[1]
        self.last_frame = frame_index
        self.last_feature = dict(feature)
        self.missed = 0
        self.samples.append(dict(feature))
        if len(self.samples) > 40:
            self.samples = self.samples[-40:]

    def summary(self, frame_index):
        label, consistency = _vote_label(self.samples)
        latest = self.last_feature
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "timestamp": timestamp,
            "frame_index": frame_index,
            "mango_id": self.track_id,
            "track_id": self.track_id,
            "label": label or latest.get("label", ""),
            "confidence": _mean_feature(self.samples, "confidence"),
            "x1": int(float(latest["x1"])),
            "y1": int(float(latest["y1"])),
            "x2": int(float(latest["x2"])),
            "y2": int(float(latest["y2"])),
            "center_x": int(_box_center(latest)[0]),
            "center_y": int(_box_center(latest)[1]),
            "area_px": int(_mean_feature(self.samples, "area_px", _box_area(latest))),
            "stable_frames": len(self.samples),
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "consistency_score": consistency,
            "consistency_label": _consistency_label(consistency),
            "rgb_r_mean": _mean_feature(self.samples, "rgb_r_mean"),
            "rgb_g_mean": _mean_feature(self.samples, "rgb_g_mean"),
            "rgb_b_mean": _mean_feature(self.samples, "rgb_b_mean"),
            "hsv_h_mean_deg": _mean_feature(self.samples, "hsv_h_mean_deg"),
            "hsv_s_mean_pct": _mean_feature(self.samples, "hsv_s_mean_pct"),
            "hsv_v_mean_pct": _mean_feature(self.samples, "hsv_v_mean_pct"),
            "green_ratio": _mean_feature(self.samples, "green_ratio"),
            "yellow_orange_ratio": _mean_feature(self.samples, "yellow_orange_ratio"),
            "dark_spot_ratio": _mean_feature(self.samples, "dark_spot_ratio"),
            "brown_area_ratio": _mean_feature(self.samples, "brown_area_ratio"),
        }


class MangoTracker:
    def __init__(self, enter_line_ratio=0.20, count_line_ratio=0.75, min_frames=4, max_missed=6):
        self.enter_line_ratio = enter_line_ratio
        self.count_line_ratio = count_line_ratio
        self.min_frames = max(1, int(min_frames))
        self.max_missed = max(1, int(max_missed))
        self.next_track_id = 1
        self.tracks = {}
        self.completed_count = 0

    def _new_track(self, feature, frame_index):
        track = MangoTrack(self.next_track_id, feature, frame_index)
        self.tracks[track.track_id] = track
        self.next_track_id += 1
        return track

    def _match_score(self, track, feature, width, height):
        cx, cy = _box_center(feature)
        tx, ty = _box_center(track.last_feature)
        dx = abs(cx - tx)
        dy = abs(cy - ty)
        max_dx = max(60.0, width * 0.18)
        max_dy = max(80.0, height * 0.22)
        if dx > max_dx or dy > max_dy:
            return None
        if cy < ty - height * 0.10:
            return None
        area_ratio = _box_area(feature) / max(_box_area(track.last_feature), 1.0)
        if area_ratio < 0.30 or area_ratio > 3.20:
            return None
        overlap = _iou(track.last_feature, feature)
        return (dx / max_dx) + (dy / max_dy) - overlap

    def update(self, features, frame_index, frame_shape):
        height, width = frame_shape[:2]
        count_line_y = height * self.count_line_ratio
        enter_line_y = height * self.enter_line_ratio

        candidates = []
        unmatched_tracks = set(self.tracks.keys())
        unmatched_features = set(range(len(features)))

        for feature_index, feature in enumerate(features):
            for track_id, track in self.tracks.items():
                if track.counted:
                    continue
                score = self._match_score(track, feature, width, height)
                if score is not None:
                    candidates.append((score, track_id, feature_index))

        for _score, track_id, feature_index in sorted(candidates, key=lambda item: item[0]):
            if track_id not in unmatched_tracks or feature_index not in unmatched_features:
                continue
            track = self.tracks[track_id]
            track.add_sample(features[feature_index], frame_index)
            unmatched_tracks.remove(track_id)
            unmatched_features.remove(feature_index)

        for feature_index in sorted(unmatched_features):
            self._new_track(features[feature_index], frame_index)

        completed = []
        for track_id in list(unmatched_tracks):
            track = self.tracks.get(track_id)
            if track is None:
                continue
            track.missed += 1

        for track_id, track in list(self.tracks.items()):
            crossed = track.prev_center_y < count_line_y <= track.center_y
            has_enough_samples = len(track.samples) >= self.min_frames
            entered = track.center_y >= enter_line_y
            if not track.counted and crossed and has_enough_samples and entered:
                track.counted = True
                self.completed_count += 1
                completed.append(track.summary(frame_index))
            if track.missed > self.max_missed or (track.counted and track.center_y > count_line_y + height * 0.10):
                self.tracks.pop(track_id, None)

        return completed

    def active_tracks(self):
        return list(self.tracks.values())


def write_object_result(csv_path, json_path, result):
    if not result:
        return

    timestamp = result.get("timestamp") or time.strftime("%Y-%m-%d %H:%M:%S")
    row = {field: result.get(field, "") for field in OBJECT_CSV_FIELDS}
    row["timestamp"] = timestamp
    for key in (
        "confidence",
        "consistency_score",
        "rgb_r_mean",
        "rgb_g_mean",
        "rgb_b_mean",
        "hsv_h_mean_deg",
        "hsv_s_mean_pct",
        "hsv_v_mean_pct",
        "green_ratio",
        "yellow_orange_ratio",
        "dark_spot_ratio",
        "brown_area_ratio",
    ):
        try:
            row[key] = "{:.4f}".format(float(row[key]))
        except (TypeError, ValueError):
            row[key] = ""

    if csv_path:
        path = Path(csv_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=OBJECT_CSV_FIELDS)
            writer.writeheader()
            writer.writerow(row)
        os.replace(str(temp_path), str(path))

    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(row, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(str(temp_path), str(path))


def draw_tracking_overlay(image, tracker, enter_line_ratio, count_line_ratio, show_count_lines=False):
    height, width = image.shape[:2]
    enter_y = int(height * enter_line_ratio)
    count_y = int(height * count_line_ratio)
    if show_count_lines:
        cv2.line(image, (0, enter_y), (width - 1, enter_y), (80, 180, 255), 2)
        cv2.line(image, (0, count_y), (width - 1, count_y), (0, 220, 120), 2)
        cv2.putText(image, "Detect zone", (12, max(24, enter_y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 180, 255), 2)
        cv2.putText(image, "Count line", (12, max(24, count_y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 120), 2)

    for track in tracker.active_tracks():
        feature = track.last_feature
        x1, y1 = int(float(feature["x1"])), int(float(feature["y1"]))
        text = "Mango #{}  {}f".format(track.track_id, len(track.samples))
        cv2.putText(
            image,
            text,
            (x1, max(18, y1 - 28)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


def main():
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    args = parse_args()
    if args.qt_stream:
        args.no_display = True

    frame_output = setup_qt_frame_output() if args.qt_stream else None
    configure_display_environment(args)
    labels = load_labels(args.labels) if args.labels else None
    detector = YOLO11RKNNDetector(
        img_size=args.img_size,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        labels=labels,
        input_format=args.input_format,
        has_objectness=args.objectness,
        apply_sigmoid=args.sigmoid,
        max_det=args.max_det,
        pre_nms_topk=args.pre_nms_topk,
    )

    cap = None
    pool = None
    frames = 0
    detect_count = 0
    start_time = time.time()
    last_report = start_time
    tracker = MangoTracker(
        enter_line_ratio=args.enter_line_ratio,
        count_line_ratio=args.count_line_ratio,
        min_frames=args.track_min_frames,
        max_missed=args.track_max_missed,
    )

    try:
        cap = open_camera(args)
        pool = RKNNPoolExecutor(args.model, args.workers, detector.infer)

        for _ in range(args.workers + 1):
            ret, frame = cap.read()
            if not ret:
                raise RuntimeError("read initial camera frame failed")
            pool.put(frame)

        while RUNNING and cap.isOpened() and parent_is_alive(args.parent_pid):
            ret, frame = cap.read()
            if not ret:
                break

            pool.put(frame)
            result, ok = pool.get()
            if not ok:
                break

            annotated, count, color_features = result
            detect_count += count
            frames += 1

            completed_objects = tracker.update(color_features, frames, annotated.shape)
            for completed in completed_objects:
                write_object_result(args.object_csv, args.object_json, completed)

            if args.color_log_interval > 0 and frames % args.color_log_interval == 0:
                write_color_features(args.color_csv, frames, color_features)

            now = time.time()
            fps = frames / max(now - start_time, 1e-6)
            draw_tracking_overlay(annotated, tracker, args.enter_line_ratio, args.count_line_ratio, args.show_count_lines)
            cv2.putText(
                annotated,
                "FPS {:.1f}  DET {}  COUNT {}".format(fps, count, tracker.completed_count),
                (12, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

            if args.qt_stream:
                if not write_qt_frame(frame_output, annotated, args.jpeg_quality):
                    break
            elif not args.no_display:
                shown = maybe_resize_for_display(
                    annotated,
                    args.display_width,
                    args.display_height,
                )
                cv2.imshow(args.window, shown)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if frames % 30 == 0:
                interval = now - last_report
                print(
                    "last 30 frames fps: {:.2f}, avg fps: {:.2f}, detections: {}".format(
                        30 / max(interval, 1e-6),
                        fps,
                        detect_count,
                    ),
                    file=sys.stderr if args.qt_stream else sys.stdout,
                    flush=True,
                )
                last_report = now
    finally:
        if cap is not None:
            cap.release()
        if pool is not None:
            pool.release()
        if not args.no_display:
            cv2.destroyAllWindows()
        if frame_output is not None:
            frame_output.close()

    elapsed = time.time() - start_time
    print(
        "total frames: {}, avg fps: {:.2f}".format(frames, frames / max(elapsed, 1e-6)),
        file=sys.stderr if args.qt_stream else sys.stdout,
        flush=True,
    )


if __name__ == "__main__":
    main()

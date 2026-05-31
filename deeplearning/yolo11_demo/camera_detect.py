import argparse
import csv
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
    )

    cap = None
    pool = None
    frames = 0
    detect_count = 0
    start_time = time.time()
    last_report = start_time

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

            if args.color_log_interval > 0 and frames % args.color_log_interval == 0:
                write_color_features(args.color_csv, frames, color_features)

            now = time.time()
            fps = frames / max(now - start_time, 1e-6)
            cv2.putText(
                annotated,
                "FPS {:.1f}  DET {}".format(fps, count),
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

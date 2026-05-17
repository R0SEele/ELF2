import argparse
from pathlib import Path
import time

import cv2
import yaml

from rknn_pool import RKNNPoolExecutor
from yolo11_rknn import YOLO11RKNNDetector, load_labels


DEFAULT_CONFIG = "/home/elf/projects/config/yolo11.yaml"


DEFAULTS = {
    "model": "/home/elf/projects/deeplearning/fruits1_yolo11_rk3588_i8.rknn",
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
    "window": "yolo11_rknn_camera",
}


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
    parser.add_argument("--window", default=config["window"], help="OpenCV window name")
    return parser.parse_args()


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


def main():
    args = parse_args()
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

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            pool.put(frame)
            result, ok = pool.get()
            if not ok:
                break

            annotated, count = result
            detect_count += count
            frames += 1

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

            if not args.no_display:
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
                    )
                )
                last_report = now
    finally:
        if cap is not None:
            cap.release()
        if pool is not None:
            pool.release()
        if not args.no_display:
            cv2.destroyAllWindows()

    elapsed = time.time() - start_time
    print("total frames: {}, avg fps: {:.2f}".format(frames, frames / max(elapsed, 1e-6)))


if __name__ == "__main__":
    main()

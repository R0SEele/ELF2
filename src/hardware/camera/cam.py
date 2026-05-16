"""PyQt5 + OpenCV camera preview for ELF2 RK3588.

Features:
- Real-time preview in a PyQt5 window.
- Uses a latest-frame-only buffer to avoid frame backlog and memory growth.
- Supports direct camera device or GStreamer pipeline.
- Graceful shutdown with camera resource release.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets


@dataclass
class CameraConfig:
	source: Union[int, str] = 0
	width: int = 1280
	height: int = 720
	fps: int = 30
	display_fps: int = 30
	render_scale: float = 1.0
	smooth_scaling: bool = False
	low_latency: bool = True
	mobaxterm_mode: bool = False
	window_title: str = "ELF2 RK3588 Camera Preview"
	backend: str = "auto"


def _project_root() -> Path:
	return Path(__file__).resolve().parents[3]


def _load_yaml_config(config_path: Path) -> CameraConfig:
	cfg = CameraConfig()
	if not config_path.exists():
		return cfg

	try:
		import yaml  # type: ignore
	except Exception:
		return cfg

	try:
		raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
	except Exception:
		return cfg

	cam = raw.get("camera", raw)
	if not isinstance(cam, dict):
		return cfg

	source = cam.get("source", cfg.source)
	if isinstance(source, str) and source.isdigit():
		source = int(source)

	return CameraConfig(
		source=source,
		width=int(cam.get("width", cfg.width)),
		height=int(cam.get("height", cfg.height)),
		fps=max(1, int(cam.get("fps", cfg.fps))),
		display_fps=max(1, int(cam.get("display_fps", cam.get("fps", cfg.display_fps)))),
		render_scale=max(0.1, float(cam.get("render_scale", cfg.render_scale))),
		smooth_scaling=bool(cam.get("smooth_scaling", cfg.smooth_scaling)),
		low_latency=bool(cam.get("low_latency", cfg.low_latency)),
		mobaxterm_mode=bool(cam.get("mobaxterm_mode", cfg.mobaxterm_mode)),
		window_title=str(cam.get("window_title", cfg.window_title)),
		backend=str(cam.get("backend", cfg.backend)).lower(),
	)


def _select_backend(backend: str, source: Union[int, str]) -> int:
	if backend == "v4l2":
		return cv2.CAP_V4L2
	if backend == "gstreamer" and isinstance(source, str):
		return cv2.CAP_GSTREAMER
	return cv2.CAP_ANY


def _video_device_candidates(preferred: Union[int, str]) -> list[Union[int, str]]:
	candidates: list[Union[int, str]] = [preferred]

	if isinstance(preferred, int):
		candidates.append(f"/dev/video{preferred}")

	for dev in sorted(glob.glob("/dev/video*")):
		suffix = dev.replace("/dev/video", "", 1)
		# Only probe real numeric video nodes like /dev/video21.
		if not suffix.isdigit():
			continue
		if dev not in candidates:
			candidates.append(dev)

	return candidates


def _try_open_source(source: Union[int, str], backend: int, read_probe_frames: int = 5):
	cap = cv2.VideoCapture(source, backend)
	if not cap.isOpened():
		cap.release()
		return None

	for _ in range(read_probe_frames):
		ok, frame = cap.read()
		if ok and frame is not None:
			return cap

	cap.release()
	return None


class CameraCaptureWorker(threading.Thread):
	def __init__(self, cfg: CameraConfig):
		super().__init__(daemon=True)
		self._cfg = cfg
		self._stop_evt = threading.Event()
		self._lock = threading.Lock()
		self._latest_frame = None
		self._cap: Optional[cv2.VideoCapture] = None
		self.opened = False
		self.open_error = ""

	def run(self) -> None:
		backend = _select_backend(self._cfg.backend, self._cfg.source)
		tried: list[str] = []

		for candidate in _video_device_candidates(self._cfg.source):
			tried.append(str(candidate))
			cap = _try_open_source(candidate, backend)
			if cap is not None:
				self._cap = cap
				self._cfg.source = candidate
				break

		if self._cap is None:
			self.open_error = (
				f"Cannot open camera source: {self._cfg.source}\n"
				f"Tried: {', '.join(tried)}"
			)
			return

		self.opened = True

		self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._cfg.width)
		self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._cfg.height)
		self._cap.set(cv2.CAP_PROP_FPS, self._cfg.fps)
		# Keep capture buffer minimal to reduce latency and avoid frame accumulation.
		self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

		while not self._stop_evt.is_set():
			ok, frame = self._cap.read()
			if not ok:
				time.sleep(0.01)
				continue

			# Latest-frame-only buffer: replaces previous frame instead of queueing.
			with self._lock:
				self._latest_frame = frame

		self._release()

	def read_latest(self):
		with self._lock:
			if self._latest_frame is None:
				return None
			# Writer replaces ndarray object each frame, so returning reference is safe.
			return self._latest_frame

	def stop(self) -> None:
		self._stop_evt.set()
		self.join(timeout=1.5)
		self._release()

	def _release(self) -> None:
		if self._cap is not None:
			self._cap.release()
			self._cap = None


class CameraWindow(QtWidgets.QMainWindow):
	def __init__(self, cfg: CameraConfig):
		super().__init__()
		self.cfg = cfg
		self.setWindowTitle(cfg.window_title)
		self.resize(cfg.width, cfg.height)

		self.label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
		self.label.setStyleSheet("background-color: black;")
		self.label.setMinimumSize(640, 360)
		self.setCentralWidget(self.label)

		self.worker = CameraCaptureWorker(cfg)
		self.worker.start()

		self.timer = QtCore.QTimer(self)
		self.timer.timeout.connect(self._update_frame)
		self.timer.start(max(1, int(1000 / cfg.display_fps)))

	def _update_frame(self) -> None:
		if not self.worker.opened and self.worker.open_error:
			self.timer.stop()
			QtWidgets.QMessageBox.critical(self, "Camera Error", self.worker.open_error)
			self.close()
			return

		frame = self.worker.read_latest()
		if frame is None:
			return

		if self.cfg.render_scale != 1.0:
			new_w = max(1, int(frame.shape[1] * self.cfg.render_scale))
			new_h = max(1, int(frame.shape[0] * self.cfg.render_scale))
			frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

		rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		h, w, c = rgb.shape
		bytes_per_line = c * w
		image = QtGui.QImage(
			rgb.data,
			w,
			h,
			bytes_per_line,
			QtGui.QImage.Format_RGB888,
		)
		pixmap = QtGui.QPixmap.fromImage(image)
		self.label.setPixmap(
			pixmap.scaled(
				self.label.size(),
				QtCore.Qt.KeepAspectRatio,
				QtCore.Qt.SmoothTransformation if self.cfg.smooth_scaling else QtCore.Qt.FastTransformation,
			)
		)

	def closeEvent(self, event: QtGui.QCloseEvent) -> None:
		self.timer.stop()
		self.worker.stop()
		super().closeEvent(event)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="ELF2 RK3588 PyQt5 camera preview")
	parser.add_argument(
		"--config",
		default=str(_project_root() / "config" / "camera.yaml"),
		help="Path to camera yaml config",
	)
	parser.add_argument("--source", help="Override source from config: index, /dev/video21, or pipeline")
	parser.add_argument("--width", type=int, help="Override capture width")
	parser.add_argument("--height", type=int, help="Override capture height")
	parser.add_argument("--fps", type=int, help="Override preview fps")
	parser.add_argument("--display-fps", type=int, help="Override GUI refresh fps")
	parser.add_argument("--render-scale", type=float, help="Resize frame before display, e.g. 0.5")
	parser.add_argument(
		"--backend",
		choices=["auto", "v4l2", "gstreamer"],
		help="Override backend",
	)
	parser.add_argument("--low-latency", action="store_true", help="Enable low-latency tuning")
	parser.add_argument("--mobaxterm", action="store_true", help="Enable MobaXterm/X11 compatibility tuning")
	parser.add_argument(
		"--qt-platform",
		default="auto",
		help="Qt platform: auto/xcb/wayland/offscreen/linuxfb/eglfs/minimal",
	)
	return parser.parse_args()


def _configure_qt_platform(requested: str) -> Optional[str]:
	requested = (requested or "auto").strip().lower()
	if requested != "auto":
		os.environ["QT_QPA_PLATFORM"] = requested
		return None

	# Respect explicit environment if already provided by user/system.
	if os.environ.get("QT_QPA_PLATFORM"):
		return None

	if os.environ.get("WAYLAND_DISPLAY"):
		os.environ["QT_QPA_PLATFORM"] = "wayland"
		return None

	if os.environ.get("DISPLAY"):
		os.environ["QT_QPA_PLATFORM"] = "xcb"
		return None

	return (
		"No GUI display detected. Start from Ubuntu desktop terminal or set DISPLAY/WAYLAND.\n"
		"Current env: DISPLAY and WAYLAND_DISPLAY are empty (TTY session).\n"
		"Try: export DISPLAY=:0\n"
		"If using SSH, use X11 forwarding or run from local desktop session."
	)


def _is_remote_x11_session() -> bool:
	display = os.environ.get("DISPLAY", "")
	return display.startswith("localhost:") or display.startswith("127.0.0.1:")


def _apply_runtime_tuning(cfg: CameraConfig, force_mobaxterm: bool) -> None:
	remote_x11 = force_mobaxterm or cfg.mobaxterm_mode or _is_remote_x11_session()

	if cfg.low_latency:
		cfg.smooth_scaling = False
		cfg.display_fps = min(cfg.display_fps, cfg.fps)

	if remote_x11:
		# Remote X11 usually has higher transport overhead; lower render load to cut delay.
		cfg.display_fps = min(cfg.display_fps, 20)
		cfg.render_scale = min(cfg.render_scale, 0.5)
		cfg.width = min(cfg.width, 960)
		cfg.height = min(cfg.height, 540)
		cfg.fps = min(cfg.fps, 20)
		cfg.smooth_scaling = False
		os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
		os.environ.setdefault("QT_X11_NO_MITSHM", "1")


def main() -> int:
	args = parse_args()
	cfg = _load_yaml_config(Path(args.config))

	if args.source is not None:
		src = args.source
		cfg.source = int(src) if src.isdigit() else src
	if args.width is not None:
		cfg.width = args.width
	if args.height is not None:
		cfg.height = args.height
	if args.fps is not None:
		cfg.fps = max(1, args.fps)
	if args.display_fps is not None:
		cfg.display_fps = max(1, args.display_fps)
	if args.render_scale is not None:
		cfg.render_scale = max(0.1, args.render_scale)
	if args.backend is not None:
		cfg.backend = args.backend
	if args.low_latency:
		cfg.low_latency = True
	if args.mobaxterm:
		cfg.mobaxterm_mode = True

	_apply_runtime_tuning(cfg, force_mobaxterm=args.mobaxterm)

	qt_err = _configure_qt_platform(args.qt_platform)
	if qt_err:
		print(qt_err, file=sys.stderr)
		return 2

	app = QtWidgets.QApplication(sys.argv)
	window = CameraWindow(cfg)
	window.show()
	return app.exec_()


if __name__ == "__main__":
	raise SystemExit(main())

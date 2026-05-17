# YOLO11 RKNN Camera Demo for RK3588

This demo runs `/home/elf/projects/deeplearning/fruits1_yolo11_rk3588_i8.rknn` with RKNNLite on RK3588 and shows real-time camera detections.

## Run

```bash
cd /home/elf/projects/deeplearning/yolo11_demo
python3 camera_detect.py --camera /dev/video21
```

Press `q` to quit.

Common options:

```bash
python3 camera_detect.py --camera /dev/video0 --workers 3 --conf 0.25 --iou 0.45
python3 camera_detect.py --camera /dev/video21 --width 1280 --height 720 --fps 30
python3 camera_detect.py --labels labels.txt
```

`fruits1_yolo11_rk3588_i8.rknn` uses 9 output tensors: three detection scales, each with box, class, and score-sum outputs. The model has 29 classes, and the default `labels.txt` is stored in this demo directory.

If `init_runtime` fails with `failed to open rknpu module`, run on the RK3588 board with the Rockchip NPU driver loaded and a compatible `librknnrt.so`.

`fruits1_yolo11_rk3588_i8.rknn` uses the Rockchip optimized split-head format: three detection scales with box, class, and score-sum outputs. This is the high-performance INT8 layout used by the Rockchip YOLO demos.

# YOLO11 RKNN Camera Demo for RK3588

This demo runs `/home/elf/projects/deeplearning/mango_yolo11_rk3588_i8.rknn` with RKNNLite on RK3588 and shows real-time camera detections.

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

`mango_yolo11_rk3588_i8.rknn` uses one YOLO output tensor shaped `[1, 7, 8400]`: four bbox channels plus three class channels. The default `labels.txt` is stored in this demo directory.

If `init_runtime` fails with `failed to open rknpu module`, run on the RK3588 board with the Rockchip NPU driver loaded and a compatible `librknnrt.so`.

The mango model classes are `mango_unripe`, `mango_ripe`, and `mango_overripe`, matching the mango quality fusion module.

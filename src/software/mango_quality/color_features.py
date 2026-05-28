import cv2
import numpy as np


def extract_mango_color_features_from_bgr_roi(roi_bgr):
    if roi_bgr is None or roi_bgr.size == 0:
        return {}

    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    b_mean, g_mean, r_mean = roi_bgr.reshape(-1, 3).mean(axis=0)
    h_mean, s_mean, v_mean = hsv.reshape(-1, 3).mean(axis=0)

    hue_deg = hsv[:, :, 0].astype(np.float32) * 2.0
    sat_pct = hsv[:, :, 1].astype(np.float32) * 100.0 / 255.0
    val_pct = hsv[:, :, 2].astype(np.float32) * 100.0 / 255.0
    r = roi_bgr[:, :, 2].astype(np.float32)
    g = roi_bgr[:, :, 1].astype(np.float32)
    b = roi_bgr[:, :, 0].astype(np.float32)

    valid = (sat_pct > 12.0) & (val_pct > 10.0)
    total = max(1, int(valid.sum()))

    green = valid & (hue_deg >= 35.0) & (hue_deg <= 95.0) & (sat_pct >= 20.0)
    yellow_orange = valid & (hue_deg >= 8.0) & (hue_deg <= 38.0) & (sat_pct >= 25.0)
    dark = (val_pct < 28.0) | ((r < 65.0) & (g < 65.0) & (b < 65.0))
    brown = (
        (hue_deg >= 8.0)
        & (hue_deg <= 42.0)
        & (sat_pct >= 18.0)
        & (val_pct <= 55.0)
        & (r >= g * 0.85)
        & (g >= b * 0.85)
    )

    return {
        "rgb_r_mean": float(r_mean),
        "rgb_g_mean": float(g_mean),
        "rgb_b_mean": float(b_mean),
        "hsv_h_mean_deg": float(h_mean) * 2.0,
        "hsv_s_mean_pct": float(s_mean) * 100.0 / 255.0,
        "hsv_v_mean_pct": float(v_mean) * 100.0 / 255.0,
        "green_ratio": float(green.sum()) / total,
        "yellow_orange_ratio": float(yellow_orange.sum()) / total,
        "dark_spot_ratio": float(dark.sum()) / max(1, roi_bgr.shape[0] * roi_bgr.shape[1]),
        "brown_area_ratio": float(brown.sum()) / total,
    }

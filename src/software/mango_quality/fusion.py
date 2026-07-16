import csv
import json
import math
import os
import time
from datetime import datetime
from dataclasses import asdict, dataclass, field
from pathlib import Path


PROJECT_ROOT = Path("/home/elf/projects")
DEFAULT_VISION_CSV = PROJECT_ROOT / "datas" / "csv" / "vision_color_realtime.csv"
DEFAULT_OBJECT_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_object_realtime.csv"
DEFAULT_SPECTRUM_CSV = PROJECT_ROOT / "datas" / "spectrum_quality_samples.csv"
ALT_SPECTRUM_CSV = PROJECT_ROOT / "datas" / "csv" / "spectrum_realtime.csv"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_quality_realtime.csv"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "datas" / "csv" / "mango_quality_realtime.json"
DEFAULT_BATCH_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_batch_summary.csv"
DEFAULT_BATCH_JSON = PROJECT_ROOT / "datas" / "csv" / "mango_batch_summary.json"
DEFAULT_BATCH_STATE_JSON = PROJECT_ROOT / "datas" / "csv" / "mango_batch_state.json"
DEFAULT_HISTORY_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_quality_history.csv"
OBJECT_STALE_SECONDS = 20.0
VISION_STALE_SECONDS = 5.0
SPECTRUM_STALE_SECONDS = 30.0


MANGO_LABELS = {
    "mango_unripe": ("unripe", 20.0, "未熟"),
    "mango_ripe": ("ripe", 65.0, "成熟"),
    "mango_overripe": ("overripe", 88.0, "过熟"),
    "unripe": ("unripe", 20.0, "未熟"),
    "ripe": ("ripe", 65.0, "成熟"),
    "overripe": ("overripe", 88.0, "过熟"),
    "芒果-未熟": ("unripe", 20.0, "未熟"),
    "芒果-成熟": ("ripe", 65.0, "成熟"),
    "芒果-过熟": ("overripe", 88.0, "过熟"),
    "未熟": ("unripe", 20.0, "未熟"),
    "成熟": ("ripe", 65.0, "成熟"),
    "过熟": ("overripe", 88.0, "过熟"),
}


QUALITY_FIELDS = [
    "timestamp",
    "mango_id",
    "stable_frames",
    "consistency_label",
    "consistency_score",
    "quality_grade",
    "suggested_channel",
    "vision_timestamp",
    "spectrum_timestamp",
    "data_status",
    "yolo_label",
    "yolo_confidence",
    "maturity_label",
    "maturity_score",
    "maturity_confidence",
    "sugar_label",
    "sugar_score",
    "reference_brix_range",
    "rot_status",
    "rot_score",
    "final_status",
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
    "red_green_ratio",
    "yellow_green_ratio",
    "nir_ratio",
    "spectral_centroid_nm",
    "reason",
]

BATCH_FIELDS = [
    "timestamp",
    "batch_id",
    "total_count",
    "unripe_count",
    "ripe_count",
    "overripe_count",
    "grade_a_count",
    "grade_b_count",
    "grade_c_count",
    "reject_count",
    "saleable_count",
    "saleable_ratio",
    "rot_risk_count",
    "rot_risk_ratio",
    "channel_sales_count",
    "channel_ripen_count",
    "channel_process_count",
    "channel_recheck_count",
    "channel_reject_count",
    "last_mango_id",
    "last_quality_grade",
    "last_suggested_channel",
    "last_maturity_label",
    "last_final_status",
    "last_timestamp",
]

HISTORY_FIELDS = [
    "timestamp",
    "mango_id",
    "quality_grade",
    "suggested_channel",
    "maturity_label",
    "reference_brix_range",
    "rot_status",
    "final_status",
    "consistency_label",
    "stable_frames",
    "yolo_label",
    "yolo_confidence",
    "reason",
]


@dataclass
class VisionFeatures:
    timestamp: str = ""
    mango_id: str = ""
    stable_frames: int = 0
    consistency_label: str = ""
    consistency_score: float = 0.0
    label: str = ""
    label_key: str = ""
    confidence: float = 0.0
    area_px: float = 0.0
    rgb_r_mean: float = math.nan
    rgb_g_mean: float = math.nan
    rgb_b_mean: float = math.nan
    hsv_h_mean_deg: float = math.nan
    hsv_s_mean_pct: float = math.nan
    hsv_v_mean_pct: float = math.nan
    green_ratio: float = math.nan
    yellow_orange_ratio: float = math.nan
    dark_spot_ratio: float = math.nan
    brown_area_ratio: float = math.nan
    raw: dict = field(default_factory=dict)


@dataclass
class SpectrumFeatures:
    timestamp: str = ""
    f1_415: float = math.nan
    f2_445: float = math.nan
    f3_480: float = math.nan
    f4_515: float = math.nan
    f5_555: float = math.nan
    f6_590: float = math.nan
    f7_630: float = math.nan
    f8_680: float = math.nan
    clear: float = math.nan
    nir: float = math.nan
    nir_ratio: float = math.nan
    dominant_wavelength_nm: float = math.nan
    spectral_centroid_nm: float = math.nan
    red_sum: float = math.nan
    green_sum: float = math.nan
    blue_sum: float = math.nan
    red_green_ratio: float = math.nan
    yellow_green_ratio: float = math.nan
    raw: dict = field(default_factory=dict)


@dataclass
class QualityAssessment:
    timestamp: str
    mango_id: str = ""
    stable_frames: int = 0
    consistency_label: str = ""
    consistency_score: float = 0.0
    quality_grade: str = "--"
    suggested_channel: str = "--"
    vision_timestamp: str = ""
    spectrum_timestamp: str = ""
    data_status: str = ""
    yolo_label: str = ""
    yolo_confidence: float = 0.0
    maturity_label: str = "未检测到芒果"
    maturity_score: float = 0.0
    maturity_confidence: float = 0.0
    sugar_label: str = "无法评估"
    sugar_score: float = 0.0
    reference_brix_range: str = ""
    rot_status: str = "无法评估"
    rot_score: float = 0.0
    final_status: str = "无有效检测"
    rgb_r_mean: float = math.nan
    rgb_g_mean: float = math.nan
    rgb_b_mean: float = math.nan
    hsv_h_mean_deg: float = math.nan
    hsv_s_mean_pct: float = math.nan
    hsv_v_mean_pct: float = math.nan
    green_ratio: float = math.nan
    yellow_orange_ratio: float = math.nan
    dark_spot_ratio: float = math.nan
    brown_area_ratio: float = math.nan
    red_green_ratio: float = math.nan
    yellow_green_ratio: float = math.nan
    nir_ratio: float = math.nan
    spectral_centroid_nm: float = math.nan
    reason: str = ""


@dataclass
class BatchSummary:
    timestamp: str
    batch_id: str
    total_count: int = 0
    unripe_count: int = 0
    ripe_count: int = 0
    overripe_count: int = 0
    grade_a_count: int = 0
    grade_b_count: int = 0
    grade_c_count: int = 0
    reject_count: int = 0
    saleable_count: int = 0
    saleable_ratio: float = 0.0
    rot_risk_count: int = 0
    rot_risk_ratio: float = 0.0
    channel_sales_count: int = 0
    channel_ripen_count: int = 0
    channel_process_count: int = 0
    channel_recheck_count: int = 0
    channel_reject_count: int = 0
    last_mango_id: str = ""
    last_quality_grade: str = ""
    last_suggested_channel: str = ""
    last_maturity_label: str = ""
    last_final_status: str = ""
    last_timestamp: str = ""


def clamp(value, low=0.0, high=100.0):
    if value is None or is_nan(value):
        return low
    return max(low, min(high, float(value)))


def is_nan(value):
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def safe_float(value, default=math.nan):
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def ratio_score(value, low, high):
    if is_nan(value):
        return math.nan
    if high == low:
        return 0.0
    return clamp((float(value) - low) * 100.0 / (high - low))


def inverse_ratio_score(value, low, high):
    if is_nan(value):
        return math.nan
    return 100.0 - ratio_score(value, low, high)


def weighted_average(items):
    total_weight = 0.0
    weighted_sum = 0.0
    for value, weight in items:
        if is_nan(value) or weight <= 0:
            continue
        total_weight += weight
        weighted_sum += float(value) * weight
    if total_weight <= 0:
        return math.nan
    return weighted_sum / total_weight


def normalize_label(label):
    text = str(label or "").strip()
    lowered = text.lower().replace(" ", "_")
    return MANGO_LABELS.get(text) or MANGO_LABELS.get(lowered)


def read_csv_rows(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle)]


def row_timestamp(row):
    return str(row.get("timestamp") or row.get("timestamp_iso") or "").strip()


def read_latest_vision(path=DEFAULT_VISION_CSV, max_age_s=None):
    rows = read_csv_rows(path)
    candidates = []
    for row in rows:
        if max_age_s is not None and not is_recent_timestamp(row_timestamp(row), max_age_s):
            continue
        label_info = normalize_label(row.get("label"))
        if not label_info:
            continue
        confidence = safe_float(row.get("confidence"), 0.0)
        area = safe_float(row.get("area_px"), 0.0)
        rank = confidence * max(1.0, math.log10(max(area, 1.0)))
        candidates.append((rank, row, label_info))

    if not candidates:
        return None

    _rank, row, label_info = max(candidates, key=lambda item: item[0])
    label_key, _label_score, _label_zh = label_info
    return VisionFeatures(
        timestamp=row_timestamp(row),
        mango_id=str(row.get("mango_id", "")),
        stable_frames=int(safe_float(row.get("stable_frames"), 0.0) or 0),
        consistency_label=str(row.get("consistency_label", "")),
        consistency_score=clamp(safe_float(row.get("consistency_score"), 0.0), 0.0, 1.0),
        label=str(row.get("label", "")),
        label_key=label_key,
        confidence=clamp(safe_float(row.get("confidence"), 0.0), 0.0, 1.0),
        area_px=safe_float(row.get("area_px"), 0.0),
        rgb_r_mean=safe_float(row.get("rgb_r_mean")),
        rgb_g_mean=safe_float(row.get("rgb_g_mean")),
        rgb_b_mean=safe_float(row.get("rgb_b_mean")),
        hsv_h_mean_deg=safe_float(row.get("hsv_h_mean_deg")),
        hsv_s_mean_pct=safe_float(row.get("hsv_s_mean_pct")),
        hsv_v_mean_pct=safe_float(row.get("hsv_v_mean_pct")),
        green_ratio=safe_float(row.get("green_ratio")),
        yellow_orange_ratio=safe_float(row.get("yellow_orange_ratio")),
        dark_spot_ratio=safe_float(row.get("dark_spot_ratio")),
        brown_area_ratio=safe_float(row.get("brown_area_ratio")),
        raw=row,
    )


def read_latest_object(path=DEFAULT_OBJECT_CSV):
    return read_latest_vision(path, max_age_s=OBJECT_STALE_SECONDS)


def _first_existing_spectrum_path(path):
    explicit = Path(path) if path else None
    if explicit and explicit.exists():
        return explicit
    if DEFAULT_SPECTRUM_CSV.exists():
        return DEFAULT_SPECTRUM_CSV
    if ALT_SPECTRUM_CSV.exists():
        return ALT_SPECTRUM_CSV
    return explicit or DEFAULT_SPECTRUM_CSV


def read_latest_spectrum(path=DEFAULT_SPECTRUM_CSV, max_age_s=None):
    rows = read_csv_rows(_first_existing_spectrum_path(path))
    if not rows:
        return None

    row = rows[-1]
    timestamp = row_timestamp(row)
    if max_age_s is not None and not is_recent_timestamp(timestamp, max_age_s):
        return None

    f4 = safe_float(row.get("f4_515"))
    f5 = safe_float(row.get("f5_555"))
    f6 = safe_float(row.get("f6_590"))
    f7 = safe_float(row.get("f7_630"))
    f8 = safe_float(row.get("f8_680"))
    green_sum = safe_float(row.get("green_sum"))
    red_sum = safe_float(row.get("red_sum"))
    blue_sum = safe_float(row.get("blue_sum"))

    if is_nan(green_sum):
        green_sum = sum_valid([f4, f5])
    if is_nan(red_sum):
        red_sum = sum_valid([f6, f7, f8])
    if is_nan(blue_sum):
        blue_sum = sum_valid(
            [
                safe_float(row.get("f1_415")),
                safe_float(row.get("f2_445")),
                safe_float(row.get("f3_480")),
            ]
        )

    denominator = max(green_sum, 1.0) if not is_nan(green_sum) else math.nan
    red_green_ratio = safe_div(red_sum, denominator)
    yellow_green_ratio = safe_div(f6, denominator)

    clear = safe_float(row.get("clear"))
    nir = safe_float(row.get("nir"))
    nir_ratio = safe_float(row.get("nir_ratio"))
    if is_nan(nir_ratio):
        nir_ratio = safe_div(nir, max(clear, 1.0) if not is_nan(clear) else math.nan)

    return SpectrumFeatures(
        timestamp=timestamp,
        f1_415=safe_float(row.get("f1_415")),
        f2_445=safe_float(row.get("f2_445")),
        f3_480=safe_float(row.get("f3_480")),
        f4_515=f4,
        f5_555=f5,
        f6_590=f6,
        f7_630=f7,
        f8_680=f8,
        clear=clear,
        nir=nir,
        nir_ratio=nir_ratio,
        dominant_wavelength_nm=safe_float(row.get("dominant_wavelength_nm")),
        spectral_centroid_nm=safe_float(row.get("spectral_centroid_nm")),
        red_sum=red_sum,
        green_sum=green_sum,
        blue_sum=blue_sum,
        red_green_ratio=red_green_ratio,
        yellow_green_ratio=yellow_green_ratio,
        raw=row,
    )


def sum_valid(values):
    total = 0.0
    used = False
    for value in values:
        if not is_nan(value):
            total += float(value)
            used = True
    return total if used else math.nan


def safe_div(numerator, denominator):
    if is_nan(numerator) or is_nan(denominator) or abs(float(denominator)) < 1e-9:
        return math.nan
    return float(numerator) / float(denominator)


def parse_timestamp(value):
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
        if stamp.tzinfo is not None:
            stamp = stamp.astimezone().replace(tzinfo=None)
        return stamp
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def is_recent_timestamp(value, max_age_s):
    stamp = parse_timestamp(value)
    if stamp is None:
        return False
    return abs((datetime.now() - stamp).total_seconds()) <= max_age_s


def yolo_maturity_score(vision):
    if vision is None:
        return math.nan
    label_info = normalize_label(vision.label)
    if not label_info:
        return math.nan
    _label_key, score, _label_zh = label_info
    return score


def color_maturity_score(vision):
    if vision is None:
        return math.nan

    ratio_based = weighted_average(
        [
            (20.0, ratio_weight(vision.green_ratio)),
            (70.0, ratio_weight(vision.yellow_orange_ratio)),
            (88.0, ratio_weight(vision.brown_area_ratio)),
            (92.0, ratio_weight(vision.dark_spot_ratio)),
        ]
    )
    if not is_nan(ratio_based):
        return ratio_based

    hue = vision.hsv_h_mean_deg
    sat = vision.hsv_s_mean_pct
    val = vision.hsv_v_mean_pct
    if is_nan(hue):
        return math.nan

    hue = hue % 360.0
    if 35.0 <= hue <= 95.0:
        score = 22.0 + inverse_ratio_score(hue, 35.0, 95.0) * 0.12
    elif 10.0 <= hue < 35.0:
        score = 63.0 + inverse_ratio_score(hue, 10.0, 35.0) * 0.12
    elif hue < 10.0 or hue >= 330.0:
        score = 78.0
    else:
        score = 55.0

    if not is_nan(sat):
        score += ratio_score(sat, 20.0, 75.0) * 0.08
    if not is_nan(val):
        if val < 35.0:
            score += 14.0
        elif val > 70.0:
            score -= 4.0
    return clamp(score)


def ratio_weight(value):
    if is_nan(value):
        return 0.0
    return max(0.0, float(value))


def spectrum_maturity_score(spectrum):
    if spectrum is None:
        return math.nan

    rg_score = ratio_score(spectrum.red_green_ratio, 0.85, 2.35)
    yg_score = ratio_score(spectrum.yellow_green_ratio, 0.15, 1.10)
    centroid_score = ratio_score(spectrum.spectral_centroid_nm, 510.0, 640.0)
    nir_score = ratio_score(spectrum.nir_ratio, 0.02, 0.45)

    return weighted_average(
        [
            (rg_score, 0.45),
            (yg_score, 0.20),
            (centroid_score, 0.25),
            (nir_score, 0.10),
        ]
    )


def estimate_dark_score(vision):
    if vision is None:
        return math.nan
    if not is_nan(vision.dark_spot_ratio):
        return clamp(vision.dark_spot_ratio * 280.0)

    val_score = inverse_ratio_score(vision.hsv_v_mean_pct, 25.0, 70.0)
    rgb_mean = weighted_average(
        [
            (vision.rgb_r_mean, 1.0),
            (vision.rgb_g_mean, 1.0),
            (vision.rgb_b_mean, 1.0),
        ]
    )
    rgb_score = inverse_ratio_score(rgb_mean, 45.0, 155.0)
    return weighted_average([(val_score, 0.65), (rgb_score, 0.35)])


def estimate_brown_score(vision):
    if vision is None:
        return math.nan
    if not is_nan(vision.brown_area_ratio):
        return clamp(vision.brown_area_ratio * 240.0)

    hue = vision.hsv_h_mean_deg
    sat = vision.hsv_s_mean_pct
    val = vision.hsv_v_mean_pct
    if is_nan(hue):
        return math.nan

    hue = hue % 360.0
    hue_signal = 0.0
    if 8.0 <= hue <= 38.0:
        hue_signal = 100.0
    elif 38.0 < hue <= 55.0:
        hue_signal = inverse_ratio_score(hue, 38.0, 55.0)

    sat_signal = ratio_score(sat, 15.0, 65.0)
    dark_signal = inverse_ratio_score(val, 35.0, 75.0)
    return weighted_average([(hue_signal, 0.45), (sat_signal, 0.20), (dark_signal, 0.35)])


def spectrum_abnormal_score(spectrum):
    if spectrum is None:
        return math.nan
    high_red = ratio_score(spectrum.red_green_ratio, 1.9, 3.2)
    high_centroid = ratio_score(spectrum.spectral_centroid_nm, 610.0, 680.0)
    low_nir = inverse_ratio_score(spectrum.nir_ratio, 0.03, 0.35)
    return weighted_average([(high_red, 0.45), (high_centroid, 0.35), (low_nir, 0.20)])


def rot_score(vision, spectrum):
    overripe_signal = 0.0
    if vision is not None and vision.label_key == "overripe":
        overripe_signal = vision.confidence * 100.0

    dark_weight = 0.45 if vision is not None and not is_nan(vision.dark_spot_ratio) else 0.15
    brown_weight = 0.25 if vision is not None and not is_nan(vision.brown_area_ratio) else 0.35
    overripe_weight = 0.25 if overripe_signal > 0 else 0.0
    spectrum_weight = 0.15 if spectrum is not None else 0.0

    return weighted_average(
        [
            (estimate_dark_score(vision), dark_weight),
            (estimate_brown_score(vision), brown_weight),
            (overripe_signal, overripe_weight),
            (spectrum_abnormal_score(spectrum), spectrum_weight),
        ]
    )


def sugar_score(maturity_score, vision, spectrum, rot_value):
    sat_score = ratio_score(vision.hsv_s_mean_pct, 20.0, 75.0) if vision else math.nan
    spectrum_sugar = weighted_average(
        [
            (ratio_score(spectrum.red_green_ratio, 0.85, 2.20), 0.65),
            (ratio_score(spectrum.nir_ratio, 0.02, 0.45), 0.35),
        ]
    ) if spectrum else math.nan

    score = weighted_average(
        [
            (maturity_score, 0.50),
            (spectrum_sugar, 0.30),
            (sat_score, 0.20),
        ]
    )
    if is_nan(score):
        return math.nan
    if not is_nan(rot_value) and rot_value >= 65.0:
        score = min(score, 82.0)
    return clamp(score)


def maturity_label(score):
    if is_nan(score):
        return "无法评估"
    if score < 45.0:
        return "未熟"
    if score < 78.0:
        return "成熟"
    return "过熟"


def sugar_label_and_brix(score, rot_value):
    if is_nan(score):
        return "无法评估", ""
    if not is_nan(rot_value) and rot_value >= 65.0:
        return "过熟异常，糖度参考不可靠", "不建议参考"
    if score < 40.0:
        return "偏低", "8-12 Brix"
    if score < 70.0:
        return "中等", "12-16 Brix"
    if score < 85.0:
        return "较高", "16-20 Brix"
    return "过熟偏高，仅供参考", "18-22 Brix"


def rot_status(score):
    if is_nan(score):
        return "无法评估"
    if score < 35.0:
        return "正常"
    if score < 65.0:
        return "疑似腐烂"
    return "腐烂/建议剔除"


def final_status(maturity, rot):
    if rot == "腐烂/建议剔除":
        return "建议剔除"
    if rot == "疑似腐烂":
        return "需要复检"
    if maturity == "无法评估" or maturity == "未检测到芒果":
        return "无有效检测"
    return "可接受"


def quality_grade(maturity, sugar, rot):
    if rot == "腐烂/建议剔除":
        return "剔除"
    if rot == "疑似腐烂":
        return "C级"
    if maturity == "成熟" and sugar in ("较高", "中等"):
        return "A级"
    if maturity == "成熟":
        return "B级"
    if maturity in ("未熟", "过熟"):
        return "B级"
    return "--"


def suggested_channel(maturity, sugar, rot):
    if rot == "腐烂/建议剔除":
        return "剔除通道"
    if rot == "疑似腐烂":
        return "复检通道"
    if maturity == "未熟":
        return "催熟通道"
    if maturity == "成熟":
        return "销售通道"
    if maturity == "过熟":
        return "加工通道"
    if sugar == "无法评估":
        return "等待数据"
    return "销售通道"


def data_status(vision, spectrum):
    parts = []
    parts.append("vision_ok" if vision else "vision_missing")
    parts.append("spectrum_ok" if spectrum else "spectrum_missing")
    return ",".join(parts)


def build_reason(vision, spectrum, maturity, sugar_label, rot):
    reasons = []
    if vision:
        if vision.mango_id:
            reasons.append("芒果#{}连续检测{}帧".format(vision.mango_id, vision.stable_frames))
        if vision.consistency_label:
            reasons.append("多帧稳定性{}".format(vision.consistency_label))
        reasons.append("视觉判断{}".format(vision.label))
    else:
        reasons.append("未读取到YOLO芒果检测结果")
    if spectrum:
        reasons.append("光谱数据已参与参考")
    else:
        reasons.append("未读取到光谱数据")
    reasons.append("成熟度={}".format(maturity))
    reasons.append("糖度={}".format(sugar_label))
    reasons.append("腐烂={}".format(rot))
    if vision and is_nan(vision.dark_spot_ratio):
        reasons.append("当前视觉CSV无斑点面积字段，腐烂判断基于均值特征")
    return "; ".join(reasons)


def assess_mango_quality(vision=None, spectrum=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if vision is None:
        return QualityAssessment(
            timestamp=timestamp,
            spectrum_timestamp=spectrum.timestamp if spectrum else "",
            data_status=data_status(vision, spectrum),
            reason=build_reason(vision, spectrum, "未检测到芒果", "无法评估", "无法评估"),
        )

    yolo_score = yolo_maturity_score(vision)
    color_score = color_maturity_score(vision)
    spectral_score = spectrum_maturity_score(spectrum)

    yolo_weight = 0.60 * max(0.25, vision.confidence)
    maturity_value = weighted_average(
        [
            (yolo_score, yolo_weight),
            (color_score, 0.25),
            (spectral_score, 0.15),
        ]
    )
    if is_nan(maturity_value):
        maturity_value = 0.0

    rot_value = rot_score(vision, spectrum)
    sugar_value = sugar_score(maturity_value, vision, spectrum, rot_value)
    maturity = maturity_label(maturity_value)
    sugar_label, brix_range = sugar_label_and_brix(sugar_value, rot_value)
    rot = rot_status(rot_value)
    grade = quality_grade(maturity, sugar_label, rot)
    channel = suggested_channel(maturity, sugar_label, rot)

    source_count = int(vision is not None) + int(spectrum is not None)
    maturity_confidence = clamp(45.0 + vision.confidence * 35.0 + source_count * 10.0)
    if spectrum is None:
        maturity_confidence = min(maturity_confidence, 78.0)

    return QualityAssessment(
        timestamp=timestamp,
        mango_id=vision.mango_id,
        stable_frames=vision.stable_frames,
        consistency_label=vision.consistency_label,
        consistency_score=round(vision.consistency_score, 4),
        quality_grade=grade,
        suggested_channel=channel,
        vision_timestamp=vision.timestamp,
        spectrum_timestamp=spectrum.timestamp if spectrum else "",
        data_status=data_status(vision, spectrum),
        yolo_label=vision.label,
        yolo_confidence=round(vision.confidence, 4),
        maturity_label=maturity,
        maturity_score=round(maturity_value, 2),
        maturity_confidence=round(maturity_confidence, 2),
        sugar_label=sugar_label,
        sugar_score=round(sugar_value, 2) if not is_nan(sugar_value) else 0.0,
        reference_brix_range=brix_range,
        rot_status=rot,
        rot_score=round(rot_value, 2) if not is_nan(rot_value) else 0.0,
        final_status=final_status(maturity, rot),
        rgb_r_mean=vision.rgb_r_mean,
        rgb_g_mean=vision.rgb_g_mean,
        rgb_b_mean=vision.rgb_b_mean,
        hsv_h_mean_deg=vision.hsv_h_mean_deg,
        hsv_s_mean_pct=vision.hsv_s_mean_pct,
        hsv_v_mean_pct=vision.hsv_v_mean_pct,
        green_ratio=vision.green_ratio,
        yellow_orange_ratio=vision.yellow_orange_ratio,
        dark_spot_ratio=vision.dark_spot_ratio,
        brown_area_ratio=vision.brown_area_ratio,
        red_green_ratio=spectrum.red_green_ratio if spectrum else math.nan,
        yellow_green_ratio=spectrum.yellow_green_ratio if spectrum else math.nan,
        nir_ratio=spectrum.nir_ratio if spectrum else math.nan,
        spectral_centroid_nm=spectrum.spectral_centroid_nm if spectrum else math.nan,
        reason=build_reason(vision, spectrum, maturity, sugar_label, rot),
    )


def assessment_to_row(assessment):
    row = asdict(assessment)
    output = {}
    for field_name in QUALITY_FIELDS:
        value = row.get(field_name, "")
        if isinstance(value, float):
            output[field_name] = "" if is_nan(value) else "{:.4f}".format(value)
        else:
            output[field_name] = value
    return output


def assessment_has_object(assessment):
    if assessment is None:
        return False
    mango_id = str(assessment.mango_id or "").strip()
    if not mango_id or mango_id == "--":
        return False
    if assessment.final_status == "无有效检测":
        return False
    return True


def _is_saleable(assessment):
    return assessment.quality_grade in ("A级", "B级") and assessment.suggested_channel == "销售通道"


class BatchAccumulator:
    def __init__(self, batch_id=None, assessments=None, source_ids=None):
        self.batch_id = batch_id or time.strftime("%Y%m%d_%H%M%S")
        self.seen_ids = set()
        self.assessments = []
        self.source_ids = dict(source_ids or {})
        self.next_mango_number = 1
        for assessment in assessments or []:
            if assessment_has_object(assessment):
                mango_id = str(assessment.mango_id).strip()
                self.seen_ids.add(mango_id)
                self.assessments.append(assessment)
                if mango_id.isdigit():
                    self.next_mango_number = max(self.next_mango_number, int(mango_id) + 1)

    @staticmethod
    def _legacy_source_id(mango_id):
        text = str(mango_id or "").strip()
        tail = text.rsplit("-", 1)[-1]
        return tail if tail.isdigit() else text

    @classmethod
    def _source_key(cls, assessment, mango_id=None):
        source_id = cls._legacy_source_id(
            assessment.mango_id if mango_id is None else mango_id
        )
        timestamp = str(assessment.vision_timestamp or assessment.timestamp or "").strip()
        return "{}|{}".format(timestamp, source_id)

    def assign_mango_id(self, assessment):
        if not assessment_has_object(assessment):
            return ""

        raw_id = str(assessment.mango_id).strip()
        source_key = self._source_key(assessment, raw_id)
        mango_id = self.source_ids.get(source_key)
        if not mango_id:
            mango_id = str(self.next_mango_number)
            self.next_mango_number += 1
            self.source_ids[source_key] = mango_id

        assessment.mango_id = mango_id
        old_reason = "芒果#{}连续".format(raw_id)
        if old_reason in assessment.reason:
            assessment.reason = assessment.reason.replace(
                old_reason,
                "芒果#{}连续".format(mango_id),
                1,
            )
        return mango_id

    @classmethod
    def load(cls, path, batch_id=None):
        path = Path(path)
        if not path.exists() or path.stat().st_size == 0:
            return cls(batch_id)

        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return cls(batch_id)

        saved_batch_id = str(data.get("batch_id") or "").strip()
        if batch_id and saved_batch_id and saved_batch_id != str(batch_id):
            return cls(batch_id)

        assessments = []
        source_ids = data.get("source_ids")
        if not isinstance(source_ids, dict):
            source_ids = {}
        migrate_legacy_ids = not source_ids
        for item in data.get("assessments") or []:
            if not isinstance(item, dict):
                continue
            payload = {field_name: item.get(field_name, "") for field_name in QUALITY_FIELDS}
            assessment = QualityAssessment(**payload)
            if migrate_legacy_ids and assessment_has_object(assessment):
                legacy_id = str(assessment.mango_id).strip()
                display_id = str(len(assessments) + 1)
                source_ids[cls._source_key(assessment, legacy_id)] = display_id
                assessment.mango_id = display_id
            assessments.append(assessment)
        return cls(batch_id or saved_batch_id or None, assessments, source_ids)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "batch_id": self.batch_id,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seen_ids": sorted(self.seen_ids),
            "source_ids": self.source_ids,
            "assessments": [
                {key: json_safe_value(value) for key, value in asdict(assessment).items()}
                for assessment in self.assessments
            ],
        }
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temp_path, path)

    def add(self, assessment):
        if not assessment_has_object(assessment):
            return False

        mango_id = str(assessment.mango_id).strip()
        if mango_id in self.seen_ids:
            return False

        self.seen_ids.add(mango_id)
        self.assessments.append(assessment)
        return True

    def summary(self):
        summary = BatchSummary(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            batch_id=self.batch_id,
        )

        summary.total_count = len(self.assessments)
        if not self.assessments:
            return summary

        for item in self.assessments:
            if item.maturity_label == "未熟":
                summary.unripe_count += 1
            elif item.maturity_label == "成熟":
                summary.ripe_count += 1
            elif item.maturity_label == "过熟":
                summary.overripe_count += 1

            if item.quality_grade == "A级":
                summary.grade_a_count += 1
            elif item.quality_grade == "B级":
                summary.grade_b_count += 1
            elif item.quality_grade == "C级":
                summary.grade_c_count += 1
            elif item.quality_grade == "剔除":
                summary.reject_count += 1

            if _is_saleable(item):
                summary.saleable_count += 1

            if item.rot_status in ("疑似腐烂", "腐烂/建议剔除") or item.final_status in ("需要复检", "建议剔除"):
                summary.rot_risk_count += 1

            if item.suggested_channel == "销售通道":
                summary.channel_sales_count += 1
            elif item.suggested_channel == "催熟通道":
                summary.channel_ripen_count += 1
            elif item.suggested_channel == "加工通道":
                summary.channel_process_count += 1
            elif item.suggested_channel == "复检通道":
                summary.channel_recheck_count += 1
            elif item.suggested_channel == "剔除通道":
                summary.channel_reject_count += 1

        summary.saleable_ratio = round(summary.saleable_count * 100.0 / max(summary.total_count, 1), 2)
        summary.rot_risk_ratio = round(summary.rot_risk_count * 100.0 / max(summary.total_count, 1), 2)

        last = self.assessments[-1]
        summary.last_mango_id = last.mango_id
        summary.last_quality_grade = last.quality_grade
        summary.last_suggested_channel = last.suggested_channel
        summary.last_maturity_label = last.maturity_label
        summary.last_final_status = last.final_status
        summary.last_timestamp = last.timestamp
        return summary


def batch_summary_to_row(summary):
    row = asdict(summary)
    output = {}
    for field_name in BATCH_FIELDS:
        value = row.get(field_name, "")
        if isinstance(value, float):
            output[field_name] = "{:.2f}".format(value)
        else:
            output[field_name] = value
    return output


def assessment_to_history_row(assessment):
    row = assessment_to_row(assessment)
    return {field_name: row.get(field_name, "") for field_name in HISTORY_FIELDS}


def write_assessment_csv(path, assessment):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUALITY_FIELDS)
        writer.writeheader()
        writer.writerow(assessment_to_row(assessment))
    os.replace(temp_path, path)


def write_batch_summary_csv(path, summary):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATCH_FIELDS)
        writer.writeheader()
        writer.writerow(batch_summary_to_row(summary))
    os.replace(temp_path, path)


def write_assessment_history_csv(path, assessment, max_rows=200):
    if not assessment_has_object(assessment):
        return False

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle)]

    mango_id = str(assessment.mango_id).strip()
    timestamp = str(assessment.timestamp or "").strip()
    rows = [
        row
        for row in rows
        if not (
            str(row.get("mango_id", "")).strip() == mango_id
            and str(row.get("timestamp", "")).strip() == timestamp
        )
    ]
    rows.append(assessment_to_history_row(assessment))
    rows = rows[-max(1, int(max_rows)):]

    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp_path, path)
    return True


def json_safe_value(value):
    if isinstance(value, float) and is_nan(value):
        return None
    return value


def write_assessment_json(path, assessment):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    data = {key: json_safe_value(value) for key, value in asdict(assessment).items()}
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temp_path, path)


def write_batch_summary_json(path, summary):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    data = {key: json_safe_value(value) for key, value in asdict(summary).items()}
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temp_path, path)

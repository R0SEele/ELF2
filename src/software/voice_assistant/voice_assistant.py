#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path("/home/elf/projects")
DEFAULT_QUALITY_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_quality_realtime.csv"
DEFAULT_HISTORY_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_quality_history.csv"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_TIMEOUT_S = 15
INVALID_FINAL_STATUSES = {"", "--", "无有效检测"}


def read_latest_csv_row(path):
    csv_path = Path(path)
    if not csv_path.exists() or csv_path.stat().st_size <= 0:
        return {}

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        latest = {}
        for row in reader:
            if any((value or "").strip() for value in row.values()):
                latest = row
        return latest


def is_valid_mango_result(row):
    final_status = (row.get("final_status") or "").strip()
    mango_id = (row.get("mango_id") or "").strip()
    maturity = (row.get("maturity_label") or "").strip()

    if final_status in INVALID_FINAL_STATUSES:
        return False
    if maturity in ("", "--", "未检测到芒果"):
        return False
    return bool(mango_id or maturity)


def local_announcement(row):
    grade = value_or(row, "quality_grade", "未评级")
    maturity = value_or(row, "maturity_label", "成熟度未知")
    sugar = value_or(row, "reference_brix_range", "")
    sugar_label = value_or(row, "sugar_label", "")
    rot = value_or(row, "rot_status", "腐烂情况未知")
    channel = value_or(row, "suggested_channel", "待人工确认")
    final_status = value_or(row, "final_status", "检测完成")
    mango_id = (row.get("mango_id") or "").strip()

    subject = "当前芒果"
    if mango_id and mango_id != "--":
        subject = "当前芒果"

    sugar_text = ""
    if sugar and sugar != "--":
        sugar_text = "，参考糖度{}".format(sugar)
    elif sugar_label and sugar_label != "--":
        sugar_text = "，糖度{}".format(sugar_label)

    return "{}检测完成，等级{}，成熟度{}{}，腐烂状况{}，建议{}。".format(
        subject,
        grade,
        maturity,
        sugar_text,
        rot,
        channel if channel != "--" else final_status,
    )


def value_or(row, key, fallback):
    value = (row.get(key) or "").strip()
    return value if value and value != "--" else fallback


def deepseek_announcement(row, api_key, model=DEFAULT_MODEL, api_base=DEFAULT_API_BASE, timeout_s=DEFAULT_TIMEOUT_S):
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    endpoint = api_base.rstrip("/") + "/chat/completions"
    prompt_payload = {
        "quality_grade": row.get("quality_grade", ""),
        "maturity_label": row.get("maturity_label", ""),
        "maturity_confidence": row.get("maturity_confidence", ""),
        "reference_brix_range": row.get("reference_brix_range", ""),
        "sugar_label": row.get("sugar_label", ""),
        "rot_status": row.get("rot_status", ""),
        "final_status": row.get("final_status", ""),
        "suggested_channel": row.get("suggested_channel", ""),
        "data_status": row.get("data_status", ""),
        "reason": row.get("reason", ""),
    }

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是芒果品质检测设备的语音播报助手。"
                    "根据检测字段生成一句普通人能听懂的中文播报。"
                    "要求：不超过45个汉字；语气客观；不要提CSV、模型、算法、置信度；"
                    "不要编造字段以外的信息。"
                ),
            },
            {
                "role": "user",
                "content": "检测结果JSON：{}\n请生成一句现场播报。".format(
                    json.dumps(prompt_payload, ensure_ascii=False)
                ),
            },
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0.3,
        "max_tokens": 120,
        "stream": False,
    }

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": "Bearer {}".format(api_key),
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("DeepSeek API HTTP {}: {}".format(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("DeepSeek API connection failed: {}".format(exc.reason)) from exc

    try:
        text = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected DeepSeek response: {}".format(payload)) from exc

    return sanitize_announcement(text) or local_announcement(row)


def sanitize_announcement(text):
    cleaned = " ".join((text or "").replace("\n", " ").split()).strip()
    if len(cleaned) > 80:
        cleaned = cleaned[:80].rstrip("，。；、 ") + "。"
    return cleaned


def speak_text(text, backend="auto", wait=True, dry_run=False, alsa_device=""):
    if dry_run:
        print(text)
        return True

    candidates = []
    if backend == "auto":
        candidates = ["espeak-ng", "spd-say"]
    else:
        candidates = [backend]

    errors = []
    for candidate in candidates:
        exe = shutil.which(candidate)
        if not exe:
            errors.append("{} not found".format(candidate))
            continue

        if candidate == "espeak-ng":
            cmd = [exe, "-v", "zh", "-s", "155", text]
        elif candidate == "spd-say":
            cmd = [exe, "-l", "zh-CN", "-r", "-10"]
            if wait:
                cmd.append("-w")
            cmd.append(text)
        else:
            errors.append("unsupported backend {}".format(candidate))
            continue

        env = os.environ.copy()
        if candidate == "espeak-ng" and alsa_device:
            env["AUDIODEV"] = alsa_device

        try:
            subprocess.run(cmd, check=True, env=env)
            return True
        except subprocess.CalledProcessError as exc:
            errors.append("{} failed with code {}".format(candidate, exc.returncode))
        except OSError as exc:
            errors.append("{} failed: {}".format(candidate, exc))

    raise RuntimeError("No usable TTS backend: {}".format("; ".join(errors)))


def build_announcement(row, use_api=True, model=DEFAULT_MODEL, api_base=DEFAULT_API_BASE, timeout_s=DEFAULT_TIMEOUT_S):
    if use_api:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        try:
            return deepseek_announcement(row, api_key, model=model, api_base=api_base, timeout_s=timeout_s), "deepseek"
        except Exception as exc:
            print("voice_assistant: DeepSeek fallback: {}".format(exc), file=sys.stderr)

    return local_announcement(row), "local"


def parse_args():
    parser = argparse.ArgumentParser(description="Announce mango quality results with DeepSeek and local TTS.")
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV), help="Realtime mango quality CSV")
    parser.add_argument("--history-csv", default=str(DEFAULT_HISTORY_CSV), help="Reserved for later history announcements")
    parser.add_argument("--text", default="", help="Speak this text directly instead of reading CSV")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--watch", action="store_true", help="Watch CSV and announce when a new mango result appears")
    parser.add_argument("--interval", type=float, default=1.0, help="Watch interval in seconds")
    parser.add_argument("--no-api", action="store_true", help="Use local fixed template, do not call DeepSeek")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="DeepSeek model name")
    parser.add_argument("--api-base", default=os.environ.get("DEEPSEEK_API_BASE", DEFAULT_API_BASE), help="DeepSeek API base URL")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="DeepSeek request timeout in seconds")
    parser.add_argument("--backend", default="auto", choices=["auto", "espeak-ng", "spd-say"], help="TTS backend")
    parser.add_argument(
        "--alsa-device",
        default=os.environ.get("VOICE_ALSA_DEVICE", ""),
        help="ALSA output device for espeak-ng, for example plughw:1,0",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print announcement without speaking")
    parser.add_argument("--speak-invalid", action="store_true", help="Also announce invalid/no-mango results")
    return parser.parse_args()


def row_identity(row):
    return "|".join(
        [
            (row.get("mango_id") or "").strip(),
            (row.get("timestamp") or "").strip(),
            (row.get("quality_grade") or "").strip(),
            (row.get("final_status") or "").strip(),
        ]
    )


def announce_latest(args, last_identity=""):
    if args.text.strip():
        text = sanitize_announcement(args.text)
        speak_text(text, backend=args.backend, dry_run=args.dry_run, alsa_device=args.alsa_device)
        return row_identity({"timestamp": str(time.time()), "final_status": text}), text

    row = read_latest_csv_row(args.quality_csv)
    if not row:
        text = "暂未读取到芒果检测结果。"
        if args.speak_invalid:
            speak_text(text, backend=args.backend, dry_run=args.dry_run, alsa_device=args.alsa_device)
        return last_identity, text

    identity = row_identity(row)
    if identity and identity == last_identity:
        return last_identity, ""

    if not args.speak_invalid and not is_valid_mango_result(row):
        return identity, ""

    text, source = build_announcement(
        row,
        use_api=not args.no_api,
        model=args.model,
        api_base=args.api_base,
        timeout_s=args.timeout,
    )
    print("voice_assistant: announcement source={}: {}".format(source, text), file=sys.stderr)
    speak_text(text, backend=args.backend, dry_run=args.dry_run, alsa_device=args.alsa_device)
    return identity, text


def main():
    args = parse_args()
    if args.interval <= 0:
        print("interval must be > 0", file=sys.stderr)
        return 2

    if args.once or not args.watch:
        announce_latest(args)
        return 0

    last_identity = ""
    try:
        while True:
            last_identity, _text = announce_latest(args, last_identity)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

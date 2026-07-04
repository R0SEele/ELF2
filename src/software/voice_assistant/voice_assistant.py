#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path("/home/elf/projects")
DEFAULT_QUALITY_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_quality_realtime.csv"
DEFAULT_HISTORY_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_quality_history.csv"
DEFAULT_BATCH_CSV = PROJECT_ROOT / "datas" / "csv" / "mango_batch_summary.csv"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_TIMEOUT_S = 15
DEFAULT_TTS_TIMEOUT_S = 12
INVALID_FINAL_STATUSES = {"", "--", "无有效检测"}
DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"


def find_executable(name):
    exe = shutil.which(name)
    if exe:
        return exe

    local_bin = Path.home() / ".local" / "bin" / name
    if local_bin.exists() and os.access(str(local_bin), os.X_OK):
        return str(local_bin)

    return ""


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


def local_announcement(row, subject="当前芒果"):
    grade = value_or(row, "quality_grade", "未评级")
    maturity = value_or(row, "maturity_label", "成熟度未知")
    sugar = value_or(row, "reference_brix_range", "")
    sugar_label = value_or(row, "sugar_label", "")
    rot = value_or(row, "rot_status", "腐烂情况未知")
    channel = value_or(row, "suggested_channel", "待人工确认")
    final_status = value_or(row, "final_status", "检测完成")

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


def int_value(row, key, fallback=0):
    try:
        return int(float((row.get(key) or "").strip()))
    except (TypeError, ValueError):
        return fallback


def float_value(row, key, fallback=0.0):
    try:
        return float((row.get(key) or "").strip())
    except (TypeError, ValueError):
        return fallback


def local_batch_announcement(row):
    total = int_value(row, "total_count")
    reject = int_value(row, "reject_count")
    saleable = float_value(row, "saleable_ratio")
    rot_risk = float_value(row, "rot_risk_ratio")

    if total <= 0:
        return "当前批次尚未统计到有效芒果。"

    return "本批次共{}个芒果，可销售{:.1f}%，剔除{}个，异常风险{:.1f}%。".format(
        total,
        saleable,
        reject,
        rot_risk,
    )


def value_or(row, key, fallback):
    value = (row.get(key) or "").strip()
    return value if value and value != "--" else fallback


def deepseek_announcement(row, api_key, model=DEFAULT_MODEL, api_base=DEFAULT_API_BASE, timeout_s=DEFAULT_TIMEOUT_S, subject="当前芒果"):
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    endpoint = api_base.rstrip("/") + "/chat/completions"
    prompt_payload = {
        "subject": subject,
        "mango_id": row.get("mango_id", ""),
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
                "content": "播报对象：{}。\n检测结果JSON：{}\n请生成一句现场播报。".format(
                    subject,
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

    return sanitize_announcement(text) or local_announcement(row, subject=subject)


def deepseek_batch_announcement(row, api_key, model=DEFAULT_MODEL, api_base=DEFAULT_API_BASE, timeout_s=DEFAULT_TIMEOUT_S):
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    endpoint = api_base.rstrip("/") + "/chat/completions"
    prompt_payload = {
        "batch_id": row.get("batch_id", ""),
        "total_count": row.get("total_count", ""),
        "unripe_count": row.get("unripe_count", ""),
        "ripe_count": row.get("ripe_count", ""),
        "overripe_count": row.get("overripe_count", ""),
        "grade_a_count": row.get("grade_a_count", ""),
        "grade_b_count": row.get("grade_b_count", ""),
        "grade_c_count": row.get("grade_c_count", ""),
        "reject_count": row.get("reject_count", ""),
        "saleable_count": row.get("saleable_count", ""),
        "saleable_ratio": row.get("saleable_ratio", ""),
        "rot_risk_count": row.get("rot_risk_count", ""),
        "rot_risk_ratio": row.get("rot_risk_ratio", ""),
        "channel_sales_count": row.get("channel_sales_count", ""),
        "channel_ripen_count": row.get("channel_ripen_count", ""),
        "channel_process_count": row.get("channel_process_count", ""),
        "channel_recheck_count": row.get("channel_recheck_count", ""),
        "channel_reject_count": row.get("channel_reject_count", ""),
        "last_mango_id": row.get("last_mango_id", ""),
        "last_quality_grade": row.get("last_quality_grade", ""),
        "last_suggested_channel": row.get("last_suggested_channel", ""),
        "last_maturity_label": row.get("last_maturity_label", ""),
        "last_final_status": row.get("last_final_status", ""),
    }

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是芒果品质检测设备的语音播报助手。"
                    "根据批次统计字段生成一句普通人能听懂的中文批次评价。"
                    "要求：不超过55个汉字；语气客观；不要提CSV、模型、算法、置信度；"
                    "不要编造字段以外的信息。"
                ),
            },
            {
                "role": "user",
                "content": "批次统计JSON：{}\n请生成一句现场播报。".format(
                    json.dumps(prompt_payload, ensure_ascii=False)
                ),
            },
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0.3,
        "max_tokens": 140,
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

    return sanitize_announcement(text) or local_batch_announcement(row)


def sanitize_announcement(text):
    cleaned = " ".join((text or "").replace("\n", " ").split()).strip()
    if len(cleaned) > 80:
        cleaned = cleaned[:80].rstrip("，。；、 ") + "。"
    return cleaned


def play_audio_file(path, alsa_device="", timeout_s=DEFAULT_TTS_TIMEOUT_S):
    players = []
    mpv = find_executable("mpv")
    if mpv:
        cmd = [mpv, "--no-video", "--really-quiet"]
        if alsa_device:
            cmd.append("--audio-device=alsa/{}".format(alsa_device))
        cmd.append(path)
        players.append(("mpv", cmd))

    ffplay = find_executable("ffplay")
    if ffplay:
        players.append(("ffplay", [ffplay, "-nodisp", "-autoexit", "-loglevel", "error", path]))

    errors = []
    for name, cmd in players:
        try:
            subprocess.run(cmd, check=True, timeout=timeout_s)
            return True
        except subprocess.CalledProcessError as exc:
            errors.append("{} failed with code {}".format(name, exc.returncode))
        except subprocess.TimeoutExpired:
            errors.append("{} timed out after {}s".format(name, timeout_s))
        except OSError as exc:
            errors.append("{} failed: {}".format(name, exc))

    raise RuntimeError("No usable audio player: {}".format("; ".join(errors) or "mpv/ffplay not found"))


def speak_text(
    text,
    backend="auto",
    wait=True,
    dry_run=False,
    alsa_device="",
    edge_voice=DEFAULT_EDGE_VOICE,
    tts_timeout_s=DEFAULT_TTS_TIMEOUT_S,
):
    if dry_run:
        print(text)
        return True

    candidates = []
    if backend == "auto":
        candidates = ["edge-tts", "espeak-ng", "spd-say"]
    else:
        candidates = [backend]

    errors = []
    for candidate in candidates:
        exe = find_executable(candidate)
        if not exe:
            errors.append("{} not found".format(candidate))
            continue

        if candidate == "edge-tts":
            media_path = ""
            try:
                with tempfile.NamedTemporaryFile(prefix="voice_assistant_", suffix=".mp3", delete=False) as media_file:
                    media_path = media_file.name
                subprocess.run(
                    [
                        exe,
                        "--voice",
                        edge_voice,
                        "--text",
                        text,
                        "--write-media",
                        media_path,
                    ],
                    check=True,
                    timeout=tts_timeout_s,
                )
                play_audio_file(media_path, alsa_device=alsa_device, timeout_s=tts_timeout_s)
                return True
            except subprocess.CalledProcessError as exc:
                errors.append("{} failed with code {}".format(candidate, exc.returncode))
                continue
            except subprocess.TimeoutExpired:
                errors.append("{} timed out after {}s".format(candidate, tts_timeout_s))
                continue
            except OSError as exc:
                errors.append("{} failed: {}".format(candidate, exc))
                continue
            except RuntimeError as exc:
                errors.append("{} playback failed: {}".format(candidate, exc))
                continue
            finally:
                if media_path:
                    try:
                        os.unlink(media_path)
                    except OSError:
                        pass

        if candidate == "espeak-ng":
            if alsa_device:
                aplay = find_executable("aplay")
                if not aplay:
                    errors.append("aplay not found for ALSA device {}".format(alsa_device))
                    continue

                wav_path = ""
                try:
                    with tempfile.NamedTemporaryFile(prefix="voice_assistant_", suffix=".wav", delete=False) as wav_file:
                        wav_path = wav_file.name
                    subprocess.run([exe, "-v", "zh", "-s", "155", "-w", wav_path, text], check=True, timeout=tts_timeout_s)
                    subprocess.run([aplay, "-D", alsa_device, wav_path], check=True, timeout=tts_timeout_s)
                    return True
                except subprocess.CalledProcessError as exc:
                    errors.append("{} or aplay failed with code {}".format(candidate, exc.returncode))
                    continue
                except subprocess.TimeoutExpired:
                    errors.append("{} or aplay timed out after {}s".format(candidate, tts_timeout_s))
                    continue
                except OSError as exc:
                    errors.append("{} or aplay failed: {}".format(candidate, exc))
                    continue
                finally:
                    if wav_path:
                        try:
                            os.unlink(wav_path)
                        except OSError:
                            pass

            cmd = [exe, "-v", "zh", "-s", "155", text]
        elif candidate == "spd-say":
            cmd = [exe, "-l", "zh-CN", "-r", "-10"]
            if wait:
                cmd.append("-w")
            cmd.append(text)
        else:
            errors.append("unsupported backend {}".format(candidate))
            continue

        try:
            subprocess.run(cmd, check=True, timeout=tts_timeout_s)
            return True
        except subprocess.CalledProcessError as exc:
            errors.append("{} failed with code {}".format(candidate, exc.returncode))
        except subprocess.TimeoutExpired:
            errors.append("{} timed out after {}s".format(candidate, tts_timeout_s))
        except OSError as exc:
            errors.append("{} failed: {}".format(candidate, exc))

    raise RuntimeError("No usable TTS backend: {}".format("; ".join(errors)))


def build_announcement(row, use_api=True, model=DEFAULT_MODEL, api_base=DEFAULT_API_BASE, timeout_s=DEFAULT_TIMEOUT_S, subject="当前芒果"):
    if use_api:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        try:
            return deepseek_announcement(row, api_key, model=model, api_base=api_base, timeout_s=timeout_s, subject=subject), "deepseek"
        except Exception as exc:
            print("voice_assistant: DeepSeek fallback: {}".format(exc), file=sys.stderr)

    return local_announcement(row, subject=subject), "local"


def build_batch_announcement(row, use_api=True, model=DEFAULT_MODEL, api_base=DEFAULT_API_BASE, timeout_s=DEFAULT_TIMEOUT_S):
    if use_api:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        try:
            return deepseek_batch_announcement(row, api_key, model=model, api_base=api_base, timeout_s=timeout_s), "deepseek"
        except Exception as exc:
            print("voice_assistant: DeepSeek batch fallback: {}".format(exc), file=sys.stderr)

    return local_batch_announcement(row), "local"


def parse_args():
    parser = argparse.ArgumentParser(description="Announce mango quality results with DeepSeek and local TTS.")
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV), help="Realtime mango quality CSV")
    parser.add_argument("--history-csv", default=str(DEFAULT_HISTORY_CSV), help="Mango quality history CSV")
    parser.add_argument("--batch-csv", default=str(DEFAULT_BATCH_CSV), help="Mango batch summary CSV")
    parser.add_argument(
        "--target",
        default="current",
        choices=["current", "previous", "batch"],
        help="Announcement target: realtime current mango, latest historical mango, or whole batch",
    )
    parser.add_argument("--text", default="", help="Speak this text directly instead of reading CSV")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--watch", action="store_true", help="Watch CSV and announce when a new mango result appears")
    parser.add_argument("--interval", type=float, default=1.0, help="Watch interval in seconds")
    parser.add_argument("--no-api", action="store_true", help="Use local fixed template, do not call DeepSeek")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="DeepSeek model name")
    parser.add_argument("--api-base", default=os.environ.get("DEEPSEEK_API_BASE", DEFAULT_API_BASE), help="DeepSeek API base URL")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="DeepSeek request timeout in seconds")
    parser.add_argument(
        "--tts-timeout",
        type=float,
        default=float(os.environ.get("VOICE_TTS_TIMEOUT", DEFAULT_TTS_TIMEOUT_S)),
        help="TTS generation/playback timeout in seconds",
    )
    parser.add_argument("--backend", default="auto", choices=["auto", "edge-tts", "espeak-ng", "spd-say"], help="TTS backend")
    parser.add_argument(
        "--edge-voice",
        default=os.environ.get("VOICE_EDGE_VOICE", DEFAULT_EDGE_VOICE),
        help="edge-tts voice name",
    )
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


def batch_identity(row):
    return "|".join(
        [
            (row.get("batch_id") or "").strip(),
            (row.get("timestamp") or "").strip(),
            (row.get("total_count") or "").strip(),
            (row.get("last_mango_id") or "").strip(),
        ]
    )


def is_valid_batch_result(row):
    return int_value(row, "total_count") > 0


def announce_mango_from_csv(args, path, subject, no_data_text, last_identity=""):
    row = read_latest_csv_row(path)
    if not row:
        text = no_data_text
        if args.speak_invalid:
            speak_text(
                text,
                backend=args.backend,
                dry_run=args.dry_run,
                alsa_device=args.alsa_device,
                edge_voice=args.edge_voice,
                tts_timeout_s=args.tts_timeout,
            )
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
        subject=subject,
    )
    print("voice_assistant: announcement source={}: {}".format(source, text), file=sys.stderr)
    speak_text(
        text,
        backend=args.backend,
        dry_run=args.dry_run,
        alsa_device=args.alsa_device,
        edge_voice=args.edge_voice,
        tts_timeout_s=args.tts_timeout,
    )
    return identity, text


def announce_batch(args, last_identity=""):
    row = read_latest_csv_row(args.batch_csv)
    if not row:
        text = "暂未读取到批次统计结果。"
        if args.speak_invalid:
            speak_text(
                text,
                backend=args.backend,
                dry_run=args.dry_run,
                alsa_device=args.alsa_device,
                edge_voice=args.edge_voice,
                tts_timeout_s=args.tts_timeout,
            )
        return last_identity, text

    identity = batch_identity(row)
    if identity and identity == last_identity:
        return last_identity, ""

    if not args.speak_invalid and not is_valid_batch_result(row):
        return identity, ""

    text, source = build_batch_announcement(
        row,
        use_api=not args.no_api,
        model=args.model,
        api_base=args.api_base,
        timeout_s=args.timeout,
    )
    print("voice_assistant: batch announcement source={}: {}".format(source, text), file=sys.stderr)
    speak_text(
        text,
        backend=args.backend,
        dry_run=args.dry_run,
        alsa_device=args.alsa_device,
        edge_voice=args.edge_voice,
        tts_timeout_s=args.tts_timeout,
    )
    return identity, text


def announce_latest(args, last_identity=""):
    if args.text.strip():
        text = sanitize_announcement(args.text)
        speak_text(
            text,
            backend=args.backend,
            dry_run=args.dry_run,
            alsa_device=args.alsa_device,
            edge_voice=args.edge_voice,
            tts_timeout_s=args.tts_timeout,
        )
        return row_identity({"timestamp": str(time.time()), "final_status": text}), text

    if args.target == "batch":
        return announce_batch(args, last_identity)

    if args.target == "previous":
        return announce_mango_from_csv(
            args,
            args.history_csv,
            "上一个芒果",
            "暂未读取到已检测芒果记录。",
            last_identity,
        )

    return announce_mango_from_csv(
        args,
        args.quality_csv,
        "当前芒果",
        "暂未读取到芒果检测结果。",
        last_identity,
    )


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

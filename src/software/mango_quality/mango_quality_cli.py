import argparse
import os
import signal
import sys
import time

try:
    from .fusion import (
        DEFAULT_OUTPUT_CSV,
        DEFAULT_OUTPUT_JSON,
        DEFAULT_SPECTRUM_CSV,
        DEFAULT_VISION_CSV,
        assess_mango_quality,
        read_latest_spectrum,
        read_latest_vision,
        write_assessment_csv,
        write_assessment_json,
    )
except ImportError:
    from fusion import (
        DEFAULT_OUTPUT_CSV,
        DEFAULT_OUTPUT_JSON,
        DEFAULT_SPECTRUM_CSV,
        DEFAULT_VISION_CSV,
        assess_mango_quality,
        read_latest_spectrum,
        read_latest_vision,
        write_assessment_csv,
        write_assessment_json,
    )


RUNNING = True


def handle_signal(_signum, _frame):
    global RUNNING
    RUNNING = False


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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fuse YOLO, RGB/HSV and AS7341 spectrum data for mango quality assessment."
    )
    parser.add_argument("--vision-csv", default=str(DEFAULT_VISION_CSV), help="YOLO RGB/HSV realtime CSV")
    parser.add_argument("--spectrum-csv", default=str(DEFAULT_SPECTRUM_CSV), help="AS7341 spectrum CSV")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV), help="Realtime assessment CSV")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON), help="Realtime assessment JSON")
    parser.add_argument("--interval", type=float, default=0.5, help="Watch interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run one assessment and exit")
    parser.add_argument("--no-json", action="store_true", help="Do not write JSON output")
    parser.add_argument("--parent-pid", type=int, default=0, help="Exit when this parent process is gone")
    return parser.parse_args()


def run_once(args):
    vision = read_latest_vision(args.vision_csv)
    spectrum = read_latest_spectrum(args.spectrum_csv)
    assessment = assess_mango_quality(vision, spectrum)
    write_assessment_csv(args.output_csv, assessment)
    if not args.no_json:
        write_assessment_json(args.output_json, assessment)
    return assessment


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    args = parse_args()

    if args.interval < 0:
        print("interval must be >= 0", file=sys.stderr)
        return 2

    while RUNNING and parent_is_alive(args.parent_pid):
        assessment = run_once(args)
        print(
            "mango_quality updated: maturity={} sugar={} rot={} final={}".format(
                assessment.maturity_label,
                assessment.sugar_label,
                assessment.rot_status,
                assessment.final_status,
            ),
            file=sys.stderr,
            flush=True,
        )
        if args.once:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

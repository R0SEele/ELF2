import argparse
import os
import signal
import sys
import time

try:
    from .auto_sorter import AutoSorter
except ImportError:
    from auto_sorter import AutoSorter

try:
    from .fusion import (
        DEFAULT_BATCH_CSV,
        DEFAULT_BATCH_JSON,
        DEFAULT_HISTORY_CSV,
        DEFAULT_OUTPUT_CSV,
        DEFAULT_OUTPUT_JSON,
        DEFAULT_OBJECT_CSV,
        DEFAULT_SPECTRUM_CSV,
        DEFAULT_VISION_CSV,
        BatchAccumulator,
        assess_mango_quality,
        read_latest_object,
        read_latest_spectrum,
        read_latest_vision,
        write_assessment_csv,
        write_assessment_history_csv,
        write_assessment_json,
        write_batch_summary_csv,
        write_batch_summary_json,
    )
except ImportError:
    from fusion import (
        DEFAULT_BATCH_CSV,
        DEFAULT_BATCH_JSON,
        DEFAULT_HISTORY_CSV,
        DEFAULT_OUTPUT_CSV,
        DEFAULT_OUTPUT_JSON,
        DEFAULT_OBJECT_CSV,
        DEFAULT_SPECTRUM_CSV,
        DEFAULT_VISION_CSV,
        BatchAccumulator,
        assess_mango_quality,
        read_latest_object,
        read_latest_spectrum,
        read_latest_vision,
        write_assessment_csv,
        write_assessment_history_csv,
        write_assessment_json,
        write_batch_summary_csv,
        write_batch_summary_json,
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
    parser.add_argument("--object-csv", default=str(DEFAULT_OBJECT_CSV), help="Completed mango object CSV")
    parser.add_argument("--spectrum-csv", default=str(DEFAULT_SPECTRUM_CSV), help="AS7341 spectrum CSV")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV), help="Realtime assessment CSV")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON), help="Realtime assessment JSON")
    parser.add_argument("--batch-csv", default=str(DEFAULT_BATCH_CSV), help="Batch summary CSV")
    parser.add_argument("--batch-json", default=str(DEFAULT_BATCH_JSON), help="Batch summary JSON")
    parser.add_argument("--history-csv", default=str(DEFAULT_HISTORY_CSV), help="Deduplicated mango quality history CSV")
    parser.add_argument("--auto-sort", action="store_true", default=True, help="Enable automatic sorter servo control")
    parser.add_argument("--no-auto-sort", dest="auto_sort", action="store_false", help="Disable automatic sorter servo control")
    parser.add_argument("--batch-id", default="", help="Optional batch identifier")
    parser.add_argument("--interval", type=float, default=0.5, help="Watch interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run one assessment and exit")
    parser.add_argument("--no-json", action="store_true", help="Do not write JSON output")
    parser.add_argument("--parent-pid", type=int, default=0, help="Exit when this parent process is gone")
    return parser.parse_args()


def run_once(args, batch=None, sorter=None):
    vision = read_latest_object(args.object_csv) or read_latest_vision(args.vision_csv)
    spectrum = read_latest_spectrum(args.spectrum_csv)
    assessment = assess_mango_quality(vision, spectrum)
    write_assessment_csv(args.output_csv, assessment)
    write_assessment_history_csv(args.history_csv, assessment)
    if not args.no_json:
        write_assessment_json(args.output_json, assessment)
    if batch is not None:
        batch.add(assessment)
        summary = batch.summary()
        write_batch_summary_csv(args.batch_csv, summary)
        if not args.no_json:
            write_batch_summary_json(args.batch_json, summary)
    if sorter is not None:
        sorter.sort_once(assessment)
    return assessment


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    args = parse_args()

    if args.interval < 0:
        print("interval must be >= 0", file=sys.stderr)
        return 2

    batch = BatchAccumulator(args.batch_id or None)
    sorter = AutoSorter() if args.auto_sort else None
    write_batch_summary_csv(args.batch_csv, batch.summary())
    if not args.no_json:
        write_batch_summary_json(args.batch_json, batch.summary())

    try:
        while RUNNING and parent_is_alive(args.parent_pid):
            assessment = run_once(args, batch, sorter)
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
    finally:
        if sorter is not None:
            sorter.close(drain=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

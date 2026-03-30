import argparse
import os
import time
from datetime import datetime, timezone

from camera import capture_image
from frame_quality import are_metrics_usable, get_frame_quality_metrics


def _utc_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_metrics(metrics):
    return (
        f"brightness={metrics['brightness']:.2f} "
        f"contrast_stddev={metrics['contrast_stddev']:.2f} "
        f"laplacian_var={metrics['laplacian_var']:.2f}"
    )


def run_check(continuous=False, interval_s=1.0, keep_images=False):
    """Capture frame(s) and print quality metrics with pass/fail status."""
    if interval_s <= 0:
        raise ValueError("interval_s must be > 0")

    count = 0
    while True:
        path = None
        try:
            path = capture_image()
            metrics = get_frame_quality_metrics(path)
            if metrics is None:
                print(f"[{_utc_ts()}] quality=UNKNOWN image={path} (failed to compute metrics)")
            else:
                usable = are_metrics_usable(metrics)
                print(
                    f"[{_utc_ts()}] quality={'PASS' if usable else 'FAIL'} "
                    f"image={path} {_format_metrics(metrics)}"
                )
            count += 1
        except Exception as err:
            print(f"[{_utc_ts()}] quality=ERROR error={err}")
        finally:
            if path and (not keep_images) and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as cleanup_err:
                    print(f"[{_utc_ts()}] cleanup warning for {path}: {cleanup_err}")

        if not continuous:
            break
        time.sleep(interval_s)

    return count


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Capture image(s) and evaluate frame quality (brightness/contrast/sharpness)."
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Keep capturing and evaluating frames until stopped (Ctrl+C).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between checks in continuous mode (default: 1.0).",
    )
    parser.add_argument(
        "--keep-images",
        action="store_true",
        help="Keep captured image files instead of deleting them after scoring.",
    )
    return parser


def main():
    parser = _build_arg_parser()
    args = parser.parse_args()

    try:
        run_check(
            continuous=args.continuous,
            interval_s=args.interval,
            keep_images=args.keep_images,
        )
    except KeyboardInterrupt:
        print("Stopped by user")


if __name__ == "__main__":
    main()

"""AGOS Rapid Burst Capture Tool
=============================
Captures a fast sequence of frames with PersistentCamera (e.g., water spray,
debris testing, dynamic flow changes) and optionally uploads to Cloudinary in parallel.

Usage:
    python burst_capture.py                      # Default: 10 images, 1s apart, label=raining
    python burst_capture.py --count 20 --delay 0.5
    python burst_capture.py --label debris_blocked --count 15
    python burst_capture.py --no-upload          # Local only
    python burst_capture.py --workers 4          # 4 parallel Cloudinary upload threads
"""

import argparse
import concurrent.futures
import datetime
import os
import sys
import time

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

from typing import NamedTuple

from camera import PersistentCamera
from frame_quality import get_frame_quality_metrics

load_dotenv()

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
)


class UploadResult(NamedTuple):
    success: bool
    filepath: str
    detail: str


class BurstUploadContext(NamedTuple):
    session_id: str
    label: str = "raining"
    cloud_folder: str | None = None


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def upload_to_cloudinary(filepath, session_id, label="raining", cloud_folder=None) -> UploadResult:
    """Upload a single image to Cloudinary."""
    if isinstance(session_id, BurstUploadContext):
        ctx = session_id
        session_id = ctx.session_id
        label = ctx.label
        cloud_folder = ctx.cloud_folder

    folder = cloud_folder or f"agos/training_{label}"
    tags = ["training", f"session_{session_id}", label]
    try:
        res = cloudinary.uploader.upload(
            filepath,
            folder=folder,
            tags=tags,
            context=f"session={session_id}|label={label}",
        )
        return UploadResult(success=True, filepath=filepath, detail=res.get("secure_url") or "")
    except Exception as e:
        return UploadResult(success=False, filepath=filepath, detail=str(e))


def upload_all_concurrent(filepaths, session_id, label="raining", cloud_folder=None, max_workers=4):
    """Upload list of image filepaths concurrently using ThreadPoolExecutor."""
    if not filepaths:
        return []

    context = (
        session_id
        if isinstance(session_id, BurstUploadContext)
        else BurstUploadContext(session_id=str(session_id), label=label, cloud_folder=cloud_folder)
    )

    workers = max(1, min(max_workers, len(filepaths)))
    print(f"\n[CLOUD] Uploading {len(filepaths)} images to Cloudinary ({workers} parallel workers)...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(upload_to_cloudinary, fp, context): fp
            for fp in filepaths
        }
        completed = 0
        for future in concurrent.futures.as_completed(future_map):
            completed += 1
            raw = future.result()
            result = raw if isinstance(raw, UploadResult) else UploadResult(*raw)
            results.append(result)
            status_tag = "[OK]" if result.success else "[FAIL]"
            filename = os.path.basename(result.filepath)
            if result.success:
                print(f"  [{completed}/{len(filepaths)}] {status_tag} Uploaded {filename}")
            else:
                print(f"  [{completed}/{len(filepaths)}] {status_tag} Failed {filename}: {result.detail}")

    success_count = sum(1 for res in results if getattr(res, "success", res[0]))
    print(f"[CLOUD] Uploads complete: {success_count}/{len(filepaths)} successful!")
    return results


def run_countdown(seconds: int = 3):
    """Visual countdown in terminal so user can prepare."""
    if seconds <= 0:
        return
    print()
    for s in range(seconds, 0, -1):
        print(f"  Starting in {s}...", end="\r", flush=True)
        time.sleep(1.0)
    print("  Starting NOW!       \n")


def main():
    parser = argparse.ArgumentParser(description="AGOS Rapid Burst Capture")
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=10,
        help="Number of images to capture (default: 10)",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between captures (default: 1.0)",
    )
    parser.add_argument(
        "-l",
        "--label",
        type=str,
        default="raining",
        help="Dataset label / scenario tag (default: raining)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=None,
        help="Local directory to store captures (default: training_{label})",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent Cloudinary upload workers (default: 4)",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=3,
        help="Countdown seconds before starting capture (default: 3, 0 to disable)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip uploading to Cloudinary (save locally only)",
    )
    args = parser.parse_args()

    label = args.label.strip().lower()
    output_dir = args.output_dir or f"training_{label}"
    cloud_folder = f"agos/training_{label}"

    _ensure_dir(output_dir)
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n========================================================")
    print(f"  AGOS Burst Capture — [{label.upper()}]")
    print("========================================================")
    print(f"  Target:     {args.count} images")
    print(f"  Interval:   1 image every {args.delay} seconds")
    print(f"  Label/Tag:  {label}")
    print(f"  Folder:     ./{output_dir}/")
    print(f"  Cloud:      {'Disabled' if args.no_upload else f'{cloud_folder} ({args.workers} workers)'}")
    print("========================================================\n")

    input("Press ENTER to start the burst sequence...")
    run_countdown(args.countdown)

    print("[CAMERA] Initializing camera...")
    captured_files = []
    metrics_list = []

    with PersistentCamera() as cam:
        print("[START] Sequence started!\n")
        for i in range(1, args.count + 1):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"burst_{label}_{session_id}_{i:03d}_{timestamp}.jpg"
            filepath = os.path.join(output_dir, filename)

            try:
                cam.capture(filepath)
                metrics = get_frame_quality_metrics(filepath)
                if metrics:
                    metrics_list.append(metrics)
                    bright = metrics.get("brightness", 0.0)
                    sharp = metrics.get("laplacian_var", 0.0)
                    print(f"  [{i}/{args.count}] Captured: {filename} (brightness={bright:.1f}, sharpness={sharp:.1f})")
                else:
                    print(f"  [{i}/{args.count}] Captured: {filename}")
                captured_files.append(filepath)
            except Exception as e:
                print(f"  [{i}/{args.count}] [ERROR] Capture failed: {e}")

            if i < args.count:
                time.sleep(args.delay)

    print(f"\n[DONE] Captured {len(captured_files)}/{args.count} images in ./{output_dir}/")

    # Quality summary
    if metrics_list:
        avg_bright = sum(m["brightness"] for m in metrics_list) / len(metrics_list)
        avg_sharp = sum(m["laplacian_var"] for m in metrics_list) / len(metrics_list)
        avg_contrast = sum(m["contrast_stddev"] for m in metrics_list) / len(metrics_list)
        print(f"\n--- Quality Stats (avg across {len(metrics_list)} frames) ---")
        print(f"  Brightness: {avg_bright:.1f} | Sharpness (Laplacian): {avg_sharp:.1f} | Contrast: {avg_contrast:.1f}")

    # Upload phase
    if not args.no_upload and captured_files:
        upload_all_concurrent(
            captured_files,
            session_id=session_id,
            label=label,
            cloud_folder=cloud_folder,
            max_workers=args.workers,
        )

    print(f"\n[SUCCESS] Check ./{output_dir}/ or your Cloudinary dashboard ({cloud_folder}).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Burst capture interrupted by user. Exiting.")
        sys.exit(0)


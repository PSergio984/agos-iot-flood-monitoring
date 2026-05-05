"""
This script allows you to capture a rapid burst of images (e.g., 10 frames over 10 seconds)
Usage:
    python burst_capture.py             # Default: 10 images, 1 second apart
    python burst_capture.py --count 20  # Capture 20 images
    python burst_capture.py --delay 0.5 # Capture every 0.5 seconds
"""

import argparse
import datetime
import os
import time

from dotenv import load_dotenv

load_dotenv()

import cloudinary
import cloudinary.uploader

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

from camera import PersistentCamera

LOCAL_BACKUP_DIR = "training_normal2"
CLOUD_FOLDER = "agos/training_normal2"


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def upload_to_cloudinary(filepath, session_id):
    """Upload a single image to Cloudinary."""
    tags = ["training", f"session_{session_id}", "raining"]
    try:
        cloudinary.uploader.upload(
            filepath,
            folder=CLOUD_FOLDER,
            tags=tags,
            context=f"session={session_id}",
        )
        return True
    except Exception as e:
        print(f"    [FAIL] Upload error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Defense Burst Capture")
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
        "--no-upload", action="store_true", help="Skip uploading to Cloudinary"
    )
    args = parser.parse_args()

    _ensure_dir(LOCAL_BACKUP_DIR)
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n========================================================")
    print("  AGOS Defense Burst Capture (Water Spray Test)")
    print("========================================================")
    print(f"  Target: {args.count} images")
    print(f"  Speed:  1 image every {args.delay} seconds")
    print(f"  Folder: ./{LOCAL_BACKUP_DIR}/")
    print(f"  Upload: {'Disabled' if args.no_upload else 'Enabled (after capture)'}")
    print("========================================================\n")

    input("Press ENTER to START the burst capture (then start spraying!)...")

    print("\n[CAMERA] Warming up camera...")
    captured_files = []

    with PersistentCamera() as cam:
        print("\n[START] Burst capture sequence initiated!\n")

        for i in range(1, args.count + 1):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"burst_{session_id}_{i:03d}_{timestamp}.jpg"
            filepath = os.path.join(LOCAL_BACKUP_DIR, filename)

            try:
                # Capture frame
                cam.capture(filepath)
                print(f"  [{i}/{args.count}] Captured: {filename}")
                captured_files.append(filepath)
            except Exception as e:
                print(f"  [{i}/{args.count}] [ERROR] Capture failed: {e}")

            # Wait before next capture (skip delay on the last image)
            if i < args.count:
                time.sleep(args.delay)

    print("\n[DONE] Burst capture complete!")

    # Upload phase
    if not args.no_upload and captured_files:
        print(f"\n[CLOUD] Uploading {len(captured_files)} images to Cloudinary...")
        for i, filepath in enumerate(captured_files, 1):
            print(
                f"  [{i}/{len(captured_files)}] Uploading {os.path.basename(filepath)}..."
            )
            upload_to_cloudinary(filepath, session_id)
        print("[CLOUD] Uploads complete!")

    print("\n[SUCCESS] Check your training_captures/ folder or Cloudinary dashboard.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Burst capture interrupted by user. Exiting.")
        sys.exit(0)

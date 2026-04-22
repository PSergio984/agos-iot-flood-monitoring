"""
AGOS Training Data Capture Tool
================================
Interactive camera capture → Cloudinary upload workflow for building
YOLOv8 training datasets on a Raspberry Pi Zero W (headless).

Uses the project's PersistentCamera (Picamera2) — keeps the camera
open between captures so the 2-second AEC/AWB warm-up is paid only
once at startup.  Images are captured at maximum quality.

Usage:
    python training_capture.py                  # Capture and upload
    python training_capture.py --no-upload      # Local-only (skip Cloudinary)

Interactive Commands (while running):
    ENTER                — Capture current frame and upload to Cloudinary
    Ctrl+C               — Quit and show session summary

Images are uploaded to:
    Cloudinary folder:  agos/training_capture/
    Tags:               [training, session_{session_id}]

A local backup is also saved to:
    ./training_captures/

Requires (already in project):
    cloudinary, python-dotenv, Picamera2 (on RPi)
"""

import argparse
import datetime
import os
import shutil
import sys

from dotenv import load_dotenv

load_dotenv()

# ── Cloudinary setup (reuse project .env) ────────────────────────────────────
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

# ── Import project camera (Picamera2 / mock) ────────────────────────────────
from camera import PersistentCamera
from frame_quality import get_frame_quality_metrics, are_metrics_usable

# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_FOLDER = "agos/training_capture"
LOCAL_BACKUP_DIR = "training_captures"


# ── Utilities ────────────────────────────────────────────────────────────────

def _timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _session_id():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def upload_to_cloudinary(image_path, folder, session):
    """Upload a single image to Cloudinary with training metadata."""
    tags = ["training", f"session_{session}"]

    try:
        result = cloudinary.uploader.upload(
            image_path,
            folder=folder,
            tags=tags,
            context=f"session={session}",
        )
        return result
    except Exception as e:
        print(f"  [FAIL] Cloudinary upload error: {e}")
        return None


def save_local_backup(captured_path):
    """Copy captured frame to the local backup directory."""
    _ensure_dir(LOCAL_BACKUP_DIR)
    filename = f"capture_{_timestamp()}.jpg"
    filepath = os.path.join(LOCAL_BACKUP_DIR, filename)
    shutil.copy2(captured_path, filepath)
    return filepath


def print_session_summary(session, total, folder):
    print()
    print("=" * 56)
    print("  SESSION SUMMARY")
    print("=" * 56)
    print(f"  Session ID:   {session}")
    print(f"  Total images: {total}")
    print(f"  Cloud folder: {folder}/")
    print(f"  Local backup: ./{LOCAL_BACKUP_DIR}/")
    print("=" * 56)
    if total > 0:
        print(f"  Tip: find this session on Cloudinary → tag: session_{session}")
    print("  Done.")
    print()


# ── Main capture loop ────────────────────────────────────────────────────────

def run(folder, do_upload):
    session = _session_id()
    capture_count = 0

    print()
    print("=" * 56)
    print("  AGOS Training Data Capture")
    print("=" * 56)
    print(f"  Camera:       Picamera2 (PersistentCamera)")
    print(f"  Cloud folder: {folder}/")
    print(f"  Upload:       {'enabled' if do_upload else 'DISABLED (local only)'}")
    print(f"  Session:      {session}")
    print(f"  Local backup: ./{LOCAL_BACKUP_DIR}/")
    print()
    print("  Commands:")
    print("    ENTER          Capture and upload")
    print("    Ctrl+C         Quit")
    print("=" * 56)
    print()

    print("[CAMERA] Opening camera (one-time warm-up) ...")
    cam = PersistentCamera()
    cam.start()
    print("[CAMERA] Ready.")
    print()

    try:
        while True:
            prompt = "  ENTER=capture: "
            try:
                input(prompt)
            except EOFError:
                break

            # ── Capture ──
            capture_count += 1

            print(f"  [#{capture_count}] Capturing ...")
            cap_path = cam.capture()

            if cap_path is None or not os.path.exists(cap_path):
                print(f"  [FAIL] Capture returned no image.")
                capture_count -= 1
                continue

            # Save local backup
            local_path = save_local_backup(cap_path)
            print(f"  [OK]   Saved locally: {local_path}")

            # Show quality metrics so user knows if image is good for training
            metrics = get_frame_quality_metrics(local_path)
            if metrics:
                usable = are_metrics_usable(metrics)
                status = "\u2713 GOOD" if usable else "\u2717 LOW QUALITY"
                print(f"  [QA]   {status}  brightness={metrics['brightness']:.1f}  "
                      f"contrast={metrics['contrast_stddev']:.1f}  "
                      f"sharpness={metrics['laplacian_var']:.1f}")
                if not usable:
                    print(f"  [QA]   \u26a0 Image may be too dark/blurry — consider retaking")

            # Upload to Cloudinary
            if do_upload:
                print(f"  [...]  Uploading to {folder}/ ...")
                result = upload_to_cloudinary(local_path, folder, session)
                if result:
                    url = result.get("secure_url", "?")
                    public_id = result.get("public_id", "?")
                    print(f"  [OK]   {public_id}")
                    print(f"         {url}")
                else:
                    print(f"  [FAIL] Upload failed. Local backup kept.")
            else:
                print(f"  [SKIP] Upload disabled (--no-upload)")

            # Clean up the temp capture file (backup already saved)
            try:
                if cap_path != local_path and os.path.exists(cap_path):
                    os.remove(cap_path)
            except Exception:
                pass

            print()

    except KeyboardInterrupt:
        pass
    finally:
        cam.stop()

    print_session_summary(session, capture_count, folder)


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AGOS Training Data Capture — interactive photo capture and Cloudinary upload for YOLOv8 training",
    )
    parser.add_argument(
        "--folder", type=str, default=DEFAULT_FOLDER,
        help=f"Cloudinary folder (default: {DEFAULT_FOLDER})",
    )
    parser.add_argument(
        "--no-upload", action="store_true",
        help="Skip Cloudinary upload — save locally only",
    )
    args = parser.parse_args()

    # Validate Cloudinary credentials (unless --no-upload)
    if not args.no_upload and not all([CLOUD_NAME, API_KEY, API_SECRET]):
        print("[ERROR] Cloudinary credentials not found in .env")
        print("   Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET")
        print("   Or use --no-upload for local-only mode.")
        sys.exit(1)

    run(args.folder, do_upload=not args.no_upload)


if __name__ == "__main__":
    main()

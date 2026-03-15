import os
from dotenv import load_dotenv
load_dotenv()

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
SERVER_URL = os.getenv("SERVER_URL")
IOT_API_KEY = os.getenv("IOT_API_KEY", "")
SENSOR_DEVICE_ID = int(os.getenv("SENSOR_DEVICE_ID", "1"))

# ── Feature toggles ─────────────────────────────────────────────────────────
ENABLE_CLOUDINARY_UPLOAD = os.getenv("ENABLE_CLOUDINARY_UPLOAD", "true").lower() == "true"
ENABLE_WEBSOCKET_SEND = os.getenv("ENABLE_WEBSOCKET_SEND", "true").lower() == "true"
USE_TEST_IMAGES = os.getenv("USE_TEST_IMAGES", "false").lower() == "true"
TEST_IMAGES_DIR = os.getenv("TEST_IMAGES_DIR", "test_images")

# ── Timing / throughput ──────────────────────────────────────────────────────
# How often each subsystem runs.  Adjust these (or the matching env vars) to
# trade bandwidth/storage against data freshness.
#
#   SENSOR_INTERVAL  1.0  → 1 reading/second
#   CAMERA_INTERVAL  0.5  → 2 fps
#
# The camera loop keeps picamera2 open between captures so the 2-second
# AEC/AWB warm-up is paid only once at startup.
SENSOR_INTERVAL = float(os.getenv("SENSOR_INTERVAL", "1.0"))   # seconds
CAMERA_INTERVAL = float(os.getenv("CAMERA_INTERVAL", "0.5"))   # seconds  (2 fps)

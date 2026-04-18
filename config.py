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
WS_SEND_METADATA_FIRST = os.getenv("WS_SEND_METADATA_FIRST", "false").lower() == "true"
USE_TEST_IMAGES = os.getenv("USE_TEST_IMAGES", "false").lower() == "true"
TEST_IMAGES_DIR = os.getenv("TEST_IMAGES_DIR", "test_images")
SENSOR_POST_ENABLED = os.getenv("SENSOR_POST_ENABLED", "true").lower() == "true"

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

# ── Sensor GPIO mapping (BCM numbering) ───────────────────────────────────
SENSOR_TRIG_PIN = int(os.getenv("SENSOR_TRIG_PIN", "23"))
SENSOR_ECHO_PIN = int(os.getenv("SENSOR_ECHO_PIN", "24"))

# ── Local warning LED (optional) ────────────────────────────────────────────
LED_WARNING_ENABLED = os.getenv("LED_WARNING_ENABLED", "false").lower() == "true"
LED_WARNING_PIN = int(os.getenv("LED_WARNING_PIN", "18"))
LED_WARNING_THRESHOLD_CM = float(os.getenv("LED_WARNING_THRESHOLD_CM", "10.0"))
LED_CLEAR_ENABLED = os.getenv("LED_CLEAR_ENABLED", "false").lower() == "true"
LED_CLEAR_PIN = int(os.getenv("LED_CLEAR_PIN", "15"))

# ── Sensor filtering (outlier rejection + smoothing) ───────────────────────
# Recommended baseline for ultrasonic water-level telemetry:
# 1) Physical range gate
# 2) Robust outlier check using MAD-based modified Z-score
# 3) Rolling average of accepted readings
SENSOR_FILTER_ENABLED = os.getenv("SENSOR_FILTER_ENABLED", "true").lower() == "true"
SENSOR_FILTER_WINDOW_SIZE = int(os.getenv("SENSOR_FILTER_WINDOW_SIZE", "7"))
SENSOR_FILTER_MIN_VALID_SAMPLES = int(os.getenv("SENSOR_FILTER_MIN_VALID_SAMPLES", "3"))
SENSOR_FILTER_MIN_CM = float(os.getenv("SENSOR_FILTER_MIN_CM", "0.0"))
SENSOR_FILTER_MAX_CM = float(os.getenv("SENSOR_FILTER_MAX_CM", "400.0"))
SENSOR_FILTER_MODZ_THRESHOLD = float(os.getenv("SENSOR_FILTER_MODZ_THRESHOLD", "3.5"))
SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM = float(os.getenv("SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM", "1.0"))
SENSOR_FILTER_REBASELINE_OUTLIER_STREAK = int(os.getenv("SENSOR_FILTER_REBASELINE_OUTLIER_STREAK", "5"))
SENSOR_FILTER_REBASELINE_SPREAD_MAX_CM = float(os.getenv("SENSOR_FILTER_REBASELINE_SPREAD_MAX_CM", "8.0"))

# ── Camera frame quality gate (lightweight OpenCV checks) ──────────────────
FRAME_QUALITY_CHECK_ENABLED = os.getenv("FRAME_QUALITY_CHECK_ENABLED", "true").lower() == "true"
FRAME_QUALITY_MIN_BRIGHTNESS = float(os.getenv("FRAME_QUALITY_MIN_BRIGHTNESS", "25.0"))
FRAME_QUALITY_MAX_BRIGHTNESS = float(os.getenv("FRAME_QUALITY_MAX_BRIGHTNESS", "230.0"))
FRAME_QUALITY_MIN_CONTRAST_STDDEV = float(os.getenv("FRAME_QUALITY_MIN_CONTRAST_STDDEV", "10.0"))
FRAME_QUALITY_MIN_LAPLACIAN_VAR = float(os.getenv("FRAME_QUALITY_MIN_LAPLACIAN_VAR", "80.0"))
FRAME_QUALITY_RESIZE_WIDTH = int(os.getenv("FRAME_QUALITY_RESIZE_WIDTH", "320"))

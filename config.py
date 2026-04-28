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
CAMERA_SEND_PRECAPTURE_STATUS_IMAGE = os.getenv("CAMERA_SEND_PRECAPTURE_STATUS_IMAGE", "false").lower() == "true"
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

# ── Sensor sampling and timing ────────────────────────────────────────────
SENSOR_TIMEOUT_S = float(os.getenv("SENSOR_TIMEOUT_S", "0.3"))
SENSOR_BURST_SAMPLES = max(1, int(os.getenv("SENSOR_BURST_SAMPLES", "7")))
SENSOR_BURST_MIN_VALID = max(1, int(os.getenv("SENSOR_BURST_MIN_VALID", "3")))
SENSOR_BURST_SAMPLE_DELAY_S = max(
    0.06, float(os.getenv("SENSOR_BURST_SAMPLE_DELAY_S", "0.06"))
)
_temp_c_raw = os.getenv("SENSOR_TEMPERATURE_C", "").strip()
try:
    SENSOR_TEMPERATURE_C = float(_temp_c_raw) if _temp_c_raw else None
except ValueError:
    SENSOR_TEMPERATURE_C = None

# ── Risk Indicator LEDs (unified, state-based naming) ──────────────────────
# Use -1 to disable a specific state LED.
# Backward compatibility: falls back to legacy color-based env vars when
# the new names are not present.
RISK_LED_CRITICAL_PIN = int(
    os.getenv("RISK_LED_CRITICAL_PIN", os.getenv("RISK_LED_RED_PIN", "14"))
)
RISK_LED_WARNING_PIN = int(
    os.getenv("RISK_LED_WARNING_PIN", os.getenv("RISK_LED_YELLOW_PIN", "18"))
)
RISK_LED_SAFE_PIN = int(
    os.getenv("RISK_LED_SAFE_PIN", os.getenv("RISK_LED_GREEN_PIN", "15"))
)

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
# Tuned for YOLOv8 detection accuracy on OV5647 output.
FRAME_QUALITY_CHECK_ENABLED = os.getenv("FRAME_QUALITY_CHECK_ENABLED", "true").lower() == "true"
FRAME_QUALITY_MIN_BRIGHTNESS = float(os.getenv("FRAME_QUALITY_MIN_BRIGHTNESS", "45.0"))
FRAME_QUALITY_MAX_BRIGHTNESS = float(os.getenv("FRAME_QUALITY_MAX_BRIGHTNESS", "210.0"))
FRAME_QUALITY_MIN_CONTRAST_STDDEV = float(os.getenv("FRAME_QUALITY_MIN_CONTRAST_STDDEV", "25.0"))
FRAME_QUALITY_MIN_LAPLACIAN_VAR = float(os.getenv("FRAME_QUALITY_MIN_LAPLACIAN_VAR", "100.0"))
FRAME_QUALITY_RESIZE_WIDTH = int(os.getenv("FRAME_QUALITY_RESIZE_WIDTH", "320"))

# Fusion & Decision Engine API (leave blank to use water-level fallback only)
RISK_SCORE_API_URL = os.getenv("RISK_SCORE_API_URL", "")
RISK_SCORE_POLL_INTERVAL = float(os.getenv("RISK_SCORE_POLL_INTERVAL", "10.0"))

# Water-level fallback thresholds (used when API is unreachable)
# Distance in cm — lower distance = higher water level = more danger
RISK_FALLBACK_SAFE_ABOVE_CM = float(os.getenv("RISK_FALLBACK_SAFE_ABOVE_CM", "50.0"))
RISK_FALLBACK_WARNING_ABOVE_CM = float(os.getenv("RISK_FALLBACK_WARNING_ABOVE_CM", "30.0"))
# Below WARNING threshold = Danger (red)

# ── Environment Sensing (Auto Night Vision) ────────────────────────────────
ENV_SENSE_DARKNESS_THRESHOLD = float(os.getenv("ENV_SENSE_DARKNESS_THRESHOLD", "40.0"))
ENV_SENSE_OBSCURED_CONTRAST_MAX = float(os.getenv("ENV_SENSE_OBSCURED_CONTRAST_MAX", "10.0"))
ENV_SENSE_OBSCURED_LAPLACIAN_MAX = float(os.getenv("ENV_SENSE_OBSCURED_LAPLACIAN_MAX", "50.0"))

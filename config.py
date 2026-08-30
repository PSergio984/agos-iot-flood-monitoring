import os
import urllib.parse
from dotenv import load_dotenv
load_dotenv()


def get_env_var(key: str | list[str] | tuple[str, ...], default: str = "", cast_type=None):
    """Retrieve an environment variable safely, falling back to default if unset, empty, or whitespace."""
    keys = [key] if isinstance(key, str) else key
    val = ""
    for k in keys:
        raw = os.getenv(k)
        if raw is not None and raw.strip() != "":
            val = raw.strip()
            break
    if not val:
        val = default
    if cast_type is bool:
        return str(val).strip().lower() in ("true", "1", "yes")
    if cast_type is not None:
        try:
            return cast_type(val)
        except (ValueError, TypeError):
            return cast_type(default) if str(default).strip() != "" else None
    return val


# ── Server & Device Identity ───────────────────────────────────────────────
BACKEND_BASE_URL = get_env_var(["BACKEND_BASE_URL", "SERVER_BASE_URL", "API_BASE_URL"], "").rstrip("/")
LOCATION_ID = get_env_var("LOCATION_ID", "1", int)
CAMERA_DEVICE_ID = get_env_var("CAMERA_DEVICE_ID", "1", int)
SENSOR_DEVICE_ID = get_env_var("SENSOR_DEVICE_ID", "1", int)
IOT_API_KEY = get_env_var("IOT_API_KEY", "")


def _derive_websocket_url() -> str:
    explicit = get_env_var("WEBSOCKET_SERVER_URL", "")
    if explicit:
        return explicit
    if not BACKEND_BASE_URL:
        return ""
    parsed = urllib.parse.urlparse(BACKEND_BASE_URL)
    ws_scheme = "wss" if parsed.scheme in ("https", "wss") else "ws"
    netloc = parsed.netloc or parsed.path
    return f"{ws_scheme}://{netloc}/ws/rpi?camera_device_id={CAMERA_DEVICE_ID}&location_id={LOCATION_ID}"


SERVER_URL = get_env_var(
    "SERVER_URL",
    f"{BACKEND_BASE_URL}/api/v1/sensor-readings/record" if BACKEND_BASE_URL else "http://localhost:8000/api/v1/sensor-readings/record",
)
WEBSOCKET_SERVER_URL = _derive_websocket_url()

CLOUD_NAME = get_env_var("CLOUDINARY_CLOUD_NAME", "")
API_KEY = get_env_var("CLOUDINARY_API_KEY", "")
API_SECRET = get_env_var("CLOUDINARY_API_SECRET", "")
CLOUDINARY_URL = get_env_var("CLOUDINARY_URL", "")


# ── Feature toggles ─────────────────────────────────────────────────────────
ENABLE_CLOUDINARY_UPLOAD = get_env_var("ENABLE_CLOUDINARY_UPLOAD", "true", bool)
ENABLE_WEBSOCKET_SEND = get_env_var("ENABLE_WEBSOCKET_SEND", "true", bool)
WS_SEND_METADATA_FIRST = get_env_var("WS_SEND_METADATA_FIRST", "false", bool)
WS_PING_INTERVAL = get_env_var("WS_PING_INTERVAL", "15", int)
WS_PING_TIMEOUT = get_env_var("WS_PING_TIMEOUT", "10", int)
WS_MAX_CONNECTION_AGE_S = get_env_var("WS_MAX_CONNECTION_AGE_S", "0.0", float)
CAMERA_SEND_PRECAPTURE_STATUS_IMAGE = get_env_var("CAMERA_SEND_PRECAPTURE_STATUS_IMAGE", "false", bool)
USE_TEST_IMAGES = get_env_var("USE_TEST_IMAGES", "false", bool)
TEST_IMAGES_DIR = get_env_var("TEST_IMAGES_DIR", "test_images")
USE_TRAINING_CAPTURES = get_env_var("USE_TRAINING_CAPTURES", "false", bool)
TRAINING_CAPTURES_DIR = get_env_var("TRAINING_CAPTURES_DIR", "training_captures")
USE_TRAINING_RAINING = get_env_var("USE_TRAINING_RAINING", "false", bool)
TRAINING_RAINING_DIR = get_env_var("TRAINING_RAINING_DIR", "training_raining")
SENSOR_POST_ENABLED = get_env_var("SENSOR_POST_ENABLED", "true", bool)

# ── Timing / throughput ──────────────────────────────────────────────────────
# How often each subsystem runs.  Adjust these (or the matching env vars) to
# trade bandwidth/storage against data freshness.
#
#   SENSOR_INTERVAL  1.0  → 1 reading/second
#   CAMERA_INTERVAL  0.5  → 2 fps
#
# The camera loop keeps picamera2 open between captures so the 2-second
# AEC/AWB warm-up is paid only once at startup.
SENSOR_INTERVAL = get_env_var("SENSOR_INTERVAL", "1.0", float)   # seconds
CAMERA_INTERVAL = get_env_var("CAMERA_INTERVAL", "1.0", float)   # seconds  (1 fps)

# ── Sensor GPIO mapping (BCM numbering) ───────────────────────────────────
SENSOR_TRIG_PIN = get_env_var("SENSOR_TRIG_PIN", "23", int)
SENSOR_ECHO_PIN = get_env_var("SENSOR_ECHO_PIN", "24", int)

# ── Sensor sampling and timing ────────────────────────────────────────────
SENSOR_TIMEOUT_S = get_env_var("SENSOR_TIMEOUT_S", "0.3", float)
SENSOR_BURST_SAMPLES = max(1, get_env_var("SENSOR_BURST_SAMPLES", "7", int))
SENSOR_BURST_MIN_VALID = max(1, get_env_var("SENSOR_BURST_MIN_VALID", "3", int))
SENSOR_BURST_SAMPLE_DELAY_S = max(
    0.06, get_env_var("SENSOR_BURST_SAMPLE_DELAY_S", "0.06", float)
)
SENSOR_TEMPERATURE_C = get_env_var("SENSOR_TEMPERATURE_C", "", float)

# ── Risk Indicator LEDs (unified, state-based naming) ──────────────────────
# Use -1 to disable a specific state LED.
# Backward compatibility: falls back to legacy color-based env vars when
# the new names are not present.
RISK_LED_CRITICAL_PIN = get_env_var(["RISK_LED_CRITICAL_PIN", "RISK_LED_RED_PIN"], "14", int)
RISK_LED_WARNING_PIN = get_env_var(["RISK_LED_WARNING_PIN", "RISK_LED_YELLOW_PIN"], "18", int)
RISK_LED_SAFE_PIN = get_env_var(["RISK_LED_SAFE_PIN", "RISK_LED_GREEN_PIN"], "15", int)

# ── Sensor filtering (outlier rejection + smoothing) ───────────────────────
# Recommended baseline for ultrasonic water-level telemetry:
# 1) Physical range gate
# 2) Robust outlier check using MAD-based modified Z-score
# 3) Rolling average of accepted readings
SENSOR_FILTER_ENABLED = get_env_var("SENSOR_FILTER_ENABLED", "true", bool)
SENSOR_FILTER_WINDOW_SIZE = get_env_var("SENSOR_FILTER_WINDOW_SIZE", "7", int)
SENSOR_FILTER_MIN_VALID_SAMPLES = get_env_var("SENSOR_FILTER_MIN_VALID_SAMPLES", "3", int)
SENSOR_FILTER_MIN_CM = get_env_var("SENSOR_FILTER_MIN_CM", "0.0", float)
SENSOR_FILTER_MAX_CM = get_env_var("SENSOR_FILTER_MAX_CM", "400.0", float)
SENSOR_FILTER_MODZ_THRESHOLD = get_env_var("SENSOR_FILTER_MODZ_THRESHOLD", "3.5", float)
SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM = get_env_var("SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM", "1.0", float)
SENSOR_FILTER_REBASELINE_OUTLIER_STREAK = get_env_var("SENSOR_FILTER_REBASELINE_OUTLIER_STREAK", "5", int)
SENSOR_FILTER_REBASELINE_SPREAD_MAX_CM = get_env_var("SENSOR_FILTER_REBASELINE_SPREAD_MAX_CM", "8.0", float)

# ── Camera frame quality gate (lightweight OpenCV checks) ──────────────────
# Tuned for YOLOv8 detection accuracy on OV5647 output.
FRAME_QUALITY_CHECK_ENABLED = get_env_var("FRAME_QUALITY_CHECK_ENABLED", "true", bool)
FRAME_QUALITY_MIN_BRIGHTNESS = get_env_var("FRAME_QUALITY_MIN_BRIGHTNESS", "45.0", float)
FRAME_QUALITY_MAX_BRIGHTNESS = get_env_var("FRAME_QUALITY_MAX_BRIGHTNESS", "210.0", float)
FRAME_QUALITY_MIN_CONTRAST_STDDEV = get_env_var("FRAME_QUALITY_MIN_CONTRAST_STDDEV", "25.0", float)
FRAME_QUALITY_MIN_LAPLACIAN_VAR = get_env_var("FRAME_QUALITY_MIN_LAPLACIAN_VAR", "100.0", float)
FRAME_QUALITY_RESIZE_WIDTH = get_env_var("FRAME_QUALITY_RESIZE_WIDTH", "320", int)

# Fusion & Decision Engine API (auto-derived from BACKEND_BASE_URL if set)
RISK_SCORE_API_URL = get_env_var(
    "RISK_SCORE_API_URL",
    f"{BACKEND_BASE_URL}/api/v1/iot/risk-score?location_id={LOCATION_ID}" if BACKEND_BASE_URL else "",
)
RISK_SCORE_POLL_INTERVAL = get_env_var("RISK_SCORE_POLL_INTERVAL", "10.0", float)

# Water-level fallback thresholds (used when API is unreachable)
# Distance in cm — lower distance = higher water level = more danger
RISK_FALLBACK_SAFE_ABOVE_CM = get_env_var("RISK_FALLBACK_SAFE_ABOVE_CM", "50.0", float)
RISK_FALLBACK_WARNING_ABOVE_CM = get_env_var("RISK_FALLBACK_WARNING_ABOVE_CM", "30.0", float)
# Below WARNING threshold = Danger (red)

# ── Environment Sensing (Auto Night Vision) ────────────────────────────────
ENV_SENSE_DARKNESS_THRESHOLD = get_env_var("ENV_SENSE_DARKNESS_THRESHOLD", "40.0", float)
ENV_SENSE_OBSCURED_CONTRAST_MAX = get_env_var("ENV_SENSE_OBSCURED_CONTRAST_MAX", "10.0", float)
ENV_SENSE_OBSCURED_LAPLACIAN_MAX = get_env_var("ENV_SENSE_OBSCURED_LAPLACIAN_MAX", "50.0", float)

# ── Night Camera Sleep & Twilight Schedule ─────────────────────────────────
CAMERA_NIGHT_SLEEP_ENABLED = get_env_var(["CAMERA_NIGHT_SLEEP_ENABLED", "NIGHT_CAMERA_SLEEP_ENABLED"], "true", bool)
CAMERA_TWILIGHT_START_HOUR = get_env_var("CAMERA_TWILIGHT_START_HOUR", "18", int)
CAMERA_NIGHT_SLEEP_START_HOUR = get_env_var(["CAMERA_NIGHT_SLEEP_START_HOUR", "NIGHT_CAMERA_START_HOUR"], "19", int)
CAMERA_NIGHT_SLEEP_END_HOUR = get_env_var(["CAMERA_NIGHT_SLEEP_END_HOUR", "NIGHT_CAMERA_END_HOUR"], "6", int)



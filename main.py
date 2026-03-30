import requests
import time
import os
import json
import logging
import signal
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from pathlib import Path

from config import (
    SENSOR_DEVICE_ID,
    SENSOR_INTERVAL,
    CAMERA_INTERVAL,
    IOT_API_KEY,
    ENABLE_CLOUDINARY_UPLOAD,
    ENABLE_WEBSOCKET_SEND,
    WS_SEND_METADATA_FIRST,
    USE_TEST_IMAGES,
    TEST_IMAGES_DIR,
    SENSOR_POST_ENABLED,
    SENSOR_FILTER_ENABLED,
    SENSOR_FILTER_WINDOW_SIZE,
    SENSOR_FILTER_MIN_VALID_SAMPLES,
    SENSOR_FILTER_MIN_CM,
    SENSOR_FILTER_MAX_CM,
    SENSOR_FILTER_MODZ_THRESHOLD,
    SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM,
    SENSOR_FILTER_REBASELINE_OUTLIER_STREAK,
    SENSOR_FILTER_REBASELINE_SPREAD_MAX_CM,
)
from camera import PersistentCamera
from frame_quality import get_frame_quality_metrics, is_frame_usable
from sensor import get_water_level, update_warning_led
from uploader import upload_image
from water_level_filter import WaterLevelFilter

try:
    import websocket as _websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server configuration
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000/api/v1/sensor-readings/record")
WEBSOCKET_SERVER_URL = os.environ.get("WEBSOCKET_SERVER_URL", "")

_TEST_IMAGE_INDEX = 0


def _load_test_images() -> list[Path]:
    image_dir = Path(TEST_IMAGES_DIR)
    if not image_dir.exists() or not image_dir.is_dir():
        return []
    allowed = {".jpg", ".jpeg", ".png"}
    return sorted(
        [p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed]
    )


_TEST_IMAGES = _load_test_images()


def _next_test_image_path() -> Path | None:
    global _TEST_IMAGE_INDEX
    if not _TEST_IMAGES:
        return None
    image_path = _TEST_IMAGES[_TEST_IMAGE_INDEX % len(_TEST_IMAGES)]
    _TEST_IMAGE_INDEX += 1
    return image_path


def _safe_ws_url(url):
    """Return scheme+host+port only — strips userinfo, path, query, and fragment."""
    try:
        if not isinstance(url, str):
            return "<invalid url>"
        p = urlparse(url)
        # netloc may contain 'user:pass@host:port'; keep only 'host:port'
        host_port = p.hostname or ""
        if p.port:
            host_port = f"{host_port}:{p.port}"
        return urlunparse((p.scheme, host_port, "", "", "", ""))
    except Exception:
        return "<invalid url>"


def _format_frame_metrics(metrics):
    if not metrics:
        return "metrics=unavailable"
    return (
        f"brightness={metrics['brightness']:.2f} "
        f"contrast_stddev={metrics['contrast_stddev']:.2f} "
        f"laplacian_var={metrics['laplacian_var']:.2f}"
    )


def send_image_websocket(image_path, cloudinary_url=None):
    """Send captured image to WebSocket server.

    Protocol:
      1. Text frame — JSON metadata (device ID, timestamp, file size, cloudinary URL).
      2. Binary frame — raw JPEG bytes.

    The server can use the metadata to associate the binary blob with the
    correct device/reading before the binary frame arrives.
    """
    if not WEBSOCKET_AVAILABLE:
        logger.warning("[WS] websocket-client not installed — skipping WebSocket send")
        return False
    if not WEBSOCKET_SERVER_URL:
        logger.debug("[WS] WEBSOCKET_SERVER_URL not set — skipping WebSocket send")
        return False

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        ws = _websocket.create_connection(WEBSOCKET_SERVER_URL, timeout=10)
        try:
            metadata = {
                "type": "image",
                "sensor_device_id": SENSOR_DEVICE_ID,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "filename": os.path.basename(image_path),
                "size": len(image_data),
                "cloudinary_url": cloudinary_url,
            }
            if WS_SEND_METADATA_FIRST:
                # Optional frame 1: metadata as JSON text.
                ws.send(json.dumps(metadata))
            # Raw image bytes frame.
            ws.send_binary(image_data)
        finally:
            ws.close()

        logger.info(
            f"[WS] Sent image ({len(image_data):,} bytes) to {_safe_ws_url(WEBSOCKET_SERVER_URL)} "
            f"(metadata_first={WS_SEND_METADATA_FIRST})"
        )
        return True

    except _websocket.WebSocketTimeoutException:
        logger.error(f"[WS] Connection timed out: {_safe_ws_url(WEBSOCKET_SERVER_URL)}")
    except _websocket.WebSocketConnectionClosedException as e:
        logger.error(f"[WS] Connection closed unexpectedly: {e}")
    except OSError as e:
        logger.error(f"[WS] Network error: {e}")
    except Exception as e:
        logger.error(f"[WS] Failed to send image: {e}")
    return False

stop_event = threading.Event()


water_level_filter = WaterLevelFilter(
    enabled=SENSOR_FILTER_ENABLED,
    window_size=SENSOR_FILTER_WINDOW_SIZE,
    min_valid_samples=SENSOR_FILTER_MIN_VALID_SAMPLES,
    min_cm=SENSOR_FILTER_MIN_CM,
    max_cm=SENSOR_FILTER_MAX_CM,
    modz_threshold=SENSOR_FILTER_MODZ_THRESHOLD,
    zero_mad_tolerance_cm=SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM,
    rebaseline_outlier_streak=SENSOR_FILTER_REBASELINE_OUTLIER_STREAK,
    rebaseline_spread_max_cm=SENSOR_FILTER_REBASELINE_SPREAD_MAX_CM,
)


def signal_handler(sig, frame):
    logger.info("Shutdown requested")
    stop_event.set()


def sensor_loop():
    """Read the JSN-SR04 and POST to the server at SENSOR_INTERVAL."""
    _rate = f"{1 / SENSOR_INTERVAL:.1f}" if SENSOR_INTERVAL else "∞"
    logger.info(
        f"[SENSOR] Loop started — interval={SENSOR_INTERVAL}s "
        f"({_rate} reading/s)"
    )
    while not stop_event.is_set():
        t0 = time.monotonic()
        try:
            level = get_water_level()
            if level is None:
                logger.warning("Failed to read water level, skipping")
            else:
                filtered_level, filter_status = water_level_filter.process(level)
                if filtered_level is None:
                    logger.warning(
                        f"[SENSOR] Dropped raw level={level}cm (reason={filter_status})"
                    )
                else:
                    update_warning_led(filtered_level)
                    logger.info(
                        f"[SENSOR] Local reading raw={level}cm filtered={filtered_level:.2f}cm "
                        f"device={SENSOR_DEVICE_ID} filter={filter_status}"
                    )

                    if not SENSOR_POST_ENABLED:
                        continue

                    try:
                        headers = {}
                        if IOT_API_KEY:
                            headers["x-api-key"] = IOT_API_KEY
                        else:
                            logger.warning("[SENSOR] IOT_API_KEY is not set; request may be rejected with 401")

                        payload = {
                            "sensor_device_id": SENSOR_DEVICE_ID,
                            "raw_distance_cm": round(level, 2),
                            "signal_strength": 100,
                            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                        response = requests.post(SERVER_URL, json=payload, headers=headers, timeout=5)
                        if response.status_code == 429:
                            logger.warning(
                                "[SENSOR] API rate-limited (429). "
                                "Keeping local logs and retrying next cycle."
                            )
                        else:
                            response.raise_for_status()
                            logger.info(
                                f"Sensor posted: raw={level}cm filtered={filtered_level:.2f}cm "
                                f"device={SENSOR_DEVICE_ID} filter={filter_status}"
                            )
                    except requests.exceptions.Timeout:
                        logger.error(f"Timeout posting sensor data to {SERVER_URL}")
                    except requests.exceptions.RequestException as e:
                        if hasattr(e, "response") and e.response is not None:
                            logger.error(
                                f"Sensor post failed: status={e.response.status_code} "
                                f"body={e.response.text}"
                            )
                        else:
                            logger.error(f"Sensor post failed: {e}")
        except Exception as e:
            logger.error(f"Sensor loop error: {e}")

        # Sleep for the remainder of the interval; wake immediately on shutdown.
        stop_event.wait(max(0.0, SENSOR_INTERVAL - (time.monotonic() - t0)))


def camera_loop():
    """Capture frames, upload to Cloudinary, and stream via WebSocket at CAMERA_INTERVAL.

    The camera is opened once via PersistentCamera and stays open for the
    lifetime of the loop, avoiding the 2-second AEC/AWB warm-up on every
    frame.
    """
    _fps = f"{1 / CAMERA_INTERVAL:.1f}" if CAMERA_INTERVAL else "∞"
    logger.info(
        f"[CAMERA] Loop started — interval={CAMERA_INTERVAL}s "
        f"({_fps} fps)"
    )
    if USE_TEST_IMAGES:
        logger.info(f"[CAMERA] Using test images from {TEST_IMAGES_DIR}")
        cam = None
        while not stop_event.is_set():
            t0 = time.monotonic()
            path = None
            try:
                path = _next_test_image_path()
                if path is None:
                    logger.warning(f"[CAMERA] No images in {TEST_IMAGES_DIR}")
                else:
                    if not is_frame_usable(str(path)):
                        metrics = get_frame_quality_metrics(str(path))
                        logger.warning(
                            f"[CAMERA] Dropped frame {path} (quality gate): {_format_frame_metrics(metrics)}"
                        )
                        stop_event.wait(max(0.0, CAMERA_INTERVAL - (time.monotonic() - t0)))
                        continue

                    url = None
                    if ENABLE_CLOUDINARY_UPLOAD:
                        url = upload_image(str(path))
                        if url is None:
                            logger.warning("Failed to upload image")

                    if ENABLE_WEBSOCKET_SEND:
                        ws_ok = send_image_websocket(str(path), cloudinary_url=url)
                        if not ws_ok:
                            logger.warning(f"[CAMERA] WebSocket send failed for {path}")
                    if url:
                        logger.info(f"Camera: uploaded {url}")
            except Exception as e:
                logger.error(f"Camera loop error: {e}")

            stop_event.wait(max(0.0, CAMERA_INTERVAL - (time.monotonic() - t0)))
    else:
        with PersistentCamera() as cam:
            while not stop_event.is_set():
                t0 = time.monotonic()
                path = None
                try:
                    path = cam.capture()
                    if not is_frame_usable(path):
                        metrics = get_frame_quality_metrics(path)
                        logger.warning(
                            f"[CAMERA] Dropped frame {path} (quality gate): {_format_frame_metrics(metrics)}"
                        )
                        stop_event.wait(max(0.0, CAMERA_INTERVAL - (time.monotonic() - t0)))
                        continue

                    url = None
                    if ENABLE_CLOUDINARY_UPLOAD:
                        url = upload_image(path)
                        if url is None:
                            logger.warning("Failed to upload image")

                    if ENABLE_WEBSOCKET_SEND:
                        ws_ok = send_image_websocket(path, cloudinary_url=url)
                        if not ws_ok:
                            logger.warning(f"[CAMERA] WebSocket send failed for {path}")
                    if url:
                        logger.info(f"Camera: uploaded {url}")
                except Exception as e:
                    logger.error(f"Camera loop error: {e}")
                finally:
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception as cleanup_err:
                            logger.warning(f"Failed to clean up {path}: {cleanup_err}")

                stop_event.wait(max(0.0, CAMERA_INTERVAL - (time.monotonic() - t0)))


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    sensor_thread = threading.Thread(target=sensor_loop, name="sensor", daemon=True)
    camera_thread = threading.Thread(target=camera_loop, name="camera", daemon=True)

    logger.info(
        f"AGOS starting — sensor={SENSOR_INTERVAL}s interval, "
        f"camera={CAMERA_INTERVAL}s interval "
        f"({f'{1 / CAMERA_INTERVAL:.1f}' if CAMERA_INTERVAL else '∞'} fps)"
    )
    sensor_thread.start()
    camera_thread.start()

    # Block the main thread until both workers exit after stop_event is set.
    sensor_thread.join()
    camera_thread.join()
    logger.info("AGOS stopped.")

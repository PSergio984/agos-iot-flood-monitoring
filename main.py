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
    CAMERA_SEND_PRECAPTURE_STATUS_IMAGE,
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
    RISK_SCORE_API_URL,
    RISK_SCORE_POLL_INTERVAL,
)
from camera import PersistentCamera, build_ir_status_image, get_ir_status_snapshot, force_night_vision
from frame_quality import get_frame_quality_metrics, is_frame_usable, is_frame_dark, is_frame_obscured
from sensor import get_water_level, update_risk_led, water_level_to_risk_score
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
    images = [
        p
        for p in image_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in allowed
    ]
    return sorted(
        images, key=lambda p: p.relative_to(image_dir).as_posix().lower()
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


def _send_precapture_status_image() -> None:
    """Optionally send an IR/day-night status image before each regular frame."""
    if not CAMERA_SEND_PRECAPTURE_STATUS_IMAGE:
        return

    status_path = None
    try:
        status_snapshot = get_ir_status_snapshot()
        status_path = build_ir_status_image()

        url = None
        if ENABLE_CLOUDINARY_UPLOAD:
            url = upload_image(status_path)
            if url is None:
                logger.warning("[CAMERA] Failed to upload pre-capture status image")

        if ENABLE_WEBSOCKET_SEND:
            ws_ok = send_image_websocket(
                status_path,
                cloudinary_url=url,
                extra_metadata={
                    "frame_role": "pre_capture_status",
                    "ir_status": status_snapshot,
                },
            )
            if not ws_ok:
                logger.warning("[CAMERA] WebSocket send failed for pre-capture status image")

        logger.info(
            "[CAMERA] Pre-capture status sent "
            f"(phase={status_snapshot['phase']} ir_pass_expected={status_snapshot['ir_pass_expected']})"
        )
    except Exception as e:
        logger.error(f"[CAMERA] Failed to build/send pre-capture status image: {e}")
    finally:
        if status_path and os.path.exists(status_path):
            try:
                os.remove(status_path)
            except Exception as cleanup_err:
                logger.warning(f"Failed to clean up {status_path}: {cleanup_err}")


def send_image_websocket(image_path, cloudinary_url=None, extra_metadata=None):
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
            if extra_metadata:
                metadata.update(extra_metadata)
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
                    # Drive state-based risk LEDs via water-level fallback.
                    risk_score = water_level_to_risk_score(filtered_level)
                    if risk_score is not None:
                        update_risk_led(risk_score)
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
                _send_precapture_status_image()
                path = _next_test_image_path()
                if path is None:
                    logger.warning(f"[CAMERA] No images in {TEST_IMAGES_DIR}")
                else:
                    # ── Environment sensing (reuses existing quality metrics) ──
                    metrics = get_frame_quality_metrics(str(path))
                    if metrics and (is_frame_dark(metrics) or is_frame_obscured(metrics)):
                        force_night_vision()
                        logger.info(
                            f"[CAMERA] Environment dark/obscured — activated night vision "
                            f"(brightness={metrics['brightness']:.1f} contrast={metrics['contrast_stddev']:.1f} "
                            f"laplacian={metrics['laplacian_var']:.1f})"
                        )

                    if not is_frame_usable(str(path)):
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
                        ws_ok = send_image_websocket(
                            str(path),
                            cloudinary_url=url,
                            extra_metadata={
                                "frame_role": "camera_frame",
                                "ir_status": get_ir_status_snapshot(),
                            },
                        )
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
                    _send_precapture_status_image()
                    path = cam.capture()

                    # ── Environment sensing (reuses existing quality metrics) ──
                    metrics = get_frame_quality_metrics(path)
                    if metrics and (is_frame_dark(metrics) or is_frame_obscured(metrics)):
                        force_night_vision()
                        logger.info(
                            f"[CAMERA] Environment dark/obscured — activated night vision "
                            f"(brightness={metrics['brightness']:.1f} contrast={metrics['contrast_stddev']:.1f} "
                            f"laplacian={metrics['laplacian_var']:.1f})"
                        )

                    if not is_frame_usable(path):
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
                        ws_ok = send_image_websocket(
                            path,
                            cloudinary_url=url,
                            extra_metadata={
                                "frame_role": "camera_frame",
                                "ir_status": get_ir_status_snapshot(),
                            },
                        )
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


def risk_led_loop():
    """Poll the Fusion & Decision Engine API for combined risk score.

    Updates the RGB LED according to REQ-22.1/22.2/22.3.
    When the API is unreachable or not configured, the sensor_loop
    drives the LED via the water-level fallback instead.
    """
    if not RISK_SCORE_API_URL:
        logger.info(
            "[LED] RISK_SCORE_API_URL not configured — "
            "RGB LED will be driven by water-level fallback in sensor_loop"
        )
        return  # Nothing to poll; sensor_loop handles the LED.

    logger.info(
        f"[LED] Risk LED loop started — polling {RISK_SCORE_API_URL} "
        f"every {RISK_SCORE_POLL_INTERVAL}s"
    )
    headers = {}
    if IOT_API_KEY:
        headers["x-api-key"] = IOT_API_KEY

    while not stop_event.is_set():
        try:
            response = requests.get(
                RISK_SCORE_API_URL, headers=headers, timeout=5
            )
            response.raise_for_status()
            data = response.json()
            score = data.get("combined_risk_score")
            if score is not None:
                update_risk_led(score)
                logger.debug(f"[LED] API risk score={score}")
            else:
                logger.warning(
                    "[LED] API response missing 'combined_risk_score' key"
                )
        except requests.exceptions.Timeout:
            logger.warning(
                "[LED] Risk score API timed out — holding last LED state"
            )
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"[LED] Risk score API error: {e} — holding last LED state"
            )
        except Exception as e:
            logger.error(f"[LED] Unexpected error in risk LED loop: {e}")

        stop_event.wait(RISK_SCORE_POLL_INTERVAL)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    sensor_thread = threading.Thread(target=sensor_loop, name="sensor", daemon=True)
    camera_thread = threading.Thread(target=camera_loop, name="camera", daemon=True)
    risk_led_thread = threading.Thread(target=risk_led_loop, name="risk_led", daemon=True)

    logger.info(
        f"AGOS starting — sensor={SENSOR_INTERVAL}s interval, "
        f"camera={CAMERA_INTERVAL}s interval "
        f"({f'{1 / CAMERA_INTERVAL:.1f}' if CAMERA_INTERVAL else '∞'} fps), "
        f"RISK_LED={'API' if RISK_SCORE_API_URL else 'water-level fallback'}"
    )
    sensor_thread.start()
    camera_thread.start()
    risk_led_thread.start()

    # Block the main thread until all workers exit after stop_event is set.
    sensor_thread.join()
    camera_thread.join()
    risk_led_thread.join()
    logger.info("AGOS stopped.")

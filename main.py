from camera import capture_image
from sensor import get_water_level
from uploader import upload_image
from config import SENSOR_DEVICE_ID
import requests
import time
import os
import logging
import signal
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server configuration
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:5000/data")

shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    logger.info("Shutdown requested")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

while not shutdown_requested:
    path = None
    try:
        path = capture_image()
        url = upload_image(path)
        if url is None:
            logger.warning("Failed to upload image, skipping this iteration")
            continue
        
        level = get_water_level()
        if level is None:
            logger.warning("Failed to read water level, skipping this iteration")
            continue
        
        # Post data to server with timeout and error handling
        try:
            payload = {
                "sensor_device_id": SENSOR_DEVICE_ID,
                "raw_distance_cm": level,
                "signal_strength": 100,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            response = requests.post(
                SERVER_URL,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"Posted data: device={SENSOR_DEVICE_ID}, distance={level}cm, url={url}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout posting to {SERVER_URL}")
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Failed to post data: status={e.response.status_code}, response={e.response.text}")
            else:
                logger.error(f"Failed to post data: {e}")
    except Exception as e:
        logger.error(f"Error in monitoring loop: {e}")
    finally:
        # Clean up temporary image file
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Cleaned up temporary file: {path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {path}: {e}")
    time.sleep(3)

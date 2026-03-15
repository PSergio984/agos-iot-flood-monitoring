"""
RPi WebSocket image-push test script.

Usage (local, on your PC):
    pip install websockets
    python ws_sender.py

Usage (on the RPi, pointing at your PC's IP):
    HOST = "192.168.1.5"   # ← change to your PC's LAN IP
    python ws_sender.py

The script:
  1. Connects to /ws/rpi with the required query params
  2. Waits for the server's "connected" acknowledgment
  3. Sends a JPEG image as a raw binary WebSocket frame
  4. Loops, sending a new frame every CAMERA_INTERVAL seconds
  5. Press Ctrl+C to stop
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    import websockets
except ImportError:
    sys.exit("websockets not installed — run: pip install websockets")

# ── Configuration (loaded from .env) ─────────────────────────────────────────
# WebSocket server URL — set WEBSOCKET_SERVER_URL in your .env file.
WEBSOCKET_SERVER_URL = os.getenv(
    "WEBSOCKET_SERVER_URL",
    "ws://localhost:8000/ws/rpi?camera_device_id=1&location_id=1",
)

# Seconds between frames; 0 = single-shot mode.  Matches CAMERA_INTERVAL in .env.
INTERVAL_SECONDS = float(os.getenv("CAMERA_INTERVAL", "0.5"))

# Optional WebSocket keepalive tuning. Set WS_PING_INTERVAL=0 to disable pings.
# Defaults disable keepalive to avoid server-side pong timeouts.
_PING_INTERVAL_RAW = os.getenv("WS_PING_INTERVAL", "0")
_PING_TIMEOUT_RAW = os.getenv("WS_PING_TIMEOUT", "0")
_CLOSE_TIMEOUT_RAW = os.getenv("WS_CLOSE_TIMEOUT", "10")

PING_INTERVAL = None if _PING_INTERVAL_RAW.strip() in {"", "0", "none", "None"} else float(_PING_INTERVAL_RAW)
PING_TIMEOUT = None if _PING_TIMEOUT_RAW.strip() in {"", "0", "none", "None"} else float(_PING_TIMEOUT_RAW)
CLOSE_TIMEOUT = float(_CLOSE_TIMEOUT_RAW)

# Folder of test images (image1/image2/image3...) to cycle through.
TEST_IMAGES_DIR = os.getenv("TEST_IMAGES_DIR", "test_images")
def _load_test_images() -> list[Path]:
    image_dir = Path(TEST_IMAGES_DIR)
    if not image_dir.exists() or not image_dir.is_dir():
        return []
    allowed = {".jpg", ".jpeg", ".png"}
    return sorted(
        [p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed]
    )


_TEST_IMAGES = _load_test_images()
_TEST_IMAGE_INDEX = 0


def _capture_frame() -> bytes:
    global _TEST_IMAGE_INDEX
    if _TEST_IMAGES:
        image_path = _TEST_IMAGES[_TEST_IMAGE_INDEX % len(_TEST_IMAGES)]
        _TEST_IMAGE_INDEX += 1
        return image_path.read_bytes()
    raise FileNotFoundError(
        f"No images found in '{TEST_IMAGES_DIR}'. Add test images or set TEST_IMAGES_DIR."
    )


async def run():
    uri = WEBSOCKET_SERVER_URL
    frame_count = 0
    reconnect_delay = 2  # seconds between reconnect attempts

    while True:
        print(f"Connecting to {uri} …")
        try:
            # Ping settings are configurable via .env to avoid keepalive timeouts
            # on slower or busy servers.
            async with websockets.connect(
                uri,
                ping_interval=PING_INTERVAL,
                ping_timeout=PING_TIMEOUT,
                close_timeout=CLOSE_TIMEOUT,
            ) as ws:
                # Wait for the server handshake acknowledgment
                ack_raw = await ws.recv()
                ack = json.loads(ack_raw)
                if ack.get("type") != "connected":
                    print(f"Unexpected handshake: {ack}")
                    return
                print(
                    f"✅ Connected  cam={ack['camera_device_id']}  loc={ack['location_id']}"
                )

                while True:
                    frame_count += 1
                    image_bytes = _capture_frame()
                    print(
                        f"📤 Sending frame #{frame_count}  ({len(image_bytes):,} bytes) …"
                    )

                    # Send the JPEG as a raw binary WebSocket frame
                    await ws.send(image_bytes)

                    if INTERVAL_SECONDS <= 0:
                        return  # Single-shot mode

                    print(f"   Waiting {INTERVAL_SECONDS}s before next frame …\n")
                    await asyncio.sleep(INTERVAL_SECONDS)

        except websockets.exceptions.ConnectionClosedError as e:
            print(f"⚠️  Connection closed ({e}), reconnecting in {reconnect_delay}s …")
            await asyncio.sleep(reconnect_delay)
        except OSError as e:
            print(f"⚠️  Network error ({e}), reconnecting in {reconnect_delay}s …")
            await asyncio.sleep(reconnect_delay)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")

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

# Optional path to a local JPEG to send instead of a generated test image.
# Leave unset (or empty) to fall back to the built-in minimal JPEG.
IMAGE_PATH = os.getenv("IMAGE_PATH", "")

def _make_minimal_jpeg() -> bytes:
    """Return a tiny but valid 1×1 white JPEG for testing without a real camera."""
    return bytes(
        [
            0xFF,
            0xD8,
            0xFF,
            0xE0,
            0x00,
            0x10,
            0x4A,
            0x46,
            0x49,
            0x46,
            0x00,
            0x01,
            0x01,
            0x00,
            0x00,
            0x01,
            0x00,
            0x01,
            0x00,
            0x00,
            0xFF,
            0xDB,
            0x00,
            0x43,
            0x00,
            0x08,
            0x06,
            0x06,
            0x07,
            0x06,
            0x05,
            0x08,
            0x07,
            0x07,
            0x07,
            0x09,
            0x09,
            0x08,
            0x0A,
            0x0C,
            0x14,
            0x0D,
            0x0C,
            0x0B,
            0x0B,
            0x0C,
            0x19,
            0x12,
            0x13,
            0x0F,
            0x14,
            0x1D,
            0x1A,
            0x1F,
            0x1E,
            0x1D,
            0x1A,
            0x1C,
            0x1C,
            0x20,
            0x24,
            0x2E,
            0x27,
            0x20,
            0x22,
            0x2C,
            0x23,
            0x1C,
            0x1C,
            0x28,
            0x37,
            0x29,
            0x2C,
            0x30,
            0x31,
            0x34,
            0x34,
            0x34,
            0x1F,
            0x27,
            0x39,
            0x3D,
            0x38,
            0x32,
            0x3C,
            0x2E,
            0x33,
            0x34,
            0x32,
            0xFF,
            0xC0,
            0x00,
            0x0B,
            0x08,
            0x00,
            0x01,
            0x00,
            0x01,
            0x01,
            0x01,
            0x11,
            0x00,
            0xFF,
            0xC4,
            0x00,
            0x1F,
            0x00,
            0x00,
            0x01,
            0x05,
            0x01,
            0x01,
            0x01,
            0x01,
            0x01,
            0x01,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x01,
            0x02,
            0x03,
            0x04,
            0x05,
            0x06,
            0x07,
            0x08,
            0x09,
            0x0A,
            0x0B,
            0xFF,
            0xDA,
            0x00,
            0x08,
            0x01,
            0x01,
            0x00,
            0x00,
            0x3F,
            0x00,
            0xFB,
            0x4D,
            0xFF,
            0xD9,
        ]
    )


def _capture_frame() -> bytes:

    if IMAGE_PATH and Path(IMAGE_PATH).exists():
        return Path(IMAGE_PATH).read_bytes()
    return _make_minimal_jpeg()


async def run():
    uri = WEBSOCKET_SERVER_URL
    frame_count = 0
    reconnect_delay = 2  # seconds between reconnect attempts

    while True:
        print(f"Connecting to {uri} …")
        try:
            # ping_interval/ping_timeout match common server defaults (20 s).
            # Keeping them enabled ensures our client answers server pings.
            async with websockets.connect(
                uri, ping_interval=20, ping_timeout=20
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

# camera.py
import os
import subprocess
import tempfile

CAMERA_WIDTH         = int(os.getenv("CAMERA_WIDTH",         "1296"))
CAMERA_HEIGHT        = int(os.getenv("CAMERA_HEIGHT",        "972"))
CAMERA_NO_CROP       = os.getenv("CAMERA_NO_CROP",           "false").lower() == "true"
CAMERA_SENSOR_WIDTH  = int(os.getenv("CAMERA_SENSOR_WIDTH",  "2592"))
CAMERA_SENSOR_HEIGHT = int(os.getenv("CAMERA_SENSOR_HEIGHT", "1944"))

# Check if we're explicitly in mock mode or if picamera2 is unavailable
MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
USE_FSWEBCAM = os.getenv("USE_FSWEBCAM", "false").lower() == "true"  # For VM testing

# Initialize PICAMERA_AVAILABLE to False by default
PICAMERA_AVAILABLE = False

# Try to import picamera2 - if it fails, automatically enable mock mode
try:
    if not MOCK:
        from picamera2 import Picamera2
        # Verify at least one camera is physically detected by libcamera.
        # global_camera_info() returns [] when no hardware is connected,
        # which would cause IndexError inside Picamera2.__init__().
        _detected = Picamera2.global_camera_info()
        if _detected:
            PICAMERA_AVAILABLE = True
            print("[CAMERA] picamera2 module loaded successfully")
        else:
            MOCK = True
            print("[CAMERA] No cameras detected by libcamera — running in MOCK mode")
    else:
        print("[CAMERA] MOCK_MODE enabled - running in MOCK mode")
except (ImportError, ModuleNotFoundError):
    MOCK = True
    print("[CAMERA] picamera2 not available - running in MOCK mode")
except Exception as e:
    MOCK = True
    print(f"[CAMERA] Camera initialisation failed ({e}) — running in MOCK mode")

def capture_image(path=None):
    # Use cross-platform temporary directory if path not specified
    if path is None:
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, "frame.jpg")
    if MOCK or not PICAMERA_AVAILABLE:
        # Option 1: Use fswebcam for VM testing with USB camera
        if USE_FSWEBCAM:
            try:
                print("[MOCK] Capturing with fswebcam...")
                result = subprocess.run(
                    ['fswebcam', '-r', '640x480', '--no-banner', '-S', '10', path],
                    capture_output=True,
                    timeout=15
                )
                if result.returncode == 0:
                    print(f"[MOCK] fswebcam capture successful: {path}")
                    return path
                else:
                    print(f"[MOCK] fswebcam failed: {result.stderr.decode()}")
            except FileNotFoundError:
                print("[MOCK] fswebcam not installed, falling back to test image")
            except Exception as e:
                print(f"[MOCK] fswebcam error: {e}")
        
        # Option 2: Copy existing test image
        if os.path.exists("test_image.jpg"):
            import shutil
            shutil.copy("test_image.jpg", path)
            print(f"[MOCK] Copied test_image.jpg to {path}")
            return path
        
        # Option 3: Generate a blank test image with PIL
        try:
            from PIL import Image, ImageDraw, ImageFont
            import datetime
            img = Image.new('RGB', (640, 480), color=(73, 109, 137))
            draw = ImageDraw.Draw(img)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            draw.text((10, 10), f"AGOS Mock Camera\n{timestamp}", fill=(255, 255, 255))
            img.save(path)
            print(f"[MOCK] Generated test image: {path}")
            return path
        except ImportError:
            print("[MOCK] PIL not available, creating minimal blank image")
            # Fallback: create a minimal valid JPEG
            with open(path, 'wb') as f:
                # Minimal 1x1 JPEG header
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                       b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
                       b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
                       b'\x1c $.\'" ,#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00'
                       b'\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01'
                       b'\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05'
                       b'\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04'
                       b'\x03\x05\x05\x04\x04\x00\x00\x01}\xff\xda\x00\x08\x01\x01\x00\x00?\x00'
                       b'\xd2\xcf \xff\xd9')
            print(f"[MOCK] Created minimal test image: {path}")
            return path
    
    import time
    cam = None
    try:
        cam = Picamera2()
        # Configure for high-quality stills at target resolution.
        # create_still_configuration() overrides the default 640×480 preview mode.
        # ScalerCrop is baked into the config so AEC/AWB converges on the
        # correct sensor region from the very first frame.
        controls = {}
        if CAMERA_NO_CROP:
            controls["ScalerCrop"] = (0, 0, CAMERA_SENSOR_WIDTH, CAMERA_SENSOR_HEIGHT)
        config = cam.create_still_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)},
            controls=controls,
            buffer_count=1,
        )
        cam.configure(config)
        cam.start()
        time.sleep(2)  # Allow AEC/AWB to converge on the correct crop region
        cam.capture_file(path)
        print(f"[CAMERA] Captured {CAMERA_WIDTH}×{CAMERA_HEIGHT} image: {path}")
        return path
    finally:
        if cam is not None:
            try:
                cam.stop()
            except Exception:
                pass  # Best effort cleanup
            try:
                cam.close()
            except Exception:
                pass  # Best effort cleanup


class PersistentCamera:
    """Keep picamera2 open across rapid successive captures.

    Opens and configures the camera once (paying the 2-second AEC/AWB
    warm-up only at startup), then captures frames on demand with no
    per-frame initialisation overhead.  Use as a context manager::

        with PersistentCamera() as cam:
            path = cam.capture()   # fast — no sleep

    Falls back to the module-level mock path when MOCK_MODE is active.
    """

    def __init__(self):
        self._cam = None

    def start(self):
        """Open and configure the camera; blocks until AEC/AWB converges."""
        if MOCK or not PICAMERA_AVAILABLE:
            print("[CAMERA] PersistentCamera: running in MOCK mode")
            return
        if self._cam is not None:
            self.stop()  # Close existing camera before re-opening
        import time
        self._cam = Picamera2()
        # ScalerCrop baked into config so AEC/AWB converges on the correct
        # sensor region from the very first frame.
        controls = {}
        if CAMERA_NO_CROP:
            controls["ScalerCrop"] = (0, 0, CAMERA_SENSOR_WIDTH, CAMERA_SENSOR_HEIGHT)
        config = self._cam.create_still_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)},
            controls=controls,
            buffer_count=1,
        )
        self._cam.configure(config)
        self._cam.start()
        time.sleep(2)  # AEC/AWB convergence on correct crop — paid once, not per frame
        print(f"[CAMERA] PersistentCamera ready ({CAMERA_WIDTH}×{CAMERA_HEIGHT}{'  full-sensor' if CAMERA_NO_CROP else ''})")

    def capture(self, path=None):
        """Capture a single frame with no startup delay.

        A timestamped filename is generated automatically when *path* is
        omitted, avoiding collisions when called at high frame rates.
        """
        if path is None:
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(tempfile.gettempdir(), f"frame_{ts}.jpg")
        if MOCK or not PICAMERA_AVAILABLE or self._cam is None:
            return capture_image(path)  # use mock path
        self._cam.capture_file(path)
        return path

    def stop(self):
        """Stop and close the camera."""
        if self._cam is not None:
            try:
                self._cam.stop()
            except Exception:
                pass
            try:
                self._cam.close()
            except Exception:
                pass
            self._cam = None
            print("[CAMERA] PersistentCamera stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

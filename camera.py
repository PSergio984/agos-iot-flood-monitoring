# camera.py
import os
import subprocess
import tempfile

# Check if we're explicitly in mock mode or if picamera2 is unavailable
MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
USE_FSWEBCAM = os.getenv("USE_FSWEBCAM", "false").lower() == "true"  # For VM testing

# Initialize PICAMERA_AVAILABLE to False by default
PICAMERA_AVAILABLE = False

# Try to import picamera2 - if it fails, automatically enable mock mode
try:
    if not MOCK:
        from picamera2 import Picamera2
        PICAMERA_AVAILABLE = True
        print("[CAMERA] picamera2 module loaded successfully")
    else:
        print("[CAMERA] MOCK_MODE enabled - running in MOCK mode")
except (ImportError, ModuleNotFoundError):
    MOCK = True
    print("[CAMERA] picamera2 not available - running in MOCK mode")

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
    
    from picamera2 import Picamera2
    import time
    cam = None
    try:
        cam = Picamera2()
        cam.start()
        time.sleep(2)
        cam.capture_file(path)
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

# camera.py
import os

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

def capture_image(path="/tmp/frame.jpg"):
    if MOCK:
        # Copy a test image instead of using real camera
        import shutil
        shutil.copy("test_image.jpg", path)
        print("[MOCK] Fake image captured")
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

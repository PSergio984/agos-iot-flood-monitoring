#!/usr/bin/env python3
"""
AGOS IoT - Mock Mode Test Script
Tests all components in mock mode without requiring hardware
"""

import os
import sys
from dotenv import load_dotenv

# Force mock mode for this test
os.environ["MOCK_MODE"] = "true"
load_dotenv()

def test_camera():
    """Test camera capture in mock mode"""
    print("\n🔍 Testing Camera Module...")
    try:
        from camera import capture_image
        path = capture_image()
        if path and os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✅ Camera test passed: {path} ({size} bytes)")
            return True
        else:
            print("❌ Camera test failed: No image created")
            return False
    except Exception as e:
        print(f"❌ Camera test failed: {e}")
        return False

def test_sensor():
    """Test sensor reading in mock mode"""
    print("\n🔍 Testing Sensor Module...")
    try:
        from sensor import get_water_level
        level = get_water_level()
        if level is not None and 0 <= level <= 100:
            print(f"✅ Sensor test passed: {level} cm")
            return True
        else:
            print(f"❌ Sensor test failed: Invalid reading {level}")
            return False
    except Exception as e:
        print(f"❌ Sensor test failed: {e}")
        return False

def test_uploader():
    """Test Cloudinary upload"""
    print("\n🔍 Testing Cloudinary Upload...")
    
    # Check if credentials are configured
    if not os.getenv("CLOUDINARY_CLOUD_NAME") or os.getenv("CLOUDINARY_CLOUD_NAME") == "your_cloud_name_here":
        print("⚠️  Cloudinary credentials not configured in .env")
        print("   Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET")
        return None
    
    try:
        from camera import capture_image
        from uploader import upload_image
        
        path = capture_image()
        
        # Check if capture_image returned a valid path
        if not path:
            print("❌ Upload test failed: capture_image returned None/invalid path")
            return False
        
        try:
            url = upload_image(path)
            
            if url:
                print(f"✅ Upload test passed: {url}")
                return True
            else:
                print("❌ Upload test failed: No URL returned")
                return False
        finally:
            # Cleanup: Always remove the temporary file if it exists
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as cleanup_err:
                    print(f"⚠️  Warning: Failed to cleanup {path}: {cleanup_err}")
                    
    except Exception as e:
        print(f"❌ Upload test failed: {e}")
        return False

def test_backend_connection():
    """Test backend server connectivity"""
    print("\n🔍 Testing Backend Connection...")
    
    server_url = os.getenv("SERVER_URL", "http://localhost:5000/data")
    print(f"   Target: {server_url}")
    
    if "localhost" in server_url or "127.0.0.1" in server_url:
        print("⚠️  Backend is set to localhost - make sure server is running")
        print("   Or update SERVER_URL in .env to point to your backend")
        return None
    
    try:
        import requests
        
        payload = {
            "image_url": "https://res.cloudinary.com/test/image.jpg",
            "water_level": 12.5
        }
        
        response = requests.post(server_url, json=payload, timeout=5)
        
        if response.status_code < 500:
            print(f"✅ Backend connection test passed: HTTP {response.status_code}")
            return True
        else:
            print(f"❌ Backend returned error: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Backend connection failed: Server not reachable")
        return False
    except requests.exceptions.Timeout:
        print("❌ Backend connection timeout")
        return False
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False

def test_environment():
    """Test environment configuration"""
    print("\n🔍 Testing Environment Configuration...")
    
    required = [
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY", 
        "CLOUDINARY_API_SECRET",
        "SERVER_URL"
    ]
    
    missing = []
    for var in required:
        value = os.getenv(var)
        if not value or "your_" in value or "here" in value:
            missing.append(var)
    
    if missing:
        print(f"⚠️  Missing or incomplete configuration: {', '.join(missing)}")
        print("   Copy .env.example to .env and configure your credentials")
        return False
    else:
        print("✅ Environment configuration complete")
        return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 AGOS IoT - Mock Mode Test Suite")
    print("=" * 60)
    
    print(f"\nMock Mode: {os.getenv('MOCK_MODE', 'false')}")
    print(f"Use fswebcam: {os.getenv('USE_FSWEBCAM', 'false')}")
    
    results = {
        "Environment": test_environment(),
        "Camera": test_camera(),
        "Sensor": test_sensor(),
        "Cloudinary": test_uploader(),
        "Backend": test_backend_connection()
    }
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for name, result in results.items():
        if result is True:
            print(f"✅ {name}: PASSED")
        elif result is False:
            print(f"❌ {name}: FAILED")
        else:
            print(f"⚠️  {name}: SKIPPED (needs configuration)")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)
    elif skipped > 0:
        print("\n⚠️  Some tests were skipped. Configure .env to run all tests.")
        sys.exit(0)
    else:
        print("\n🎉 All tests passed! Your setup is ready.")
        sys.exit(0)

if __name__ == "__main__":
    main()

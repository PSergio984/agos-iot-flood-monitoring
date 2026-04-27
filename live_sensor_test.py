import time
import os
from sensor import get_water_level, update_risk_led, water_level_to_risk_score

def main():
    """
    Standalone script to test the JSN-SR04T ultrasonic sensor and indicator LEDs
    without triggering camera captures or uploading data to the backend.
    """
    print("=" * 50)
    print("🌊 AGOS IoT: LIVE SENSOR TEST")
    print("=" * 50)
    print("Target: JSN-SR04T Ultrasonic Sensor")
    print("Action: Continuous polling (1s interval)")
    print("Features: Distance measurement + LED status updates")
    print("Excludes: Camera capture, Quality checks, Data uploading")
    print("-" * 50)
    print("Press Ctrl+C to exit.")
    print("-" * 50)

    # Note: sensor.py automatically handles GPIO initialization and MOCK detection.
    # To force REAL hardware mode on a Pi, ensure MOCK_MODE is NOT set to 'true' in .env.

    try:
        while True:
            # 1. Get raw distance from sensor
            level = get_water_level()
            
            if level is not None:
                # 2. Calculate risk score based on thresholds in config.py
                risk_score = water_level_to_risk_score(level)
                
                # 3. Update the physical LEDs if they are connected
                update_risk_led(risk_score)
                
                # 4. Log to console
                timestamp = time.strftime('%H:%M:%S')
                print(f"[{timestamp}] Reading: {level:6.2f} cm | Risk: {risk_score:3d}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Reading Failed (Check wiring/timeout)")
            
            # Rapid polling for testing; 1 second is plenty for JSN-SR04T
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\n\n[INFO] Test terminated by user.")
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")

if __name__ == "__main__":
    main()

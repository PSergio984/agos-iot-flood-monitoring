import os
import time
import random

# Check if we're explicitly in mock mode or if RPi.GPIO is unavailable
MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

# Initialize GPIO_AVAILABLE to False by default
GPIO_AVAILABLE = False

# Try to import RPi.GPIO - if it fails, automatically enable mock mode
try:
    if not MOCK:
        import RPi.GPIO as GPIO
        GPIO_AVAILABLE = True
        print("[GPIO] RPi.GPIO module loaded successfully")
    else:
        print("[GPIO] MOCK_MODE enabled - running in MOCK mode")
except (ImportError, ModuleNotFoundError, RuntimeError) as e:
    MOCK = True
    print("[GPIO] RPi.GPIO not available - running in MOCK mode")

TRIG = 23
ECHO = 24
TIMEOUT = 0.3  # 300ms timeout (covers up to ~4m range + margins)
MAX_RETRIES = 3  # Retry count before giving up

# Initialize GPIO once at module level (only if not in mock mode)
gpio_initialized = False

def _init_gpio():
    """Initialize GPIO pins once at module load."""
    global gpio_initialized
    if not gpio_initialized and GPIO_AVAILABLE and not MOCK:
        import RPi.GPIO as GPIO
        import atexit
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TRIG, GPIO.OUT)
        GPIO.setup(ECHO, GPIO.IN)
        gpio_initialized = True
        # Register cleanup to run at exit
        atexit.register(GPIO.cleanup)
        print("[GPIO] Initialized successfully")

# Initialize GPIO when module is imported (skip in mock mode)
_init_gpio()

def get_water_level():
    """Read water level from JSN-SR04 ultrasonic sensor."""
    if MOCK or not GPIO_AVAILABLE:
        # Generate realistic mock water level data (9.5-20.5 cm range)
        base_level = 12.5
        variation = random.uniform(-3.0, 8.0)
        mock_level = round(base_level + variation, 2)
        print(f"[MOCK] Generated water level: {mock_level} cm")
        return mock_level
    
    # Real hardware implementation
    import RPi.GPIO as GPIO

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Ensure trigger is low; JSN-SR04 needs ~60ms minimum cycle time
            GPIO.output(TRIG, False)
            time.sleep(0.06)  # 60ms settle (full JSN-SR04 cycle time)
            # Warn if ECHO is already HIGH — indicates a wiring or power problem.
            # JSN-SR04 wiring notes:
            #   3.3V mode: VCC→3.3V pin — ECHO outputs 3.3V, Pi-safe, no voltage divider needed.
            #   5V mode  : VCC→5V pin  — ECHO outputs 5V; add a 1kΩ/2kΩ divider to protect GPIO.
            if GPIO.input(ECHO) == 1:
                print(f"[SENSOR] Warning (attempt {attempt}): ECHO is HIGH before trigger. "
                      "Check wiring — if VCC is 5V, ECHO needs a 1kΩ/2kΩ voltage divider; "
                      "use 3.3V on VCC to avoid this.")

            # Send 10µs trigger pulse
            GPIO.output(TRIG, True)
            time.sleep(0.00001)  # 10 microseconds
            GPIO.output(TRIG, False)

            # Wait for ECHO to go HIGH (pulse start)
            timeout_start = time.monotonic()
            while GPIO.input(ECHO) == 0:
                if time.monotonic() - timeout_start > TIMEOUT:
                    raise TimeoutError(
                        f"Timeout waiting for echo HIGH (attempt {attempt}/{MAX_RETRIES}). "
                        "Check: TRIG→GPIO23, ECHO→GPIO24, VCC→3.3V (or 5V w/ voltage divider)."
                    )
            pulse_start = time.monotonic()  # Captured after ECHO went HIGH

            # Wait for ECHO to go LOW (pulse end)
            timeout_start = time.monotonic()
            while GPIO.input(ECHO) == 1:
                if time.monotonic() - timeout_start > TIMEOUT:
                    raise TimeoutError(
                        f"Timeout waiting for echo LOW (attempt {attempt}/{MAX_RETRIES})."
                    )
            pulse_end = time.monotonic()  # Captured after ECHO went LOW

            # Speed of sound ≈ 34300 cm/s, divide by 2 for round trip
            distance_cm = ((pulse_end - pulse_start) * 34300) / 2

            # Sanity check: JSN-SR04 valid range is 20 cm – 600 cm
            if not (20.0 <= distance_cm <= 600.0):
                print(f"[SENSOR] Out-of-range reading {distance_cm:.1f} cm on attempt {attempt}, retrying...")
                continue

            return round(distance_cm, 2)

        except TimeoutError as e:
            print(f"Error reading sensor: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(0.1)
        except Exception as e:
            print(f"Error reading sensor (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(0.1)

    print(f"[SENSOR] All {MAX_RETRIES} attempts failed. Returning None.")
    return None

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
TIMEOUT = 0.1  # 100ms timeout to prevent hangs

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
    """Read water level from HC-SR04 ultrasonic sensor."""
    if MOCK or not GPIO_AVAILABLE:
        # Generate realistic mock water level data (9.5-20.5 cm range)
        base_level = 12.5
        variation = random.uniform(-3.0, 8.0)
        mock_level = round(base_level + variation, 2)
        print(f"[MOCK] Generated water level: {mock_level} cm")
        return mock_level
    
    # Real hardware implementation
    import RPi.GPIO as GPIO
    try:
        # Ensure trigger is low
        GPIO.output(TRIG, False)
        time.sleep(0.01)  # 10ms settle time
        
        # Send 10µs trigger pulse
        GPIO.output(TRIG, True)
        time.sleep(0.00001)  # 10 microseconds
        GPIO.output(TRIG, False)
        
        # Wait for echo to go HIGH (with timeout)
        timeout_start = time.monotonic()
        pulse_start = time.monotonic()  # Initialize before loop
        while GPIO.input(ECHO) == 0:
            pulse_start = time.monotonic()
            if pulse_start - timeout_start > TIMEOUT:
                raise TimeoutError("Timeout waiting for echo to go HIGH")
        
        # Wait for echo to go LOW (with timeout)
        timeout_start = time.monotonic()
        pulse_end = time.monotonic()  # Initialize before loop
        while GPIO.input(ECHO) == 1:
            pulse_end = time.monotonic()
            if pulse_end - timeout_start > TIMEOUT:
                raise TimeoutError("Timeout waiting for echo to go LOW")
        
        # Calculate distance
        time_elapsed = pulse_end - pulse_start
        # Speed of sound = 34300 cm/s, divide by 2 for round trip
        distance_cm = (time_elapsed * 34300) / 2
        
        return distance_cm
        
    except (TimeoutError, Exception) as e:
        # Log error and return None on failure
        print(f"Error reading sensor: {e}")
        return None

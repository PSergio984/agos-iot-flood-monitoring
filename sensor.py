import RPi.GPIO as GPIO
import time
import atexit

TRIG = 23
ECHO = 24
TIMEOUT = 0.1  # 100ms timeout to prevent hangs

# Initialize GPIO once at module level
gpio_initialized = False

def _init_gpio():
    """Initialize GPIO pins once at module load."""
    global gpio_initialized
    if not gpio_initialized:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TRIG, GPIO.OUT)
        GPIO.setup(ECHO, GPIO.IN)
        gpio_initialized = True
        # Register cleanup to run at exit
        atexit.register(GPIO.cleanup)

# Initialize GPIO when module is imported
_init_gpio()

def get_water_level():
    """Read water level from HC-SR04 ultrasonic sensor."""
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

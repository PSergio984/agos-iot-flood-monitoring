import os
import time
import random

from config import (
    LED_CLEAR_ENABLED,
    LED_CLEAR_PIN,
    LED_WARNING_ENABLED,
    LED_WARNING_PIN,
    LED_WARNING_THRESHOLD_CM,
    SENSOR_ECHO_PIN,
    SENSOR_TRIG_PIN,
    RISK_LED_ENABLED,
    RISK_LED_RED_PIN,
    RISK_LED_YELLOW_PIN,
    RISK_LED_GREEN_PIN,
    RISK_FALLBACK_SAFE_ABOVE_CM,
    RISK_FALLBACK_WARNING_ABOVE_CM,
)

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

TRIG = SENSOR_TRIG_PIN
ECHO = SENSOR_ECHO_PIN
TIMEOUT = 0.3  # 300ms timeout (covers up to ~4m range + margins)
MAX_RETRIES = 3  # Retry count before giving up

# Initialize GPIO once at module level (only if not in mock mode)
gpio_initialized = False
_warning_led_state = None
_clear_led_state = None
_risk_led_tier = None  # Track current RGB LED tier to avoid redundant GPIO writes

def _init_gpio():
    """Initialize GPIO pins once at module load."""
    global gpio_initialized
    if not gpio_initialized and GPIO_AVAILABLE and not MOCK:
        import RPi.GPIO as GPIO
        import atexit
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TRIG, GPIO.OUT)
        GPIO.setup(ECHO, GPIO.IN)
        # Legacy 2-LED setup (kept for backward compatibility)
        if LED_WARNING_ENABLED:
            GPIO.setup(LED_WARNING_PIN, GPIO.OUT)
            GPIO.output(LED_WARNING_PIN, GPIO.LOW)
        if LED_CLEAR_ENABLED:
            GPIO.setup(LED_CLEAR_PIN, GPIO.OUT)
            GPIO.output(LED_CLEAR_PIN, GPIO.LOW)
        # Risk indicator LEDs (REQ-22)
        if RISK_LED_ENABLED:
            for pin in (RISK_LED_RED_PIN, RISK_LED_YELLOW_PIN, RISK_LED_GREEN_PIN):
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            print(f"[GPIO] Risk LED pins initialized: R={RISK_LED_RED_PIN} Y={RISK_LED_YELLOW_PIN} G={RISK_LED_GREEN_PIN}")
        gpio_initialized = True
        # Register cleanup to run at exit
        atexit.register(GPIO.cleanup)
        print("[GPIO] Initialized successfully")


def update_warning_led(water_level):
    """Toggle warning/clear LEDs based on configured water-level threshold.

    LEGACY — kept for backward compatibility.  New deployments should
    use update_risk_led() instead.
    """
    global _warning_led_state, _clear_led_state

    if not LED_WARNING_ENABLED and not LED_CLEAR_ENABLED:
        return
    if MOCK or not GPIO_AVAILABLE:
        return

    import RPi.GPIO as GPIO

    # For distance sensors, lower distance means higher water level/risk.
    warning_on = water_level is not None and water_level <= LED_WARNING_THRESHOLD_CM
    clear_on = water_level is not None and not warning_on

    if LED_WARNING_ENABLED and _warning_led_state is not warning_on:
        GPIO.output(LED_WARNING_PIN, GPIO.HIGH if warning_on else GPIO.LOW)
        _warning_led_state = warning_on
        print(
            f"[LED] Warning {'ON' if warning_on else 'OFF'} "
            f"(level={water_level}, threshold={LED_WARNING_THRESHOLD_CM})"
        )

    if LED_CLEAR_ENABLED and _clear_led_state is not clear_on:
        GPIO.output(LED_CLEAR_PIN, GPIO.HIGH if clear_on else GPIO.LOW)
        _clear_led_state = clear_on
        print(
            f"[LED] Clear {'ON' if clear_on else 'OFF'} "
            f"(level={water_level}, threshold={LED_WARNING_THRESHOLD_CM})"
        )


def water_level_to_risk_score(distance_cm):
    """Map ultrasonic distance (cm) to a 0–100 combined risk score.

    Lower distance = higher water = higher risk.
        ≥ SAFE_ABOVE_CM       → 0   (safe)
        ≥ WARNING_ABOVE_CM    → 50  (warning)
        < WARNING_ABOVE_CM    → 80  (danger)
    """
    if distance_cm is None:
        return None
    if distance_cm >= RISK_FALLBACK_SAFE_ABOVE_CM:
        return 0
    if distance_cm >= RISK_FALLBACK_WARNING_ABOVE_CM:
        return 50
    return 80


def update_risk_led(combined_risk_score):
    """Set Risk LED color based on combined risk score.

    REQ-22.1: Green  → Safe    (score 0–44)
    REQ-22.2: Yellow → Warning (score 45–75)
    REQ-22.3: Red    → Danger  (score > 75)

    Solid colors only; only writes GPIO when the tier actually changes.
    """
    global _risk_led_tier

    if not RISK_LED_ENABLED:
        return
    if MOCK or not GPIO_AVAILABLE:
        return
    if combined_risk_score is None:
        return

    # Determine tier
    if combined_risk_score <= 44:
        tier = "safe"
    elif combined_risk_score <= 75:
        tier = "warning"
    else:
        tier = "danger"

    # Skip redundant GPIO writes
    if tier == _risk_led_tier:
        return

    import RPi.GPIO as GPIO

    if tier == "safe":
        GPIO.output(RISK_LED_RED_PIN, GPIO.LOW)
        GPIO.output(RISK_LED_YELLOW_PIN, GPIO.LOW)
        GPIO.output(RISK_LED_GREEN_PIN, GPIO.HIGH)
    elif tier == "warning":
        GPIO.output(RISK_LED_RED_PIN, GPIO.LOW)
        GPIO.output(RISK_LED_YELLOW_PIN, GPIO.HIGH)
        GPIO.output(RISK_LED_GREEN_PIN, GPIO.LOW)
    else:  # danger
        GPIO.output(RISK_LED_RED_PIN, GPIO.HIGH)
        GPIO.output(RISK_LED_YELLOW_PIN, GPIO.LOW)
        GPIO.output(RISK_LED_GREEN_PIN, GPIO.LOW)

    _risk_led_tier = tier
    print(
        f"[LED] Risk Indicator → {tier.upper()} "
        f"(score={combined_risk_score}, R={RISK_LED_RED_PIN} Y={RISK_LED_YELLOW_PIN} G={RISK_LED_GREEN_PIN})"
    )

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
                        f"Check: TRIG→GPIO{TRIG}, ECHO→GPIO{ECHO}, VCC→3.3V (or 5V w/ voltage divider)."
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

import os
import time
import random
import statistics

from config import (
    SENSOR_ECHO_PIN,
    SENSOR_TRIG_PIN,
    SENSOR_TIMEOUT_S,
    SENSOR_BURST_SAMPLES,
    SENSOR_BURST_MIN_VALID,
    SENSOR_BURST_SAMPLE_DELAY_S,
    SENSOR_TEMPERATURE_C,
    RISK_LED_BLOCKED_PIN,
    RISK_LED_PARTIAL_BLOCKED_PIN,
    RISK_LED_CLEAR_PIN,
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
        import RPi.GPIO as GPIO  # type: ignore[import-not-found]
        GPIO_AVAILABLE = True

        print("[GPIO] RPi.GPIO module loaded successfully")
    else:
        print("[GPIO] MOCK_MODE enabled - running in MOCK mode")
except (ImportError, ModuleNotFoundError, RuntimeError):
    MOCK = True
    print("[GPIO] RPi.GPIO not available - running in MOCK mode")

TRIG = SENSOR_TRIG_PIN
ECHO = SENSOR_ECHO_PIN
TIMEOUT = float(SENSOR_TIMEOUT_S)
MAX_RETRIES = 3  # Retry count before giving up

# Initialize GPIO once at module level (only if not in mock mode)
gpio_initialized = False
_risk_led_tier = None  # Track current RGB LED tier to avoid redundant GPIO writes

RISK_LED_PIN_MAP = {
    "blocked": RISK_LED_BLOCKED_PIN,
    "partial_blocked": RISK_LED_PARTIAL_BLOCKED_PIN,
    "clear": RISK_LED_CLEAR_PIN,
}


def _configured_risk_led_pins():
    pins = []
    for pin in RISK_LED_PIN_MAP.values():
        if pin >= 0 and pin not in pins:
            pins.append(pin)
    return pins


def _speed_of_sound_cm_s(temp_c):
    """Return the speed of sound in air in cm/s for a Celsius temperature.

    Uses the standard approximation:
        v = 331.4 + 0.606 * T
    where v is in m/s and T is temperature in Celsius.

    The fallback value 34300.0 cm/s corresponds to approximately 343.0 m/s,
    which is the speed of sound at about 20°C.
    """
    if temp_c is None:
        return 34300.0
    return (331.4 + (0.606 * temp_c)) * 100.0


def _pulse_duration_to_cm(pulse_duration_s, temp_c):
    return (pulse_duration_s * _speed_of_sound_cm_s(temp_c)) / 2.0

def _init_gpio():
    """Initialize GPIO pins once at module load."""
    global gpio_initialized
    if not gpio_initialized and GPIO_AVAILABLE and not MOCK:
        import RPi.GPIO as GPIO  # type: ignore[import-not-found]
        import atexit
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TRIG, GPIO.OUT)
        GPIO.setup(ECHO, GPIO.IN)

        configured_pins = _configured_risk_led_pins()
        if configured_pins:
            for pin in configured_pins:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            print(
                "[GPIO] Risk LED pins initialized: "
                f"blocked={RISK_LED_BLOCKED_PIN} "
                f"partial_blocked={RISK_LED_PARTIAL_BLOCKED_PIN} "
                f"clear={RISK_LED_CLEAR_PIN}"
            )
        else:
            print("[GPIO] Risk LEDs disabled (all state pins are set to -1)")

        gpio_initialized = True
        # Register cleanup to run at exit
        atexit.register(GPIO.cleanup)
        print("[GPIO] Initialized successfully")


def _read_single_distance_cm():
    """Read a single ultrasonic distance sample in cm.

    Raises TimeoutError on echo timeouts.
    Returns None for out-of-range readings.
    """
    import RPi.GPIO as GPIO  # type: ignore[import-not-found]

    # Warn if ECHO is already HIGH — indicates a wiring or power problem.
    # JSN-SR04 wiring notes:
    #   3.3V mode: VCC→3.3V pin — ECHO outputs 3.3V, Pi-safe, no voltage divider needed.
    #   5V mode  : VCC→5V pin  — ECHO outputs 5V; add a 1kΩ/2kΩ divider to protect GPIO.
    if GPIO.input(ECHO) == 1:
        print("[SENSOR] Warning: ECHO is HIGH before trigger. "
              "Check wiring — if VCC is 5V, ECHO needs a 1kΩ/2kΩ voltage divider; "
              "use 3.3V on VCC to avoid this.")

    # Ensure the trigger pin is LOW long enough for the sensor cycle to settle
    # before sending the 10µs trigger pulse. A microsecond-scale sleep is not
    # reliable in Python; 60ms is a conservative delay for JSN-SR04 sensors.
    GPIO.output(TRIG, False)
    time.sleep(0.06)
    GPIO.output(TRIG, True)
    time.sleep(0.00001)  # 10 microseconds
    GPIO.output(TRIG, False)

    # Wait for ECHO to go HIGH (pulse start)
    timeout_start = time.monotonic()
    while GPIO.input(ECHO) == 0:
        if time.monotonic() - timeout_start > TIMEOUT:
            raise TimeoutError("Timeout waiting for echo HIGH")
    pulse_start = time.monotonic()

    # Wait for ECHO to go LOW (pulse end)
    timeout_start = time.monotonic()
    while GPIO.input(ECHO) == 1:
        if time.monotonic() - timeout_start > TIMEOUT:
            raise TimeoutError("Timeout waiting for echo LOW")
    pulse_end = time.monotonic()

    distance_cm = _pulse_duration_to_cm(pulse_end - pulse_start, SENSOR_TEMPERATURE_C)

    # Sanity check: JSN-SR04 valid range is 20 cm – 600 cm
    if not (20.0 <= distance_cm <= 600.0):
        return None

    return distance_cm


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
    """Set risk-state LEDs based on combined risk score.

    Score 0-44   -> clear
    Score 45-75  -> partial_blocked
    Score > 75   -> blocked

    Only writes GPIO when the tier actually changes.
    """
    global _risk_led_tier

    configured_pins = _configured_risk_led_pins()
    if not configured_pins:
        return
    if MOCK or not GPIO_AVAILABLE:
        return
    if combined_risk_score is None:
        return

    # Determine tier
    if combined_risk_score <= 44:
        tier = "clear"
    elif combined_risk_score <= 75:
        tier = "partial_blocked"
    else:
        tier = "blocked"

    # Skip redundant GPIO writes
    if tier == _risk_led_tier:
        return

    import RPi.GPIO as GPIO  # type: ignore[import-not-found]

    for pin in configured_pins:
        GPIO.output(pin, GPIO.LOW)

    active_pin = RISK_LED_PIN_MAP.get(tier, -1)
    if active_pin >= 0:
        GPIO.output(active_pin, GPIO.HIGH)

    _risk_led_tier = tier
    print(
        f"[LED] Risk Indicator -> {tier.upper()} "
        f"(score={combined_risk_score}, active_pin={active_pin})"
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
    
    min_valid = min(SENSOR_BURST_MIN_VALID, SENSOR_BURST_SAMPLES)

    for attempt in range(1, MAX_RETRIES + 1):
        samples = []
        for sample_idx in range(SENSOR_BURST_SAMPLES):
            try:
                distance_cm = _read_single_distance_cm()
                if distance_cm is not None:
                    samples.append(distance_cm)
            except TimeoutError as e:
                print(f"[SENSOR] Timeout (burst {attempt} sample {sample_idx + 1}): {e}")
            except Exception as e:
                print(f"[SENSOR] Error (burst {attempt} sample {sample_idx + 1}): {e}")

            if sample_idx < SENSOR_BURST_SAMPLES - 1:
                time.sleep(SENSOR_BURST_SAMPLE_DELAY_S)

        if len(samples) >= min_valid:
            median_value = statistics.median(samples)
            return round(median_value, 2)

        print(
            f"[SENSOR] Burst {attempt} insufficient valid readings "
            f"(valid={len(samples)}/{SENSOR_BURST_SAMPLES}), retrying..."
        )
        if attempt < MAX_RETRIES:
            time.sleep(0.1)

    print(f"[SENSOR] All {MAX_RETRIES} attempts failed. Returning None.")
    return None

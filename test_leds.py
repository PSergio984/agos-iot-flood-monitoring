#!/usr/bin/env python3
"""
Standalone diagnostic script to test and verify physical risk indicator LEDs.
Drives all configured LED pins simultaneously to ensure wiring, power, and pin
mappings are functioning properly.
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from config import (  # noqa: E402
    RISK_LED_CRITICAL_PIN,
    RISK_LED_SAFE_PIN,
    RISK_LED_WARNING_PIN,
)

# Auto-detect mock mode or hardware availability
MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
try:
    import RPi.GPIO as GPIO  # type: ignore[import-not-found]
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


def get_default_pins():
    """Return configured risk LED pins filtering out disabled (-1) pins."""
    configured = []
    for pin in [RISK_LED_CRITICAL_PIN, RISK_LED_WARNING_PIN, RISK_LED_SAFE_PIN]:
        if pin is not None and pin >= 0:
            configured.append(pin)
    return configured


def parse_args(argv=None):
    """Parse command line arguments for LED testing."""
    parser = argparse.ArgumentParser(
        description="AGOS IoT: Standalone LED Hardware Diagnostic Tool"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Duration in seconds to hold LEDs ON in default mode (default: 3.0)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--hold",
        action="store_true",
        help="Hold all LEDs ON continuously until Ctrl+C is pressed",
    )
    mode_group.add_argument(
        "--blink",
        action="store_true",
        help="Blink all LEDs simultaneously (0.5s cycle) until Ctrl+C is pressed",
    )
    parser.add_argument(
        "--pins",
        type=str,
        default=None,
        help="Comma-separated BCM pin list override (e.g. '14,18,15')",
    )
    return parser.parse_args(argv)


def _resolve_mode(hold: bool = False, blink: bool = False) -> str:
    """Resolve operational mode string."""
    if hold:
        return "hold"
    if blink:
        return "blink"
    return "timed"


def _log_mock_state(pins, symbol, extra=""):
    """Log formatted mock pin status to stdout."""
    timestamp = time.strftime("%H:%M:%S")
    msg = f"[MOCK] [{timestamp}] All pins {pins} -> {symbol}"
    if extra:
        msg += f" {extra}"
    print(msg)


def run_led_test(pins, duration=3.0, hold=False, blink=False, mock=None):
    """Execute the LED test sequence across all specified pins."""
    is_mock = (MOCK or not GPIO_AVAILABLE) if mock is None else mock

    if not pins:
        print("[LED_TEST] [WARNING] No valid LED pins configured (all state pins set to -1).")
        return

    mode = _resolve_mode(hold=hold, blink=blink)
    if mode == "hold":
        mode_desc = "HOLD ON continuously (press Ctrl+C to stop)"
    elif mode == "blink":
        mode_desc = "BLINK 0.5s cycle (press Ctrl+C to stop)"
    else:
        mode_desc = f"ALL ON for {duration} seconds, then OFF"

    print("=" * 55)
    print("AGOS IoT: ALL-LED HARDWARE TEST")
    print("=" * 55)
    print(f"Target BCM Pins: {pins}")
    print(f"Hardware Mode:   {'MOCK / SIMULATED' if is_mock else 'REAL GPIO (RPi.GPIO)'}")
    print(f"Operation Mode:  {mode_desc}")
    print("-" * 55)

    if is_mock:
        _run_mock_test(pins, duration=duration, hold=hold, blink=blink)
    else:
        _run_real_gpio_test(pins, duration=duration, hold=hold, blink=blink)


def _run_mock_test(pins, duration, hold, blink):
    """Simulate LED pin operations in terminal."""
    mode = _resolve_mode(hold=hold, blink=blink)
    try:
        if mode == "hold":
            _log_mock_state(pins, "[ON] ", "(Holding until Ctrl+C)...")
            while True:
                time.sleep(1.0)
        elif mode == "blink":
            print("[MOCK] Starting blink loop (press Ctrl+C to exit)...")
            state = True
            while True:
                _log_mock_state(pins, "[ON] " if state else "[OFF]")
                time.sleep(0.5)
                state = not state
        else:
            _log_mock_state(pins, "[ON] ", f"(holding {duration}s)...")
            time.sleep(duration)
            _log_mock_state(pins, "[OFF]", "(test complete)")
    except KeyboardInterrupt:
        print(f"\n[MOCK] [{time.strftime('%H:%M:%S')}] Stopped by user. All pins {pins} -> [OFF]")


def _set_gpio_pins_level(pins, level):
    """Set the same output logic level across all pins."""
    for pin in pins:
        GPIO.output(pin, level)


def _run_real_gpio_test(pins, duration, hold, blink):
    """Drive real Raspberry Pi GPIO pins."""
    mode = _resolve_mode(hold=hold, blink=blink)
    setup_successful = False
    try:
        GPIO.setmode(GPIO.BCM)
        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        setup_successful = True

        if mode == "hold":
            print("[GPIO] Driving all pins HIGH (press Ctrl+C to exit)...")
            _set_gpio_pins_level(pins, GPIO.HIGH)
            while True:
                time.sleep(1.0)
        elif mode == "blink":
            print("[GPIO] Blinking all pins (press Ctrl+C to exit)...")
            while True:
                _set_gpio_pins_level(pins, GPIO.HIGH)
                time.sleep(0.5)
                _set_gpio_pins_level(pins, GPIO.LOW)
                time.sleep(0.5)
        else:
            print(f"[GPIO] Driving all pins HIGH for {duration}s...")
            _set_gpio_pins_level(pins, GPIO.HIGH)
            time.sleep(duration)
            _set_gpio_pins_level(pins, GPIO.LOW)
            print("[GPIO] Turned all pins LOW. Test completed.")
    except KeyboardInterrupt:
        print("\n[GPIO] Test interrupted by user.")
    finally:
        for pin in pins:
            try:
                GPIO.output(pin, GPIO.LOW)
            except Exception:
                pass
        try:
            GPIO.cleanup(pins)
        except Exception:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        if setup_successful:
            print("[GPIO] Cleanup complete. All pins safely OFF.")


def main(argv=None):
    """Entry point for standalone execution."""
    args = parse_args(argv)

    if args.pins is not None:
        raw_pins = args.pins.strip()
        if not raw_pins:
            print(f"[ERROR] Invalid --pins value: '{args.pins}'. Must specify at least one pin number.")
            sys.exit(1)
        try:
            parsed_pins = [int(p.strip()) for p in raw_pins.split(",") if p.strip()]
            if not parsed_pins:
                print(f"[ERROR] Invalid --pins value: '{args.pins}'. Must specify at least one pin number.")
                sys.exit(1)
            if any(p < 0 for p in parsed_pins):
                print(f"[ERROR] Invalid --pins value: '{args.pins}'. Pin numbers cannot be negative.")
                sys.exit(1)
            pins = parsed_pins
        except ValueError:
            print(f"[ERROR] Invalid --pins format: '{args.pins}'. Must be comma-separated integers.")
            sys.exit(1)
    else:
        pins = get_default_pins()

    run_led_test(pins, duration=args.duration, hold=args.hold, blink=args.blink)


if __name__ == "__main__":
    main()

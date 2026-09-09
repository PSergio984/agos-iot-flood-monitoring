import sys
import pytest
import test_leds


class FakeGPIO:
    BCM = "BCM"
    OUT = "OUT"
    LOW = 0
    HIGH = 1

    def __init__(self):
        self.calls = []

    def setmode(self, mode):
        self.calls.append(("setmode", mode))

    def setup(self, pin, mode):
        self.calls.append(("setup", pin, mode))

    def output(self, pin, value):
        self.calls.append(("output", pin, value))

    def cleanup(self, pins=None):
        self.calls.append(("cleanup", pins))


@pytest.fixture
def fake_gpio(monkeypatch):
    gpio = FakeGPIO()
    monkeypatch.setitem(sys.modules, "RPi", type(sys)("RPi"))
    monkeypatch.setitem(sys.modules, "RPi.GPIO", gpio)
    monkeypatch.setattr(test_leds, "GPIO", gpio, raising=False)
    monkeypatch.setattr(test_leds, "GPIO_AVAILABLE", True)
    monkeypatch.setattr(test_leds, "MOCK", False)
    return gpio


def test_parse_args_defaults():
    args = test_leds.parse_args([])
    assert args.duration == 3.0
    assert args.hold is False
    assert args.blink is False
    assert args.pins is None


def test_parse_args_custom():
    args = test_leds.parse_args(["--duration", "1.5", "--hold", "--pins", "14,18"])
    assert args.duration == 1.5
    assert args.hold is True
    assert args.blink is False
    assert args.pins == "14,18"


def test_parse_args_blink():
    args = test_leds.parse_args(["--blink"])
    assert args.blink is True
    assert args.hold is False


def test_parse_args_mutually_exclusive_hold_and_blink():
    with pytest.raises(SystemExit):
        test_leds.parse_args(["--hold", "--blink"])


def test_get_default_pins(monkeypatch):
    monkeypatch.setattr(test_leds, "RISK_LED_CRITICAL_PIN", 14)
    monkeypatch.setattr(test_leds, "RISK_LED_WARNING_PIN", 18)
    monkeypatch.setattr(test_leds, "RISK_LED_SAFE_PIN", 15)

    pins = test_leds.get_default_pins()
    assert pins == [14, 18, 15]

    monkeypatch.setattr(test_leds, "RISK_LED_WARNING_PIN", -1)
    assert test_leds.get_default_pins() == [14, 15]


def test_run_led_test_empty_pins(capsys):
    test_leds.run_led_test([])
    out = capsys.readouterr().out
    assert "No valid LED pins configured" in out


def test_run_mock_test(capsys):
    test_leds.run_led_test([14, 18], duration=0.01, mock=True)
    out = capsys.readouterr().out
    assert "MOCK / SIMULATED" in out
    assert "All pins [14, 18] -> [ON]" in out
    assert "All pins [14, 18] -> [OFF]" in out


def test_run_real_gpio_test(fake_gpio, capsys):
    test_leds.run_led_test([14, 18], duration=0.01, mock=False)
    out = capsys.readouterr().out
    assert "REAL GPIO" in out
    assert ("setmode", "BCM") in fake_gpio.calls
    assert ("setup", 14, "OUT") in fake_gpio.calls
    assert ("setup", 18, "OUT") in fake_gpio.calls
    assert ("output", 14, FakeGPIO.HIGH) in fake_gpio.calls
    assert ("output", 18, FakeGPIO.HIGH) in fake_gpio.calls
    assert ("output", 14, FakeGPIO.LOW) in fake_gpio.calls
    assert ("output", 18, FakeGPIO.LOW) in fake_gpio.calls
    assert ("cleanup", [14, 18]) in fake_gpio.calls


def test_main_with_valid_args(monkeypatch, capsys):
    test_leds.main(["--duration", "0.01", "--pins", "14,15"])
    out = capsys.readouterr().out
    assert "Target BCM Pins: [14, 15]" in out


def test_main_invalid_pins(capsys):
    with pytest.raises(SystemExit) as exc_info:
        test_leds.main(["--pins", "invalid_pin"])
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "Invalid --pins format" in out

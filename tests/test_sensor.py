import pytest
import sensor


def test_get_water_level_mock_value_in_expected_range(monkeypatch):
    monkeypatch.setattr(sensor, "MOCK", True)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", False)
    monkeypatch.setattr(sensor.random, "uniform", lambda a, b: 2.25)

    level = sensor.get_water_level()

    assert level == 14.75


def test_update_risk_led_noop_when_mock_enabled(monkeypatch):
    monkeypatch.setattr(sensor, "MOCK", True)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", False)

    # Should simply return and not raise.
    sensor.update_risk_led(50)


def test_update_risk_led_noop_when_score_missing(monkeypatch):
    monkeypatch.setattr(sensor, "MOCK", True)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", False)

    sensor.update_risk_led(None)


def test_update_risk_led_logs_score_and_pin_when_gpio_unavailable(monkeypatch, caplog):
    monkeypatch.setattr(sensor, "MOCK", False)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", False)
    monkeypatch.setattr(
        sensor,
        "RISK_LED_PIN_MAP",
        {"critical": 3, "warning": 2, "safe": 1},
    )

    with caplog.at_level("INFO"):
        sensor.update_risk_led(80)

    assert "Risk score=80 tier=CRITICAL active_pin=3" in caplog.text


class FakeGPIO:
    BCM = "BCM"
    OUT = "OUT"
    IN = "IN"
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

    def cleanup(self):
        self.calls.append(("cleanup",))


@pytest.fixture
def fake_gpio(monkeypatch):
    import sys

    gpio = FakeGPIO()
    monkeypatch.setitem(sys.modules, "RPi", type(sys)("RPi"))
    monkeypatch.setitem(sys.modules, "RPi.GPIO", gpio)
    return gpio


def test_update_risk_led_disabled_by_config(monkeypatch, fake_gpio, caplog):
    monkeypatch.setattr(sensor, "RISK_LED_ENABLED", False)
    monkeypatch.setattr(sensor, "MOCK", False)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", True)
    monkeypatch.setattr(
        sensor,
        "RISK_LED_PIN_MAP",
        {"critical": 3, "warning": 2, "safe": 1},
    )

    with caplog.at_level("INFO"):
        sensor.update_risk_led(20)

    assert "Risk score=20 tier=SAFE active_pin=1 (LED disabled by config)" in caplog.text
    # Verify no GPIO output was driven HIGH
    assert not any(call[0] == "output" and call[2] == FakeGPIO.HIGH for call in fake_gpio.calls)


def test_init_gpio_pins_low_when_disabled(monkeypatch, fake_gpio, capsys):
    monkeypatch.setattr(sensor, "gpio_initialized", False)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", True)
    monkeypatch.setattr(sensor, "MOCK", False)
    monkeypatch.setattr(sensor, "RISK_LED_ENABLED", False)
    monkeypatch.setattr(sensor, "RISK_LED_CRITICAL_PIN", 14)
    monkeypatch.setattr(sensor, "RISK_LED_WARNING_PIN", 18)
    monkeypatch.setattr(sensor, "RISK_LED_SAFE_PIN", 15)
    monkeypatch.setattr(
        sensor,
        "RISK_LED_PIN_MAP",
        {"critical": 14, "warning": 18, "safe": 15},
    )

    sensor._init_gpio()

    out = capsys.readouterr().out
    assert "[GPIO] Risk LEDs disabled by config (pins forced LOW)" in out
    assert ("setup", 14, "OUT") in fake_gpio.calls
    assert ("output", 14, 0) in fake_gpio.calls
    assert ("setup", 18, "OUT") in fake_gpio.calls
    assert ("output", 18, 0) in fake_gpio.calls
    assert ("setup", 15, "OUT") in fake_gpio.calls
    assert ("output", 15, 0) in fake_gpio.calls


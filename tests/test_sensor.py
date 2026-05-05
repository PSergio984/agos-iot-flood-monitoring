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

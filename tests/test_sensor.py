import sensor


def test_get_water_level_mock_value_in_expected_range(monkeypatch):
    monkeypatch.setattr(sensor, "MOCK", True)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", False)
    monkeypatch.setattr(sensor.random, "uniform", lambda a, b: 2.25)

    level = sensor.get_water_level()

    assert level == 14.75


def test_update_warning_led_noop_when_feature_disabled(monkeypatch):
    monkeypatch.setattr(sensor, "LED_WARNING_ENABLED", False)

    # Should simply return and not raise.
    sensor.update_warning_led(5.0)


def test_update_warning_led_noop_when_mock_enabled(monkeypatch):
    monkeypatch.setattr(sensor, "LED_WARNING_ENABLED", True)
    monkeypatch.setattr(sensor, "MOCK", True)
    monkeypatch.setattr(sensor, "GPIO_AVAILABLE", False)

    sensor.update_warning_led(5.0)

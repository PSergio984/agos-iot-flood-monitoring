import config


def test_filter_config_types_and_basic_constraints():
    assert isinstance(config.SENSOR_FILTER_ENABLED, bool)
    assert isinstance(config.SENSOR_FILTER_WINDOW_SIZE, int)
    assert isinstance(config.SENSOR_FILTER_MIN_VALID_SAMPLES, int)
    assert isinstance(config.SENSOR_FILTER_MIN_CM, float)
    assert isinstance(config.SENSOR_FILTER_MAX_CM, float)
    assert isinstance(config.SENSOR_FILTER_MODZ_THRESHOLD, float)
    assert isinstance(config.SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM, float)

    assert config.SENSOR_FILTER_WINDOW_SIZE >= 1
    assert config.SENSOR_FILTER_MIN_VALID_SAMPLES >= 1
    assert config.SENSOR_FILTER_MIN_VALID_SAMPLES <= config.SENSOR_FILTER_WINDOW_SIZE
    assert config.SENSOR_FILTER_MIN_CM >= 0
    assert config.SENSOR_FILTER_MAX_CM >= config.SENSOR_FILTER_MIN_CM
    assert config.SENSOR_FILTER_MODZ_THRESHOLD > 0
    assert config.SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM >= 0

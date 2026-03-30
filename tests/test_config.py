import config


def test_filter_config_types_and_basic_constraints():
    assert isinstance(config.SENSOR_FILTER_ENABLED, bool)
    assert isinstance(config.SENSOR_POST_ENABLED, bool)
    assert isinstance(config.SENSOR_FILTER_WINDOW_SIZE, int)
    assert isinstance(config.SENSOR_FILTER_MIN_VALID_SAMPLES, int)
    assert isinstance(config.SENSOR_FILTER_MIN_CM, float)
    assert isinstance(config.SENSOR_FILTER_MAX_CM, float)
    assert isinstance(config.SENSOR_FILTER_MODZ_THRESHOLD, float)
    assert isinstance(config.SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM, float)
    assert isinstance(config.SENSOR_FILTER_REBASELINE_OUTLIER_STREAK, int)

    assert config.SENSOR_FILTER_WINDOW_SIZE >= 1
    assert config.SENSOR_FILTER_MIN_VALID_SAMPLES >= 1
    assert config.SENSOR_FILTER_MIN_VALID_SAMPLES <= config.SENSOR_FILTER_WINDOW_SIZE
    assert config.SENSOR_FILTER_MIN_CM >= 0
    assert config.SENSOR_FILTER_MAX_CM >= config.SENSOR_FILTER_MIN_CM
    assert config.SENSOR_FILTER_MODZ_THRESHOLD > 0
    assert config.SENSOR_FILTER_ZERO_MAD_TOLERANCE_CM >= 0
    assert config.SENSOR_FILTER_REBASELINE_OUTLIER_STREAK >= 2


def test_frame_quality_config_types_and_basic_constraints():
    assert isinstance(config.WS_SEND_METADATA_FIRST, bool)
    assert isinstance(config.LED_WARNING_ENABLED, bool)
    assert isinstance(config.LED_WARNING_PIN, int)
    assert isinstance(config.LED_WARNING_THRESHOLD_CM, float)
    assert isinstance(config.LED_CLEAR_ENABLED, bool)
    assert isinstance(config.LED_CLEAR_PIN, int)
    assert isinstance(config.FRAME_QUALITY_CHECK_ENABLED, bool)
    assert isinstance(config.FRAME_QUALITY_MIN_BRIGHTNESS, float)
    assert isinstance(config.FRAME_QUALITY_MAX_BRIGHTNESS, float)
    assert isinstance(config.FRAME_QUALITY_MIN_CONTRAST_STDDEV, float)
    assert isinstance(config.FRAME_QUALITY_MIN_LAPLACIAN_VAR, float)
    assert isinstance(config.FRAME_QUALITY_RESIZE_WIDTH, int)

    assert 0 <= config.FRAME_QUALITY_MIN_BRIGHTNESS <= 255
    assert 0 <= config.FRAME_QUALITY_MAX_BRIGHTNESS <= 255
    assert config.FRAME_QUALITY_MAX_BRIGHTNESS >= config.FRAME_QUALITY_MIN_BRIGHTNESS
    assert config.FRAME_QUALITY_MIN_CONTRAST_STDDEV >= 0
    assert config.FRAME_QUALITY_MIN_LAPLACIAN_VAR >= 0
    assert config.FRAME_QUALITY_RESIZE_WIDTH >= 0
    assert config.LED_WARNING_PIN >= 0
    assert config.LED_CLEAR_PIN >= 0
    assert config.LED_WARNING_THRESHOLD_CM >= 0

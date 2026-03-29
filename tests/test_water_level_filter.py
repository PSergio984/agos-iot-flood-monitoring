import math

from water_level_filter import WaterLevelFilter


def make_filter(**overrides):
    params = {
        "enabled": True,
        "window_size": 7,
        "min_valid_samples": 3,
        "min_cm": 0.0,
        "max_cm": 400.0,
        "modz_threshold": 3.5,
        "zero_mad_tolerance_cm": 1.0,
    }
    params.update(overrides)
    return WaterLevelFilter(**params)


def test_none_reading_is_rejected():
    f = make_filter()
    value, status = f.process(None)
    assert value is None
    assert status == "no-reading"


def test_non_numeric_is_rejected():
    f = make_filter()
    value, status = f.process("abc")
    assert value is None
    assert status == "non-numeric"


def test_non_finite_is_rejected():
    f = make_filter()

    value, status = f.process(float("nan"))
    assert value is None and status == "non-finite"

    value, status = f.process(float("inf"))
    assert value is None and status == "non-finite"


def test_out_of_range_is_rejected():
    f = make_filter(min_cm=10.0, max_cm=20.0)

    value, status = f.process(9.99)
    assert value is None and status == "out-of-range"

    value, status = f.process(20.01)
    assert value is None and status == "out-of-range"


def test_range_boundaries_are_inclusive():
    f = make_filter(min_cm=10.0, max_cm=20.0)

    value, status = f.process(10.0)
    assert value == 10.0 and status == "ok"

    value, status = f.process(20.0)
    assert value == 15.0 and status == "ok"


def test_disabled_filter_bypasses_smoothing():
    f = make_filter(enabled=False)
    value, status = f.process(12.34)
    assert value == 12.34
    assert status == "bypass"


def test_window_and_min_valid_are_clamped():
    f = make_filter(window_size=1, min_valid_samples=0)
    assert f.window_size == 3
    assert f.min_valid_samples == 1


def test_moving_average_on_accepted_values():
    f = make_filter(min_valid_samples=99)

    v1, _ = f.process(10)
    v2, _ = f.process(11)
    v3, _ = f.process(12)

    assert v1 == 10
    assert v2 == 10.5
    assert v3 == 11


def test_zero_mad_outlier_rejected_with_tolerance():
    f = make_filter(min_valid_samples=3, zero_mad_tolerance_cm=0.5)

    assert f.process(10)[0] is not None
    assert f.process(10)[0] is not None
    assert f.process(10)[0] is not None

    value, status = f.process(11.0)
    assert value is None
    assert status == "outlier-zero-mad"


def test_modz_outlier_rejected_when_mad_non_zero():
    f = make_filter(min_valid_samples=3, modz_threshold=3.5)

    for sample in (10, 11, 10, 11, 10, 11):
        assert f.process(sample)[0] is not None

    value, status = f.process(30)
    assert value is None
    assert status == "outlier-modz"


def test_rejected_value_does_not_pollute_history():
    f = make_filter(min_valid_samples=3, zero_mad_tolerance_cm=0.1)

    for _ in range(3):
        f.process(10)

    value, status = f.process(50)
    assert value is None and status.startswith("outlier")

    value, status = f.process(10)
    assert value == 10
    assert status == "ok"


def test_window_rolls_and_drops_old_values():
    f = make_filter(window_size=3, min_valid_samples=99)

    f.process(10)
    f.process(20)
    f.process(30)
    value, status = f.process(40)

    assert status == "ok"
    assert math.isclose(value, 30.0)
    assert list(f._history) == [20, 30, 40]


def test_outlier_check_waits_for_min_valid_samples():
    f = make_filter(min_valid_samples=5, zero_mad_tolerance_cm=0.1)

    for _ in range(4):
        value, status = f.process(10)
        assert value is not None and status == "ok"

    value, status = f.process(50)
    assert value is not None and status == "ok"

    value, status = f.process(50)
    assert value is None
    assert status == "outlier-zero-mad"

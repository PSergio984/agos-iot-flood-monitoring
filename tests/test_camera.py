import datetime as dt
from pathlib import Path

import camera


def test_capture_image_uses_training_fallback_images(monkeypatch, tmp_path):
    training_captures = tmp_path / "training_captures"
    training_captures.mkdir()
    src = training_captures / "capture_01.jpg"
    src.write_bytes(b"source-bytes")

    dst = tmp_path / "out.jpg"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(camera, "MOCK", True)
    monkeypatch.setattr(camera, "PICAMERA_AVAILABLE", False)
    monkeypatch.setattr(camera, "USE_FSWEBCAM", False)
    monkeypatch.setattr(camera, "TRAINING_CAPTURES_DIR", str(training_captures))
    monkeypatch.setattr(camera, "TRAINING_RAINING_DIR", str(tmp_path / "training_raining"))

    result = camera.capture_image(str(dst))

    assert result == str(dst)
    assert dst.read_bytes() == b"source-bytes"


def test_capture_image_falls_through_when_training_copy_fails(monkeypatch, tmp_path):
    training_captures = tmp_path / "training_captures"
    training_captures.mkdir()
    src = training_captures / "capture_01.jpg"
    src.write_bytes(b"source-bytes"
    )

    dst = tmp_path / "out.jpg"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(camera, "MOCK", True)
    monkeypatch.setattr(camera, "PICAMERA_AVAILABLE", False)
    monkeypatch.setattr(camera, "USE_FSWEBCAM", False)
    monkeypatch.setattr(camera, "TRAINING_CAPTURES_DIR", str(training_captures))
    monkeypatch.setattr(camera, "TRAINING_RAINING_DIR", str(tmp_path / "training_raining"))
    monkeypatch.setattr(camera.shutil, "copy2", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy failed")))

    result = camera.capture_image(str(dst))

    assert result == str(dst)
    assert dst.exists()
    assert dst.read_bytes() != b"source-bytes"


def test_persistent_camera_capture_delegates_to_capture_image_in_mock(monkeypatch, tmp_path):
    monkeypatch.setattr(camera, "MOCK", True)
    monkeypatch.setattr(camera, "PICAMERA_AVAILABLE", False)

    out = tmp_path / "frame.jpg"

    called = {"ok": False}

    def fake_capture_image(path):
        called["ok"] = True
        Path(path).write_bytes(b"frame")
        return path

    monkeypatch.setattr(camera, "capture_image", fake_capture_image)

    cam = camera.PersistentCamera()
    result = cam.capture(str(out))

    assert called["ok"] is True
    assert result == str(out)
    assert out.read_bytes() == b"frame"


def test_ir_cut_controller_manual_modes():
    day_ctrl = camera.IRCutController(mode="day", min_switch_interval_s=30)
    night_ctrl = camera.IRCutController(mode="night", min_switch_interval_s=30)

    assert day_ctrl.target_day_mode() is True
    assert night_ctrl.target_day_mode() is False


def test_ir_cut_controller_auto_window(monkeypatch):
    monkeypatch.setattr(camera, "IR_CUT_DAY_START_HOUR", 6)
    monkeypatch.setattr(camera, "IR_CUT_NIGHT_START_HOUR", 18)
    ctrl = camera.IRCutController(mode="auto", min_switch_interval_s=30)

    assert ctrl.target_day_mode(dt.datetime(2025, 1, 1, 7, 0, 0)) is True
    assert ctrl.target_day_mode(dt.datetime(2025, 1, 1, 19, 0, 0)) is False


def test_ir_cut_controller_applies_switch_after_filtering_delay(monkeypatch):
    monkeypatch.setattr(camera, "IR_CUT_DAY_START_HOUR", 6)
    monkeypatch.setattr(camera, "IR_CUT_NIGHT_START_HOUR", 18)
    ctrl = camera.IRCutController(mode="auto", min_switch_interval_s=30)

    calls = []

    def fake_set_ir_cut_mode(day):
        calls.append(day)

    monkeypatch.setattr(camera, "set_ir_cut_mode", fake_set_ir_cut_mode)

    # Initial daytime apply.
    assert ctrl.maybe_apply(now=dt.datetime(2025, 1, 1, 17, 59, 50), force=True) is True
    # Too soon to switch to night.
    assert ctrl.maybe_apply(now=dt.datetime(2025, 1, 1, 18, 0, 10)) is False
    # Delay elapsed: switch should apply.
    assert ctrl.maybe_apply(now=dt.datetime(2025, 1, 1, 18, 0, 25)) is True

    assert calls == [True, False]


def test_get_ir_status_snapshot_reports_phase_and_ir_expectation(monkeypatch):
    monkeypatch.setattr(camera, "IR_CUT_PIN", 17)
    monkeypatch.setattr(camera, "MOCK", False)
    monkeypatch.setattr(camera, "PICAMERA_AVAILABLE", True)
    monkeypatch.setattr(camera, "IR_CUT_DAY_START_HOUR", 6)
    monkeypatch.setattr(camera, "IR_CUT_NIGHT_START_HOUR", 18)
    monkeypatch.setattr(camera._ir_cut_controller, "mode", "auto")

    snapshot = camera.get_ir_status_snapshot(dt.datetime(2025, 1, 1, 9, 0, 0))

    assert snapshot["phase"] == "day"
    assert snapshot["desired_day_mode"] is True
    assert snapshot["ir_pass_expected"] is False
    assert snapshot["ir_cut_filter_expected"] == "engaged"


def test_build_ir_status_image_creates_file(tmp_path):
    out = tmp_path / "ir_status.jpg"

    result = camera.build_ir_status_image(
        str(out),
        now=dt.datetime(2025, 1, 1, 9, 0, 0),
    )

    assert result == str(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_ir_cut_controller_uses_consistent_datetime_awareness(monkeypatch):
    ctrl = camera.IRCutController(mode="auto", min_switch_interval_s=30)

    monkeypatch.setattr(camera, "_IR_CUT_TZ", dt.timezone.utc)
    applied = dt.datetime(2025, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
    ctrl.mark_applied(True, now=applied)

    later = dt.datetime(2025, 1, 1, 0, 0, 31, tzinfo=dt.timezone.utc)
    assert ctrl.should_apply(False, now=later) is True


def test_camera_gain_environment_parsing(monkeypatch):
    import importlib

    # Test American spelling
    monkeypatch.setenv("CAMERA_ANALOG_GAIN", "3.5")
    monkeypatch.delenv("CAMERA_ANALOGUE_GAIN", raising=False)
    importlib.reload(camera)
    assert camera.CAMERA_ANALOGUE_GAIN == 3.5

    # Test British spelling overrides
    monkeypatch.setenv("CAMERA_ANALOGUE_GAIN", "4.0")
    importlib.reload(camera)
    assert camera.CAMERA_ANALOGUE_GAIN == 4.0

    # Test empty string fallback to default 0.0
    monkeypatch.setenv("CAMERA_ANALOGUE_GAIN", "   ")
    monkeypatch.delenv("CAMERA_ANALOG_GAIN", raising=False)
    importlib.reload(camera)
    assert camera.CAMERA_ANALOGUE_GAIN == 0.0


def test_get_temp_dir_prioritizes_shm(monkeypatch):
    monkeypatch.setattr(camera.os.path, "exists", lambda p: p == "/dev/shm")
    monkeypatch.setattr(camera.os.path, "isdir", lambda p: p == "/dev/shm")
    monkeypatch.setattr(camera.os, "access", lambda p, mode: p == "/dev/shm")

    assert camera._get_temp_dir() == "/dev/shm"


def test_get_temp_dir_falls_back_when_no_shm(monkeypatch):
    monkeypatch.setattr(camera.os.path, "exists", lambda p: False)
    assert camera._get_temp_dir() == camera.tempfile.gettempdir()


def test_build_quality_controls_includes_scaler_crop_when_crop_enabled(monkeypatch):
    monkeypatch.setattr(camera, "IMAGE_CROP_ENABLED", True)
    monkeypatch.setattr(camera, "IMAGE_CROP_X", 260)
    monkeypatch.setattr(camera, "IMAGE_CROP_Y", 0)
    monkeypatch.setattr(camera, "IMAGE_CROP_WIDTH", 770)
    monkeypatch.setattr(camera, "IMAGE_CROP_HEIGHT", 680)

    controls = camera._build_quality_controls()
    assert controls["ScalerCrop"] == (260, 0, 770, 680)


def test_apply_software_crop_bypasses_on_hardware(monkeypatch):
    monkeypatch.setattr(camera, "IMAGE_CROP_ENABLED", True)
    monkeypatch.setattr(camera, "MOCK", False)
    monkeypatch.setattr(camera, "PICAMERA_AVAILABLE", True)
    monkeypatch.setattr(camera.os.path, "exists", lambda p: True)

    cv2_called = False
    fake_cv2 = type("FakeCV2", (), {"imread": lambda p: (_ for _ in ()).throw(AssertionError("cv2 should not be called"))})
    monkeypatch.setattr(camera, "cv2", fake_cv2, raising=False)

    # Should return early without calling cv2
    camera._apply_software_crop("some_path.jpg")


def test_is_night_sleep_hours(monkeypatch):
    monkeypatch.setattr(camera, "CAMERA_NIGHT_SLEEP_ENABLED", True)
    monkeypatch.setattr(camera, "CAMERA_NIGHT_SLEEP_START_HOUR", 19)
    monkeypatch.setattr(camera, "CAMERA_NIGHT_SLEEP_END_HOUR", 6)

    # 14:00 -> Daytime
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 1, 14, 0, 0)) is False
    # 18:30 -> Twilight (not yet full night sleep)
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 1, 18, 30, 0)) is False
    # 19:00 -> Full night sleep starts
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 1, 19, 0, 0)) is True
    # 23:30 -> Midnight crossing
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 1, 23, 30, 0)) is True
    # 02:00 -> Early morning before wake
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 2, 2, 0, 0)) is True
    # 06:00 -> Wake up
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 2, 6, 0, 0)) is False
    # 08:00 -> Daytime
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 2, 8, 0, 0)) is False

    # Disabled toggle
    monkeypatch.setattr(camera, "CAMERA_NIGHT_SLEEP_ENABLED", False)
    assert camera.is_night_sleep_hours(dt.datetime(2025, 1, 1, 23, 0, 0)) is False


def test_is_twilight_hours(monkeypatch):
    monkeypatch.setattr(camera, "CAMERA_TWILIGHT_START_HOUR", 18)
    monkeypatch.setattr(camera, "CAMERA_NIGHT_SLEEP_START_HOUR", 19)

    # 17:59 -> Not twilight
    assert camera.is_twilight_hours(dt.datetime(2025, 1, 1, 17, 59, 0)) is False
    # 18:00 -> Twilight begins
    assert camera.is_twilight_hours(dt.datetime(2025, 1, 1, 18, 0, 0)) is True
    # 18:45 -> Twilight active
    assert camera.is_twilight_hours(dt.datetime(2025, 1, 1, 18, 45, 0)) is True
    # 19:00 -> Twilight ends (full night sleep begins)
    assert camera.is_twilight_hours(dt.datetime(2025, 1, 1, 19, 0, 0)) is False




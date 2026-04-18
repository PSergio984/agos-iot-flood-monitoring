from pathlib import Path
import datetime as dt

import camera


def test_capture_image_uses_test_image_copy(monkeypatch, tmp_path):
    src = tmp_path / "test_image.jpg"
    src.write_bytes(b"source-bytes")

    dst = tmp_path / "out.jpg"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(camera, "MOCK", True)
    monkeypatch.setattr(camera, "PICAMERA_AVAILABLE", False)
    monkeypatch.setattr(camera, "USE_FSWEBCAM", False)

    result = camera.capture_image(str(dst))

    assert result == str(dst)
    assert dst.read_bytes() == b"source-bytes"


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

from pathlib import Path

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

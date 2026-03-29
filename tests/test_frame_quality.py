from types import SimpleNamespace

import frame_quality


class _Gray:
    def __init__(self, width=640, height=480):
        self.shape = (height, width)
        self.size = width * height


class _FakeCV2:
    IMREAD_GRAYSCALE = 0
    INTER_AREA = 1
    CV_64F = 2

    def __init__(self, brightness=120.0, contrast=30.0, laplacian_var=200.0):
        self._brightness = brightness
        self._contrast = contrast
        self._laplacian_var = laplacian_var
        self.resize_calls = 0

    def imread(self, _path, _flag):
        return _Gray(width=640, height=480)

    def resize(self, _gray, size, interpolation):
        assert interpolation == self.INTER_AREA
        self.resize_calls += 1
        return _Gray(width=size[0], height=size[1])

    def meanStdDev(self, _gray):
        return [[self._brightness]], [[self._contrast]]

    def Laplacian(self, _gray, ddepth):
        assert ddepth == self.CV_64F
        return SimpleNamespace(var=lambda: self._laplacian_var)


def test_is_frame_usable_returns_true_when_check_disabled(monkeypatch):
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", False)

    assert frame_quality.is_frame_usable("does-not-matter.jpg") is True


def test_is_frame_usable_returns_false_for_missing_file(monkeypatch):
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", True)

    assert frame_quality.is_frame_usable("missing.jpg") is False


def test_is_frame_usable_returns_true_when_cv2_unavailable(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"x")

    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", True)
    monkeypatch.setattr(frame_quality, "cv2", None)

    assert frame_quality.is_frame_usable(str(image)) is True


def test_is_frame_usable_rejects_low_brightness(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"x")

    fake_cv2 = _FakeCV2(brightness=5.0)
    monkeypatch.setattr(frame_quality, "cv2", fake_cv2)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", True)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MIN_BRIGHTNESS", 25.0)

    assert frame_quality.is_frame_usable(str(image)) is False


def test_is_frame_usable_rejects_high_brightness(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"x")

    fake_cv2 = _FakeCV2(brightness=250.0)
    monkeypatch.setattr(frame_quality, "cv2", fake_cv2)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", True)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MAX_BRIGHTNESS", 230.0)

    assert frame_quality.is_frame_usable(str(image)) is False


def test_is_frame_usable_rejects_low_contrast(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"x")

    fake_cv2 = _FakeCV2(contrast=5.0)
    monkeypatch.setattr(frame_quality, "cv2", fake_cv2)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", True)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MIN_CONTRAST_STDDEV", 10.0)

    assert frame_quality.is_frame_usable(str(image)) is False


def test_is_frame_usable_rejects_low_laplacian_variance(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"x")

    fake_cv2 = _FakeCV2(laplacian_var=20.0)
    monkeypatch.setattr(frame_quality, "cv2", fake_cv2)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", True)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MIN_LAPLACIAN_VAR", 80.0)

    assert frame_quality.is_frame_usable(str(image)) is False


def test_is_frame_usable_accepts_good_frame(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"x")

    fake_cv2 = _FakeCV2(brightness=120.0, contrast=30.0, laplacian_var=200.0)
    monkeypatch.setattr(frame_quality, "cv2", fake_cv2)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_CHECK_ENABLED", True)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MIN_BRIGHTNESS", 25.0)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MAX_BRIGHTNESS", 230.0)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MIN_CONTRAST_STDDEV", 10.0)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_MIN_LAPLACIAN_VAR", 80.0)
    monkeypatch.setattr(frame_quality, "FRAME_QUALITY_RESIZE_WIDTH", 320)

    assert frame_quality.is_frame_usable(str(image)) is True
    assert fake_cv2.resize_calls == 1

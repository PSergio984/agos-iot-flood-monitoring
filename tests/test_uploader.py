from types import SimpleNamespace

import uploader


def test_upload_image_success(monkeypatch):
    def fake_upload(path, folder):
        assert path == "image.jpg"
        assert folder == "agos/"
        return {"secure_url": "https://cdn.example.com/image.jpg"}

    monkeypatch.setattr(uploader.cloudinary.uploader, "upload", fake_upload)

    assert uploader.upload_image("image.jpg") == "https://cdn.example.com/image.jpg"


def test_upload_image_missing_secure_url(monkeypatch):
    monkeypatch.setattr(uploader.cloudinary.uploader, "upload", lambda path, folder: {"public_id": "x"})

    assert uploader.upload_image("image.jpg") is None


def test_upload_image_handles_cloudinary_exception(monkeypatch):
    class FakeErr(Exception):
        pass

    fake_exceptions = SimpleNamespace(Error=FakeErr)
    monkeypatch.setattr(uploader.cloudinary, "exceptions", fake_exceptions)

    def fake_upload(path, folder):
        raise FakeErr("boom")

    monkeypatch.setattr(uploader.cloudinary.uploader, "upload", fake_upload)

    assert uploader.upload_image("image.jpg") is None


def test_upload_image_handles_generic_exception(monkeypatch):
    def fake_upload(path, folder):
        raise RuntimeError("boom")

    monkeypatch.setattr(uploader.cloudinary.uploader, "upload", fake_upload)

    assert uploader.upload_image("image.jpg") is None

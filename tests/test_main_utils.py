import json
from pathlib import Path
from types import SimpleNamespace

import main


def test_safe_ws_url_strips_sensitive_parts():
    url = "wss://user:pass@example.com:9000/ws/path?a=1#frag"
    assert main._safe_ws_url(url) == "wss://example.com:9000"


def test_safe_ws_url_invalid_value():
    assert main._safe_ws_url(None) == "<invalid url>"


def test_send_image_websocket_returns_false_when_ws_lib_unavailable(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"abc")

    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", False)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:8000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_returns_false_when_url_missing(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"abc")

    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_success(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWS:
        def __init__(self):
            self.frames = []
            self.closed = False

        def send(self, payload):
            self.frames.append(("text", payload))

        def send_binary(self, payload):
            self.frames.append(("binary", payload))

        def close(self):
            self.closed = True

    fake_ws = FakeWS()

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            assert timeout == 10
            return fake_ws

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", True)

    assert main.send_image_websocket(
        str(image),
        cloudinary_url="https://cdn/x.jpg",
        extra_metadata={"frame_role": "camera_frame", "phase": "day"},
    ) is True
    assert fake_ws.closed is True
    assert len(fake_ws.frames) == 2

    frame_type, text_payload = fake_ws.frames[0]
    assert frame_type == "text"
    metadata = json.loads(text_payload)
    assert metadata["type"] == "image"
    assert metadata["filename"] == Path(image).name
    assert metadata["cloudinary_url"] == "https://cdn/x.jpg"
    assert metadata["frame_role"] == "camera_frame"
    assert metadata["phase"] == "day"

    frame_type, binary_payload = fake_ws.frames[1]
    assert frame_type == "binary"
    assert binary_payload == b"jpeg-bytes"


def test_send_image_websocket_binary_only_mode(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWS:
        def __init__(self):
            self.frames = []
            self.closed = False

        def send(self, payload):
            self.frames.append(("text", payload))

        def send_binary(self, payload):
            self.frames.append(("binary", payload))

        def close(self):
            self.closed = True

    fake_ws = FakeWS()

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            assert timeout == 10
            return fake_ws

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", False)

    assert main.send_image_websocket(str(image), cloudinary_url="https://cdn/x.jpg") is True
    assert fake_ws.closed is True
    assert fake_ws.frames == [("binary", b"jpeg-bytes")]


def test_send_image_websocket_timeout_path(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            raise FakeWebsocketModule.WebSocketTimeoutException("timeout")

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_closed_connection_path(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            raise FakeWebsocketModule.WebSocketConnectionClosedException("closed")

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_oserror_path(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    fake_module = SimpleNamespace(
        WebSocketTimeoutException=RuntimeError,
        WebSocketConnectionClosedException=RuntimeError,
    )

    def _raise(_url, timeout):
        raise OSError("network down")

    fake_module.create_connection = _raise

    monkeypatch.setattr(main, "_websocket", fake_module)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False
